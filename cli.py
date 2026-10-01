#!/usr/bin/env python3
"""CLI 入口：python cli.py "写小说|网文|AI novel" [--scenario map|picking] [--top 10]"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from engine import build_config, load_token, RequestCache, GithubClient, SearchEngine, enrich_all, score_pool, ranked, save_output
from engine.cluster import build_clusters
from engine.compare import render_compare


def main() -> None:
    parser = argparse.ArgumentParser(description="GitHub 赛道分析引擎")
    parser.add_argument("queries", help="搜索词，| 分隔，2-4 个变体")
    parser.add_argument("--scenario", choices=["map", "picking"], default="map", help="map=赛道地图（默认），picking=选型推荐")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--enrich-limit", type=int, default=50)
    parser.add_argument("--min-stars", type=int, default=0)
    parser.add_argument("--language", default="")
    parser.add_argument("--cache", default="output/cache.sqlite3")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    queries = [part.strip() for part in args.queries.replace("；", "|").replace(";", "|").split("|") if part.strip()]
    if not queries:
        parser.error("至少要一个搜索词")

    qualifiers = ""
    if args.language:
        qualifiers += f" language:{args.language}"
    if args.min_stars:
        qualifiers += f" stars:>={args.min_stars}"

    config = build_config(scenario=args.scenario, top_n=args.top, enrich_limit=args.enrich_limit)
    token = load_token()
    cache = None if args.no_cache else RequestCache(args.cache)
    client = GithubClient(token, cache)
    engine = SearchEngine(client, config, qualifiers=qualifiers)

    pool, rounds, stop_reason = engine.run(queries)

    print(f"候选池 {len(pool)} 仓，开始富化（上限 {config.enrich_limit}，并发 {config.concurrency}）...", file=sys.stderr)
    all_query_count = len({query for stat in rounds for query in stat["queries"]})
    # 两遍评分：先按相关性预排序决定富化谁，富化完再全量终评（否则富化的不是最相关的仓）
    score_pool(pool, config, all_query_count=all_query_count)
    pre_ranked = sorted(pool.values(), key=lambda record: (-record.relevance, -record.stars))
    enrich_all(client, pre_ranked, token, config)
    score_pool(pool, config, all_query_count=all_query_count)

    ranked_records = ranked(pool)
    clusters = build_clusters(ranked_records)
    compare_md = render_compare(ranked_records, top_n=config.top_n)
    stats = {"calls": client.calls, "limited_wait": client.limited_wait}
    default_dir = f"output/{args.queries[:36].replace('|', '_').replace('/', '_').strip()}"
    out_dir = Path(args.output) if args.output else Path(default_dir)
    save_output(out_dir, queries, ranked_records, rounds, config, stop_reason, stats,
                clusters=clusters, compare_md=compare_md)

    print(f"完成：{out_dir / 'report.md'}", file=sys.stderr)
    print(f"API 真实调用 {client.calls} 次 | 限流等待 {client.limited_wait:.0f}s | 缓存 {cache.stats() if cache else '未启用'}", file=sys.stderr)


if __name__ == "__main__":
    main()
