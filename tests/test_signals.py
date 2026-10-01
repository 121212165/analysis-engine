import sys
import datetime
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.models import RepoRecord
from engine.signals import activity, maintenance, community, adoption, license_signal, compute_all

NOW = datetime.datetime(2026, 10, 1, tzinfo=datetime.timezone.utc)


def record(**over) -> RepoRecord:
    base = dict(full_name="a/b", stars=100, forks=20, pushed_at="2026-09-25T00:00:00Z")
    base.update(over)
    return RepoRecord(**base)


class TestSignals(unittest.TestCase):
    def test_activity_push_decay(self):
        # 6 天前 push → exp(-6/180) ≈ 0.967
        score, evidence = activity(record(pushed_at="2026-09-25T00:00:00Z"), NOW)
        self.assertAlmostEqual(score, 0.9672, places=3)
        self.assertEqual(evidence["pushed_days_ago"], 6.0)

    def test_activity_without_commits_uses_push_only(self):
        score, evidence = activity(record(pushed_at="2020-01-01T00:00:00Z"), NOW)
        self.assertLess(score, 0.05)
        self.assertIsNone(evidence["commits_90d"])

    def test_activity_with_commits_blends(self):
        record_obj = record(pushed_at="2026-09-25T00:00:00Z", commits_90d=300)
        score, _ = activity(record_obj, NOW)
        self.assertGreater(score, 0.97)  # 两项都近满分

    def test_maintenance_close_ratio_and_release(self):
        record_obj = record(open_issues=10, closed_issues_90d=90, latest_release_at="2026-09-20T00:00:00Z")
        score, evidence = maintenance(record_obj, NOW)
        # ratio=0.9 → 0.63 + release≈0.97×0.3≈0.29 → ≈0.92
        self.assertGreater(score, 0.88)
        self.assertEqual(evidence["issue_close_ratio"], 0.9)

    def test_maintenance_no_data_is_neutral(self):
        score, _ = maintenance(record(open_issues=0, closed_issues_90d=0), NOW)
        self.assertGreater(score, 0.3)  # 无数据给中性分，不冤枉小项目

    def test_community_log_norm(self):
        big, _ = community(record(stars=50000, forks=10000, contributors=300))
        small, _ = community(record(stars=50, forks=5, contributors=1))
        self.assertGreater(big, 0.99)
        self.assertLess(small, 0.30)  # 50★ 属于弱社区，但不是零分

    def test_adoption_is_pool_relative(self):
        pool = [record(stars=s) for s in (10, 100, 1000)]
        low, _ = adoption(record(stars=5), pool)
        high, _ = adoption(record(stars=2000), pool)
        self.assertEqual(low, 0.0)
        self.assertEqual(high, 1.0)

    def test_license_osi_mapping(self):
        self.assertEqual(license_signal(record(license_spdx="MIT"))[0], 1.0)
        self.assertEqual(license_signal(record(license_spdx="WTFPL"))[0], 0.7)
        self.assertEqual(license_signal(record(license_spdx=None))[0], 0.3)

    def test_compute_all_writes_record(self):
        record_obj = record()
        signals = compute_all(record_obj, [record_obj], NOW)
        self.assertEqual(set(signals), {"activity", "maintenance", "community", "adoption", "license"})
        self.assertEqual(record_obj.signals, signals)
        self.assertIn("pushed_days_ago", record_obj.evidence["activity"])


if __name__ == "__main__":
    unittest.main()
