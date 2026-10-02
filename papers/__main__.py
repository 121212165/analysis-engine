"""`python -m papers --corpus <目录>` → output/<run>/report.md + data.json"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from papers.facts import extract
from papers.models import load_corpus
from papers.report import save_output


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m papers",
                                 description="中文文献跨文献对照（只吃 corpus/*.md）")
    ap.add_argument("--corpus", required=True, help="规范化 .md 所在目录（带 front-matter）")
    ap.add_argument("--out", default="", help="输出目录，默认 output/corpus-<日期>")
    ap.add_argument("--top", type=int, default=12, help="张力点最多列几个")
    args = ap.parse_args(argv)

    corpus = Path(args.corpus)
    if not corpus.is_dir():
        print(f"[papers] 不是目录：{corpus}", file=sys.stderr)
        return 2
    papers = [extract(p) for p in load_corpus(corpus)]
    if not papers:
        print(f"[papers] {corpus} 下没有可解析的文献（需要带 front-matter 的 .md）", file=sys.stderr)
        return 2
    import datetime
    out = args.out or f"output/corpus-{datetime.date.today():%Y%m%d}"
    paths = save_output(out, papers, str(corpus))
    tot_chars = sum(len(p) for pp in papers for p in pp.paragraphs)
    print(f"[papers] {len(papers)} 篇 / {tot_chars:,} 字 → {paths['report']}")
    print(f"[papers] 数据版：{paths['data']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
