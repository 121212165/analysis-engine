"""5 个质量信号，纯函数，每个返回 (0..1, evidence_dict)——分数可拆到原始字段。"""
import datetime
import math


def _days_since(iso: str | None, now: datetime.datetime | None = None) -> float | None:
    if not iso:
        return None
    try:
        moment = datetime.datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        return None
    now = now or datetime.datetime.now(datetime.timezone.utc)
    return max(0.0, (now - moment).total_seconds() / 86400)


def _log_norm(value: float, ceiling: float) -> float:
    """对数归一到 0..1：value=ceiling → 1.0，0 → 0。"""
    if value <= 0:
        return 0.0
    return min(1.0, math.log1p(value) / math.log1p(ceiling))


def activity(record, now: datetime.datetime | None = None) -> tuple[float, dict]:
    """活跃度 = push 衰减 0.5 + 90天 commit 归一 0.5（commits 缺失时 push 权重 1.0）。"""
    days = _days_since(record.pushed_at, now)
    push_score = math.exp(-days / 180) if days is not None else 0.0
    if record.commits_90d is None:
        return round(push_score, 4), {"pushed_days_ago": days, "commits_90d": None, "note": "commits 信号未启用，push 独扛"}
    commit_score = _log_norm(record.commits_90d, 300)
    return round(0.5 * push_score + 0.5 * commit_score, 4), {
        "pushed_days_ago": days, "push_score": round(push_score, 4), "commits_90d": record.commits_90d,
    }


def maintenance(record, now: datetime.datetime | None = None) -> tuple[float, dict]:
    """维护性 = 90天 issue 处理率 0.7 + 最近 release 衰减 0.3。"""
    closed = record.closed_issues_90d or 0
    open_count = record.open_issues or 0
    total = closed + open_count
    ratio = closed / total if total > 0 else 0.5
    release_days = _days_since(record.latest_release_at, now)
    release_score = math.exp(-release_days / 365) if release_days is not None else 0.3
    return round(0.7 * ratio + 0.3 * release_score, 4), {
        "closed_issues_90d": closed, "open_issues": open_count, "issue_close_ratio": round(ratio, 4),
        "release_days_ago": release_days,
    }


def community(record) -> tuple[float, dict]:
    """社区 = stars/forks/contributors 对数归一加权。"""
    stars = _log_norm(record.stars, 50000)
    forks = _log_norm(record.forks, 10000)
    contributors = _log_norm(record.contributors or 0, 300)
    return round(0.5 * stars + 0.3 * forks + 0.2 * contributors, 4), {
        "stars": record.stars, "forks": record.forks, "contributors": record.contributors,
    }


def adoption(record, pool: list) -> tuple[float, dict]:
    """采用度 = star 在候选池内的分位数（池内相对比较，避免跨赛道失真）。"""
    if not pool:
        return 0.5, {"pool_size": 0, "percentile": None}
    stars = sorted(other.stars for other in pool)
    below = sum(1 for value in stars if value < record.stars)
    percentile = below / len(stars)
    return round(percentile, 4), {"pool_size": len(pool), "percentile": round(percentile, 4)}


def license_signal(record) -> tuple[float, dict]:
    """合规：OSI 认可=1.0，有 license=0.7，无=0.3。"""
    from .config import OSI_LICENSES

    spdx = record.license_spdx
    if spdx in OSI_LICENSES:
        score = 1.0
    elif spdx:
        score = 0.7
    else:
        score = 0.3
    return score, {"license_spdx": spdx}


ALL_SIGNALS = ("activity", "maintenance", "community", "adoption", "license")


def compute_all(record, pool: list, now: datetime.datetime | None = None) -> dict:
    signals, evidence = {}, {}
    signals["activity"], evidence["activity"] = activity(record, now)
    signals["maintenance"], evidence["maintenance"] = maintenance(record, now)
    signals["community"], evidence["community"] = community(record)
    signals["adoption"], evidence["adoption"] = adoption(record, pool)
    signals["license"], evidence["license"] = license_signal(record)
    record.signals = signals
    record.evidence = evidence
    return signals
