"""analysis-engine: GitHub 赛道「搜索 → 富化 → 评分 → 报告」引擎（stdlib only）。"""
from .config import Config, build_config
from .models import RepoRecord
from .cache import RequestCache
from .http import GithubClient, load_token
from .search import SearchEngine, mine_topics
from .enrich import enrich_all
from .signals import compute_all
from .score import score_pool, ranked
from .report import save_output, render_report
from .cluster import build_clusters, render_clusters
from .compare import render_compare

__all__ = [
    "Config", "build_config", "RepoRecord", "RequestCache", "GithubClient", "load_token",
    "SearchEngine", "mine_topics", "enrich_all", "compute_all", "score_pool", "ranked",
    "save_output", "render_report", "build_clusters", "render_clusters", "render_compare",
]
