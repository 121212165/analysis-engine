"""富化层：每仓补 5 类信号原料（并发≤4，限流退避交给 http 层）。

每仓请求数（配额口径）：
- /repos/{full}                    1  (license/open_issues/pushed_at)
- /repos/{full}/releases/latest    1  (404 容错 → None)
- search issues closed>=90d        1  (total_count，比逐仓翻 issues 便宜)
- /repos/{full}/contributors?per_page=1  1  (Link rel=last 页号 = 人数)
- /repos/{full}/readme (raw)       1
- /repos/{full}/commits?since=     0-1（可选，Link rel=last 技巧）
"""
import concurrent.futures
import datetime
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .models import RepoRecord

_SINCE_90D = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=90)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _last_page(url: str, token: str) -> int | None:
    """发一个 per_page=1 的请求，从 Link header 解出总页数 = 计数。"""
    request = urllib.request.Request(f"{url}{'&' if '?' in url else '?'}per_page=1", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "analysis-engine",
    })
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            link = response.headers.get("Link", "")
            return _parse_last_page(link) or 1
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return None
        raise


def _parse_last_page(link: str) -> int | None:
    match = re.search(r'[?&]page=(\d+)>;\s*rel="last"', link)
    return int(match.group(1)) if match else None


def _safe(fn):
    """单信号容错：一个请求挂了只损失那一个字段，不拖垮整仓。"""
    try:
        return fn()
    except Exception:
        return None


def enrich_one(client, record: RepoRecord, token: str, commits_90d: bool = False) -> RepoRecord:
    full = record.full_name
    pause = lambda: time.sleep(random.uniform(0.3, 0.8))  # 礼貌间隔，避开次级滥用检测

    def apply_meta():
        meta = client.get_json(f"https://api.github.com/repos/{full}")
        if isinstance(meta, dict):
            license_info = meta.get("license") or {}
            record.license_spdx = license_info.get("spdx_id") if license_info.get("spdx_id") not in ("NOASSERTION", None) else None
            record.open_issues = meta.get("open_issues_count")
            record.pushed_at = meta.get("pushed_at") or record.pushed_at
            record.forks = meta.get("forks_count", record.forks)
            record.stars = meta.get("stargazers_count", record.stars)

    def apply_release():
        release = client.get_json(f"https://api.github.com/repos/{full}/releases/latest")
        if isinstance(release, dict):
            record.latest_release_at = release.get("published_at")

    def apply_issues():
        issues = client.get_json(
            "https://api.github.com/search/issues?q=" + urllib.parse.quote(f"repo:{full} is:issue closed:>={_SINCE_90D}") + "&per_page=1"
        )
        if isinstance(issues, dict):
            record.closed_issues_90d = issues.get("total_count", 0)

    def apply_contributors():
        record.contributors = _last_page(f"https://api.github.com/repos/{full}/contributors", token)

    def apply_commits():
        record.commits_90d = _last_page(f"https://api.github.com/repos/{full}/commits?since={_SINCE_90D}", token)

    def apply_readme():
        readme = client.readme_text(full)
        if readme is None:
            readme = client.readme_via_search_payload(full)
        record.readme_full = readme
        record.readme_len = len(readme) if readme else 0

    steps = [apply_meta, pause, apply_release, pause, apply_issues, pause, apply_contributors]
    if commits_90d:
        steps += [pause, apply_commits]
    steps += [pause, apply_readme]
    for step in steps:
        step() if step is pause else _safe(step)
    return record


def enrich_all(client, records: list[RepoRecord], token: str, config) -> list[RepoRecord]:
    targets = records[: config.enrich_limit]
    with concurrent.futures.ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        futures = {pool.submit(enrich_one, client, record, token, config.commits_90d): record for record in targets}
        errors: dict[str, str] = {}
        for future in concurrent.futures.as_completed(futures):
            record = futures[future]
            try:
                future.result()
            except Exception as error:  # 单仓失败不拖垮整批
                errors[record.full_name] = str(error)[:200]
    return targets
