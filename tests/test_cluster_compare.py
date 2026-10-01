import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.cluster import build_clusters, render_clusters
from engine.compare import render_compare
from engine.models import RepoRecord


def record(full_name, stars, topics, **over) -> RepoRecord:
    base = dict(full_name=full_name, stars=stars, topics=topics, channels=["phrase"],
                signals={"activity": 0.5, "maintenance": 0.5, "community": 0.5, "adoption": 0.5, "license": 0.5},
                overall=0.6, relevance=0.7, quality=0.5, pushed_at="2026-09-20T00:00:00Z")
    base.update(over)
    return RepoRecord(**base)


class TestCluster(unittest.TestCase):
    def test_cooccurring_topics_merge_into_one_cluster(self):
        records = [
            record("a/one", 100, ["novel-writing", "ai-writing"]),
            record("b/two", 80, ["novel-writing", "ai-writing"]),
            record("c/three", 60, ["novel-writing"]),
        ]
        clusters = build_clusters(records)
        self.assertEqual(len([c for c in clusters if c["name"] != "其他"]), 1)
        merged = [c for c in clusters if c["name"] != "其他"][0]
        self.assertEqual(set(merged["repos"]), {"a/one", "b/two", "c/three"})
        self.assertEqual(merged["stars_total"], 240)
        self.assertEqual(merged["name"], "novel-writing")  # 代表 topic = 覆盖仓库最多者

    def test_weakly_related_topics_stay_apart(self):
        records = [
            record("a/one", 100, ["webnovel"]),
            record("b/two", 80, ["cli-tools"]),
        ]
        clusters = build_clusters(records)
        names = {c["name"] for c in clusters}
        self.assertEqual(names, {"webnovel", "cli-tools"})

    def test_repos_without_topics_land_in_other(self):
        clusters = build_clusters([record("x/y", 10, [])])
        self.assertEqual(clusters[0]["name"], "其他")

    def test_noise_topics_ignored(self):
        clusters = build_clusters([
            record("a/one", 100, ["ai", "llm", "webnovel"]),
            record("b/two", 80, ["ai", "webnovel"]),
        ])
        # ai/llm 是噪声，只有 webnovel 参与聚类
        self.assertEqual([c["name"] for c in clusters], ["webnovel"])

    def test_precise_only_filters_readme_coincidence(self):
        readme_only = record("mega/guide", 99999, ["cpp"], channels=["readme"])
        precise = [record("a/one", 100, ["webnovel"]), record("b/two", 80, ["webnovel"])]
        clusters = build_clusters(precise + [readme_only], precise_only=True)
        all_repos = {r for c in clusters for r in c["repos"]}
        self.assertNotIn("mega/guide", all_repos)  # 正文通道巨库不进赛道图
        clusters_all = build_clusters(precise + [readme_only], precise_only=False)
        self.assertIn("mega/guide", {r for c in clusters_all for r in c["repos"]})

    def test_render_is_markdown_table(self):
        text = render_clusters(build_clusters([
            record("a/one", 100, ["novel-writing"]), record("b/two", 80, ["novel-writing"]),
        ]))
        self.assertIn("| 赛道 | 仓库数 | 总星 | 代表仓库 |", text)
        self.assertIn("novel-writing", text)


class TestCompare(unittest.TestCase):
    def test_matrix_rows_and_columns(self):
        records = [
            record("a/one", 100, [], license_spdx="MIT", closed_issues_90d=9, open_issues=1,
                   latest_release_at="2026-09-01T00:00:00Z", contributors=3),
            record("b/two", 200, [], license_spdx=None),
        ]
        text = render_compare(records, top_n=2)
        self.assertIn("| 仓库 | ⭐ | 综合 | 活跃 | 维护 | 社区 | 采用 | License |", text)
        self.assertIn("a/one", text)
        self.assertIn("MIT", text)
        self.assertIn("9/1", text)
        self.assertIn("b/two", text)
        self.assertIn("无", text)  # 未富化/无 license 显示

    def test_top_n_truncates(self):
        records = [record(f"r/{i}", i, []) for i in range(5)]
        text = render_compare(sorted(records, key=lambda r: -r.stars), top_n=2)
        self.assertIn("r/4", text)
        self.assertNotIn("r/2", text)


if __name__ == "__main__":
    unittest.main()
