"""GitHub REST client: token bootstrap (gh auth token / env), request-level
SQLite cache, rate-limit awareness. Pure stdlib.

富化成本口径（评审结论）：每仓 5 个固定请求（repo meta / releases / issues
closed 90d / contributors / readme），commits_90d 默认关（可选开，用
Link header rel=last 技巧单请求拿 90 天 commit 数）。
"""
import base64
import json
import subprocess
import time
import urllib.error
import urllib.request

from .cache import RequestCache

_API = "https://api.github.com"


def load_token() -> str:
    import os

    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env and env.strip():
        return env.strip()
    result = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, timeout=15)
    token = result.stdout.strip()
    if not token:
        raise RuntimeError("拿不到 GitHub token：gh auth token 失败且无 GITHUB_TOKEN 环境变量")
    return token


class GithubClient:
    def __init__(self, token: str, cache: RequestCache | None = None):
        self.token = token
        self.cache = cache
        self.calls = 0          # 真实发出的网络请求数（缓存命中不计）
        self.limited_wait = 0.0  # 因限流累计等待秒数

    def _headers(self, accept: str = "application/vnd.github+json") -> dict:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": accept,
            "User-Agent": "analysis-engine",
        }

    def get_json(self, url: str, ttl_hours: float | None = None) -> dict | list | None:
        """GET → parsed JSON。缓存命中不发网络请求。404 → None（调用方自行容错）。"""
        if self.cache:
            hit = self.cache.get(url)
            if hit is not None:
                return json.loads(hit)
        try:
            self._throttled_get(url, accept_json=True)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code in (403, 429):  # 限流：读重置时间，等待后重试一次
                self.limited_wait += self._wait_for_reset()
                return self.get_json(url, ttl_hours)
            raise
        raw = self._throttled_get(url, accept_json=True)
        body = raw.decode("utf-8", errors="replace")
        if self.cache:
            self.cache.put(url, body, ttl_hours)
        return json.loads(body)

    def get_text(self, url: str, accept: str, ttl_hours: float | None = None) -> str | None:
        if self.cache:
            hit = self.cache.get(url)
            if hit is not None:
                return hit
        try:
            raw = self._throttled_get(url, accept_json=False, accept=accept)
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code in (403, 429):
                self.limited_wait += self._wait_for_reset()
                return self.get_text(url, accept, ttl_hours)
            raise
        body = raw.decode("utf-8", errors="replace")
        if self.cache:
            self.cache.put(url, body, ttl_hours)
        return body

    def _throttled_get(self, url: str, accept_json: bool, accept: str = "application/vnd.github+json") -> bytes:
        request = urllib.request.Request(url, headers=self._headers(accept))
        with urllib.request.urlopen(request, timeout=30) as response:
            self.calls += 1
            return response.read()

    def _wait_for_reset(self) -> float:
        """核心配额耗尽（remaining=0）→ 等到 reset；次级滥用检测 → 等 60s。"""
        try:
            request = urllib.request.Request(f"{_API}/rate_limit", headers=self._headers())
            data = json.load(urllib.request.urlopen(request, timeout=15))
            core = data["resources"]["core"]
            if core.get("remaining", 1) == 0:
                wait = max(1.0, min(core["reset"] - time.time() + 1, 600))
            else:
                wait = 60.0  # 次级限制：无 reset 时间，等一分钟再试
        except Exception:
            wait = 60.0
        time.sleep(wait)
        return wait

    # ---- 富化用的封装 ----

    def readme_text(self, full_name: str) -> str | None:
        raw = self.get_text(f"{_API}/repos/{full_name}/readme",
                            "application/vnd.github.raw+json")
        return raw

    def readme_via_search_payload(self, full_name: str) -> str | None:
        """base64 路径备用（raw 被代理污染时）。"""
        payload = self.get_json(f"{_API}/repos/{full_name}/readme")
        if not payload or not payload.get("content"):
            return None
        return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
