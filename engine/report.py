"""交付层：中文 Markdown 报告 + data.json + meta.json，落 output/<run_id>/。"""
import json
import datetime
from pathlib import Path

from .cluster import render_clusters

CHANNEL_LABEL = {"phrase": "短语", "loose": "泛搜", "readme": "正文", "topic": "赛道"}


def render_report(queries: list[str], records: list, rounds: list[dict], config, stop_reason: str, client_stats: dict, cluster_lines: str = "") -> str:
    lines: list[str] = []
    lines.append(f"# 赛道分析报告：{' | '.join(queries)}")
    lines.append("")
    scenario_name = "赛道地图" if config.scenario == "map" else "选型推荐"
    enriched = len([r for r in records if r.contributors is not None or r.open_issues is not None])
    lines.append(f"场景：{scenario_name} | 候选池 {len(records)} 仓（富化 {enriched} 仓）| 生成时间 {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    lines.append("")
    lines.append("## 迭代过程")
    lines.append("")
    for stat in rounds:
        lines.append(f"- 第{stat['round']}轮 [{(' | '.join(stat['queries']))}] 新发现 {stat['new_repos']} → 池 {stat['pool_size']}")
    lines.append(f"- 链路结束：{stop_reason}")
    lines.append("")

    lines.append(f"## Top {min(config.top_n, len(records))}")
    lines.append("")
    for index, record in enumerate(records[: config.top_n], 1):
        channels = " + ".join(CHANNEL_LABEL.get(c, c) for c in record.channels)
        lines.append(f"### {index}. {record.full_name}  ⭐{record.stars} | 综合 {record.overall:.3f}（相关 {record.relevance:.2f} × 质量 {record.quality:.2f}）")
        lines.append(f"- 简介: {record.description or '（无）'}")
        lines.append(f"- 通道: {channels} | 命中词: {', '.join(record.matched_queries)}")
        sig = " ".join(f"{name}={record.signals.get(name, 0):.2f}" for name in ("activity", "maintenance", "community", "adoption", "license"))
        lines.append(f"- 信号: {sig}")
        license_note = record.license_spdx or "无 license"
        maint = f"closed90d={record.closed_issues_90d}/open={record.open_issues}"
        release = f"最近release={record.latest_release_at[:10] if record.latest_release_at else '无'}"
        lines.append(f"- 事实: {license_note} | {maint} | {release} | contributors={record.contributors}")
        if record.evidence.get("activity", {}).get("pushed_days_ago") is not None:
            lines.append(f"- 证据: 最近 push {record.evidence['activity']['pushed_days_ago']:.0f} 天前")
        lines.append("")

    if cluster_lines:
        lines.append("## 赛道地图（topics 共现聚类）")
        lines.append("")
        lines.append(cluster_lines)
        lines.append("")

    lines.append("## 完整候选池（未深挖部分）")
    lines.append("")
    for record in records[config.top_n:]:
        channels = CHANNEL_LABEL.get(record.channels[0], record.channels[0])
        lines.append(f"- {record.full_name} ⭐{record.stars} [{channels}|{','.join(record.matched_queries)}] — {(record.description or '')[:70]}")
    lines.append("")
    lines.append(f"---\n*API 真实调用 {client_stats.get('calls', 0)} 次（缓存命中不计）· 限流等待 {client_stats.get('limited_wait', 0):.0f}s · 权重场景 {config.scenario}*")
    return "\n".join(lines)


def save_output(out_dir: Path, queries: list[str], records: list, rounds: list[dict], config, stop_reason: str, client_stats: dict, clusters: list[dict] | None = None, compare_md: str = "") -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    meta = {
        "queries": queries,
        "scenario": config.scenario,
        "generated_at": datetime.datetime.now().isoformat(),
        "rounds": rounds,
        "stop_reason": stop_reason,
        "client": client_stats,
        "config": {
            "per_channel": config.per_channel, "mine_rounds": config.mine_rounds,
            "new_keep_ratio": config.new_keep_ratio, "enrich_limit": config.enrich_limit,
            "quality_weights": config.quality_weights,
        },
    }
    (out_dir / "meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "data.json").write_text(
        json.dumps([record.to_dict() for record in records], ensure_ascii=False, indent=2), encoding="utf-8")
    report = render_report(queries, records, rounds, config, stop_reason, client_stats,
                           cluster_lines=render_clusters(clusters) if clusters else "")
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    if clusters is not None:
        (out_dir / "cluster.json").write_text(
            json.dumps(clusters, ensure_ascii=False, indent=2), encoding="utf-8")
    if compare_md:
        (out_dir / "compare.md").write_text(compare_md, encoding="utf-8")
    return out_dir
