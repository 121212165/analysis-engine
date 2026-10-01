import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.config import build_config
from engine.models import RepoRecord
from engine.score import relevance_of, quality_of, score_pool, ranked


def record(channels, matched, stars=100, **over) -> RepoRecord:
    base = dict(full_name="a/b", channels=channels, matched_queries=matched, stars=stars)
    base.update(over)
    return RepoRecord(**base)


class TestScore(unittest.TestCase):
    def test_relevance_channel_dominance(self):
        # 短语命中 1 词 > 泛搜命中 3 词（通道权重主导）
        phrase = relevance_of(record(["phrase"], ["写小说"]), 3)
        loose = relevance_of(record(["loose"], ["写小说", "网文", "AI novel"]), 3)
        self.assertGreater(phrase, loose)
        self.assertAlmostEqual(phrase, 0.7 * 1.0 + 0.3 * (1 / 3), places=3)

    def test_multi_channel_multi_term_beats_single(self):
        both = relevance_of(record(["phrase", "readme"], ["写小说", "网文"]), 2)
        single = relevance_of(record(["phrase"], ["写小说"]), 2)
        self.assertGreater(both, single)

    def test_quality_weighted_mean(self):
        config = build_config(scenario="picking")
        signals = {"activity": 0.5, "maintenance": 1.0, "community": 0.0, "adoption": 0.5, "license": 1.0}
        score = quality_of(signals, config.quality_weights)
        # 选型场景 maintenance+license 权重最高 → 明显高于均值 0.6
        self.assertGreater(score, 0.65)

    def test_score_pool_traceable(self):
        config = build_config(scenario="map")
        pool = {"a/b": record(["phrase"], ["写小说"], stars=100),
                "c/d": record(["topic"], ["topic:x"], stars=1000)}
        score_pool(pool, config, all_query_count=1)
        for item in pool.values():
            self.assertAlmostEqual(item.overall, 0.4 * item.relevance + 0.6 * item.quality, places=3)
            self.assertIn("stars", item.evidence["community"])  # 证据链落盘

    def test_ranked_overall_first_star_tiebreak(self):
        config = build_config(scenario="map")
        pool = {
            "low/high": record(["readme"], ["x"], stars=90000, full_name="low/high"),
            "small/precise": record(["phrase"], ["x"], stars=10, full_name="small/precise"),
        }
        score_pool(pool, config, all_query_count=1)
        self.assertEqual(ranked(pool)[0].full_name, "small/precise")  # 通道精准度压过 9 万 star
        # 并列时 star 降序
        pool2 = {
            "p/q": record(["phrase"], ["x"], stars=50, full_name="p/q"),
            "r/s": record(["phrase"], ["x"], stars=500, full_name="r/s"),
        }
        score_pool(pool2, config, all_query_count=1)
        self.assertEqual(ranked(pool2)[0].full_name, "r/s")


if __name__ == "__main__":
    unittest.main()
