"""采集层：四通道搜索（phrase/loose/readme/topic）+ topics 挖词 + 迭代止损。

方法学与 dsh-plugin-deep-scan 一致，但走 REST API（token 来自 gh auth token），
不再每请求起一个 gh.exe 进程。
"""
import time
import urllib.parse

from .config import CHANNEL_PRIORITY, NOISE_TOPICS
from .models import RepoRecord

_SEARCH = "https://api.github.com/search/repositories"


def _search_url(query: str, per_channel: int, sort: str) -> str:
    params = urllib.parse.urlencode({"q": query, "per_page": per_page_cap(per_channel), "sort": sort, "order": "desc"})
    return f"{_SEARCH}?{params}"


def per_page_cap(n: int) -> int:
    return max(1, min(int(n), 100))


def search_one(client, query: str, per_channel: int = 30, sort: str = "") -> list[dict]:
    url = _search_url(query, per_channel, sort)
    payload = client.get_json(url)
    if not payload:
        return []
    return [item for item in payload.get("items", []) if not item.get("fork") and not item.get("archived")]


def search_channel(client, term: str, channel: str, per_channel: int, qualifiers: str = "") -> list[dict]:
    """channel ∈ phrase/loose/readme/topic。qualifiers 拼在引号外（language:/stars: 等）。"""
    suffix = f" {qualifiers.strip()}" if qualifiers.strip() else ""
    if channel == "phrase":
        return search_one(client, f'"{term}"{suffix}', per_channel)
    if channel == "loose":
        return search_one(client, f"{term}{suffix}", per_channel, sort="stars")
    if channel == "readme":
        return search_one(client, f"{term}{suffix} in:readme", per_channel, sort="stars")
    if channel == "topic":
        fixed = term if term.startswith("topic:") else f"topic:{term}"
        return search_one(client, f"{fixed}{suffix}", per_channel, sort="stars")
    raise ValueError(f"unknown channel: {channel}")


CHANNELS = ("phrase", "loose", "readme", "topic")


def mine_topics(records: list[RepoRecord], exclude: set[str], limit: int = 4) -> list[tuple[str, int]]:
    """从精准命中池统计 topics → [(topic, count)]，滤噪声、排除已搜词、count≥2。"""
    stats: dict[str, int] = {}
    for record in records:
        if CHANNEL_PRIORITY.get(record.channels[0], 9) > 1:  # 只统计 phrase/loose 命中
            continue
        for topic in record.topics:
            topic = topic.strip().lower()
            if topic and topic not in NOISE_TOPICS and topic not in exclude:
                stats[topic] = stats.get(topic, 0) + 1
    mined = sorted(((t, c) for t, c in stats.items() if c >= 2), key=lambda pair: (-pair[1], pair[0]))
    return mined[:limit]


class SearchEngine:
    def __init__(self, client, config, qualifiers: str = ""):
        self.client = client
        self.config = config
        self.qualifiers = qualifiers.strip()

    def run_round(self, terms: list[str]) -> dict[str, list[dict]]:
        results: dict[str, list[dict]] = {}
        for term in terms:
            for channel in CHANNELS:
                results[(channel, term)] = search_channel(self.client, term, channel, self.config.per_channel, self.qualifiers)
        return results

    def merge(self, results: dict[str, list[dict]]) -> dict[str, RepoRecord]:
        """去重合并：通道优先级优先保留（首个出现的通道=最精准通道），记录全部命中词。"""
        pool: dict[str, RepoRecord] = {}
        for (channel, term), items in results.items():
            for item in items:
                full_name = item.get("full_name", "")
                if not full_name:
                    continue
                record = pool.get(full_name)
                if record is None:
                    record = RepoRecord(
                        full_name=full_name,
                        stars=item.get("stargazers_count", 0),
                        forks=item.get("forks_count", 0),
                        language=item.get("language"),
                        topics=[t.lower() for t in item.get("topics", [])],
                        description=item.get("description"),
                        updated_at=item.get("updated_at"),
                        pushed_at=item.get("pushed_at"),
                        channels=[channel],
                        matched_queries=[term],
                    )
                    pool[full_name] = record
                else:
                    if channel not in record.channels:
                        record.channels.append(channel)
                    if term not in record.matched_queries:
                        record.matched_queries.append(term)
        return pool

    def run(self, queries: list[str]) -> tuple[dict[str, RepoRecord], list[dict], str]:
        """完整采集链：首搜 → 挖词迭代 → 止损。返回 (池, 轮次统计, 止损原因)。"""
        terms = [q.strip() for q in queries if q.strip()][: self.config.max_queries]
        all_terms = list(terms)
        pool: dict[str, RepoRecord] = {}
        rounds: list[dict] = []
        stop_reason = "轮次用尽"

        for round_index in range(self.config.mine_rounds + 1):
            results = self.run_round(terms)
            batch = self.merge(results)
            new_names = set(batch) - set(pool)
            for name, record in batch.items():
                existing = pool.get(name)
                if existing is None:
                    pool[name] = record
                else:
                    for channel in record.channels:
                        if channel not in existing.channels:
                            existing.channels.append(channel)
                    for term in record.matched_queries:
                        if term not in existing.matched_queries:
                            existing.matched_queries.append(term)
            rounds.append({
                "round": round_index + 1,
                "queries": list(terms),
                "new_repos": len(new_names),
                "pool_size": len(pool),
            })

            if round_index > 0 and len(new_names) < self.config.new_keep_ratio * max(1, len(pool)):
                stop_reason = f"第{round_index + 1}轮新发现占比过低（止损）"
                break

            if round_index == self.config.mine_rounds:
                break

            exclude = {t.replace("topic:", "") for t in all_terms}
            mined = mine_topics(list(pool.values()), exclude)
            next_terms = [f"topic:{topic}" for topic, _count in mined]
            if not next_terms:
                stop_reason = "没有挖出新搜索词"
                break
            terms = next_terms[: self.config.max_queries]
            all_terms.extend(terms)
            time.sleep(2)  # search API 30 req/min：一轮 = 词数×4 个请求，缓一口气

        return pool, rounds, stop_reason
