import sys
import unittest
from pathlib import Path
from urllib.parse import urlparse, parse_qs

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.config import build_config
from engine.search import SearchEngine, search_channel, mine_topics


def item(full_name, stars, topics):
    return {"full_name": full_name, "stargazers_count": stars, "forks_count": 5,
            "topics": topics, "description": f"desc {full_name}", "pushed_at": "2026-09-01T00:00:00Z",
            "language": "Python", "updated_at": "2026-09-01T00:00:00Z"}


class FakeClient:
    """按 q 参数路由的假 GitHub：写小说 三通道全命中并埋 topic:writing 的种子。"""

    def __init__(self):
        self.urls = []

    def get_json(self, url):
        self.urls.append(url)
        q = parse_qs(urlparse(url).query)["q"][0]
        if q.startswith('"'):
            return {"items": [item("p/one", 100, ["writing", "novel"]), item("p/two", 50, ["writing"])]}
        if "in:readme" in q:
            return {"items": [item("r/only", 3000, ["ai"])]}
        if q.startswith("topic:writing"):
            return {"items": [item("p/one", 100, ["writing"]), item("n/new", 700, ["writing"])]}
        if q.startswith("写小说"):
            return {"items": [item("l/huge", 50000, [])]}
        return {"items": []}


class TestSearch(unittest.TestCase):
    def test_search_channel_builds_four_query_shapes(self):
        client = FakeClient()
        search_channel(client, "写小说", "phrase", 30, "language:Python")
        search_channel(client, "写小说", "readme", 30)
        search_channel(client, "writing", "topic", 30)
        queries = [parse_qs(urlparse(url).query)["q"][0] for url in client.urls]
        self.assertEqual(queries[0], '"写小说" language:Python')  # 限定符在引号外
        self.assertEqual(queries[1], "写小说 in:readme")
        self.assertEqual(queries[2], "topic:writing")

    def test_merge_dedup_with_channel_and_term_trace(self):
        engine = SearchEngine(FakeClient(), build_config())
        results = {
            ("phrase", "写小说"): [item("a/b", 100, [])],
            ("loose", "写小说"): [item("a/b", 100, []), item("c/d", 200, [])],
        }
        pool = engine.merge(results)
        merged = pool["a/b"]
        self.assertEqual(merged.channels, ["phrase", "loose"])
        self.assertEqual(merged.matched_queries, ["写小说"])

    def test_iterate_mines_topics_and_stops_when_dry(self):
        engine = SearchEngine(FakeClient(), build_config(mine_rounds=3, new_keep_ratio=0.30))
        pool, rounds, stop_reason = engine.run(["写小说"])
        # 第1轮 写小说（12请求）→ 挖出 topic:writing → 第2轮 → 第3轮无新词可挖或止损
        self.assertGreaterEqual(len(rounds), 2)
        self.assertEqual(rounds[0]["queries"], ["写小说"])
        self.assertEqual(rounds[1]["queries"], ["topic:writing"])
        self.assertIn("topic:writing", [q for stat in rounds for q in stat["queries"]])
        # 溯源完整：n/new 记录了赛道通道和挖出的词
        record_obj = pool.get("n/new")
        self.assertIsNotNone(record_obj)
        self.assertIn("topic", record_obj.channels)

    def test_mine_topics_excludes_used_and_noise(self):
        from engine.models import RepoRecord
        records = [
            RepoRecord(full_name="a/b", channels=["phrase"], topics=["writing", "ai", "llm"]),
            RepoRecord(full_name="c/d", channels=["phrase"], topics=["writing", "novel-writing"]),
            RepoRecord(full_name="e/f", channels=["phrase"], topics=["novel-writing"]),
        ]
        mined = mine_topics(records, exclude={"novel-writing"})
        self.assertEqual([topic for topic, _ in mined], ["writing"])  # novel-writing 被排除，ai/llm 是噪声


if __name__ == "__main__":
    unittest.main()
