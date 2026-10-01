"""赛道聚类：topics 共现 → union-find 分组 → 每仓归入其主 topic 所在赛道。

确定性可复现（无随机、无 LLM）：两个 topic 在同一仓库共现 ≥2 次且共现率
≥ cooccur_ratio（相对较小者的仓库覆盖数）则合并。仓库按"命中池内最多的
topic 组"归簇；无 topics 的归「其他」。"""
from .config import NOISE_TOPICS


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, item: str) -> str:
        self.parent.setdefault(item, item)
        while self.parent[item] != item:
            self.parent[item] = self.parent[self.parent[item]]
            item = self.parent[item]
        return item

    def union(self, a: str, b: str) -> None:
        root_a, root_b = self.find(a), self.find(b)
        if root_a != root_b:
            self.parent[root_b] = root_a


def build_clusters(records: list, cooccur_min: int = 2, cooccur_ratio: float = 0.5, precise_only: bool = True) -> list[dict]:
    """返回 [{name, topics, repos, stars_total}]，按仓库数降序。

    precise_only=True 时只用 phrase/topic 通道命中的仓——readme 正文碰巧含词的
    巨库（JavaGuide 类）会把赛道图搅成星海，实测必须滤。"""
    if precise_only:
        records = [r for r in records if any(c in ("phrase", "topic") for c in r.channels)]
    topic_repos: dict[str, set[str]] = {}
    repo_topics: dict[str, list[str]] = {}
    stars = {record.full_name: record.stars for record in records}
    for record in records:
        clean = [t for t in record.topics if t and t not in NOISE_TOPICS]
        repo_topics[record.full_name] = clean
        for topic in clean:
            topic_repos.setdefault(topic, set()).add(record.full_name)

    uf = _UnionFind()
    names = list(topic_repos)
    for i, topic_a in enumerate(names):
        for topic_b in names[i + 1:]:
            shared = topic_repos[topic_a] & topic_repos[topic_b]
            if len(shared) >= cooccur_min and len(shared) / min(len(topic_repos[topic_a]), len(topic_repos[topic_b])) >= cooccur_ratio:
                uf.union(topic_a, topic_b)

    # topic → 簇
    groups: dict[str, list[str]] = {}
    for topic in names:
        groups.setdefault(uf.find(topic), []).append(topic)

    # 仓库归簇：看它的 topics 落进哪个簇最多
    cluster_repos: dict[str, list[str]] = {}
    for full_name, clean in repo_topics.items():
        if not clean:
            cluster_repos.setdefault("其他", []).append(full_name)
            continue
        votes: dict[str, int] = {}
        for topic in clean:
            votes[uf.find(topic)] = votes.get(uf.find(topic), 0) + 1
        best = max(votes.items(), key=lambda pair: (pair[1], pair[0]))[0]
        cluster_repos.setdefault(best, []).append(full_name)

    clusters = []
    for root, members in cluster_repos.items():
        topics = sorted(groups.get(root, []), key=lambda t: -len(topic_repos[t]))
        clusters.append({
            "name": topics[0] if topics else "其他",
            "topics": topics,
            "repos": sorted(members, key=lambda r: -stars[r]),
            "stars_total": sum(stars[r] for r in members),
        })
    clusters.sort(key=lambda c: (-len(c["repos"]), -c["stars_total"]))
    return clusters


def render_clusters(clusters: list[dict], top: int = 8) -> str:
    lines = ["| 赛道 | 仓库数 | 总星 | 代表仓库 |", "|---|---|---|---|"]
    for cluster in clusters[:top]:
        top_repo = cluster["repos"][0] if cluster["repos"] else "-"
        lines.append(f"| {cluster['name']} | {len(cluster['repos'])} | ⭐{cluster['stars_total']} | {top_repo} |")
    return "\n".join(lines)
