"""papers：中文文献的跨文献对照（stdlib only，零第三方依赖）。

与 GitHub 赛道那条链路完全平行——不复用 RepoRecord、不复用那 5 个 GitHub 信号，
因为论文的信号是「方法/年份/刊物/论断方向」，硬套只会产出假分数。

用法：`python -m papers --corpus <目录>`
"""
from .compare import method_matrix, overview, timeline, topic_tension
from .facts import (extract, extract_assertions, extract_methods, count_citations,
                    count_numbers, detect_sections, keywords)
from .models import Paper, load_corpus, load_records, parse_front_matter
from .report import render_report, save_output

__all__ = [
    "Paper", "count_citations", "count_numbers", "detect_sections", "extract",
    "extract_assertions", "extract_methods", "keywords", "load_corpus", "load_records",
    "method_matrix", "overview", "parse_front_matter", "render_report", "save_output",
    "timeline", "topic_tension",
]
