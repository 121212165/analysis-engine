"""竞品对比矩阵：Top N 候选 × 关键维度，一张表看全格局。"""
import datetime


def _fmt_days(iso: str | None) -> str:
    if not iso:
        return "-"
    try:
        moment = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return "-"
    days = (datetime.datetime.now(datetime.timezone.utc) - moment).days
    return f"{days}天前"


def render_compare(records: list, top_n: int = 10) -> str:
    headers = ["仓库", "⭐", "综合", "活跃", "维护", "社区", "采用", "License", "关90d/开", "最近release", "contrib", "push"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for record in records[:top_n]:
        signals = record.signals
        closed = record.closed_issues_90d if record.closed_issues_90d is not None else "-"
        opened = record.open_issues if record.open_issues is not None else "-"
        lines.append("| " + " | ".join([
            record.full_name,
            str(record.stars),
            f"{record.overall:.2f}",
            f"{signals.get('activity', 0):.2f}",
            f"{signals.get('maintenance', 0):.2f}",
            f"{signals.get('community', 0):.2f}",
            f"{signals.get('adoption', 0):.2f}",
            record.license_spdx or "无",
            f"{closed}/{opened}",
            _fmt_days(record.latest_release_at),
            str(record.contributors if record.contributors is not None else "-"),
            _fmt_days(record.pushed_at),
        ]) + " |")
    lines.append("")
    lines.append("*信号定义：活跃=push衰减+90d提交；维护=issue处理率+release新鲜度；社区=star/fork/贡献者对数归一；采用=池内star分位。富化未覆盖的仓显示 `-`，其质量分按中性值计。*")
    return "\n".join(lines)
