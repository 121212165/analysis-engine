"""评分层：relevance（通道+命中词）× quality（信号加权）→ overall。权重集中 config。"""
from .config import CHANNEL_PRIORITY, CHANNEL_WEIGHTS
from .signals import compute_all


def relevance_of(record, all_query_count: int, relevance_mix: tuple = (0.7, 0.3)) -> float:
    channel_max, coverage = relevance_mix
    best = max((CHANNEL_WEIGHTS.get(channel, 0.0) for channel in record.channels), default=0.0)
    overlap = min(1.0, len(record.matched_queries) / max(1, all_query_count))
    return round(channel_max * best + coverage * overlap, 4)


def quality_of(signals: dict, weights: dict) -> float:
    total_weight = sum(weights.values()) or 1.0
    return round(sum(signals[name] * weight for name, weight in weights.items()) / total_weight, 4)


def score_pool(pool: dict[str, "RepoRecord"], config, all_query_count: int, now=None) -> None:
    """就地给每个 RepoRecord 写 relevance/quality/overall + signals/evidence。"""
    records = list(pool.values())
    for record in records:
        compute_all(record, records, now)
        record.relevance = relevance_of(record, all_query_count, config.relevance_mix)
        record.quality = quality_of(record.signals, config.quality_weights)
        rel_w, qual_w = config.overall_mix
        record.overall = round(rel_w * record.relevance + qual_w * record.quality, 4)


def ranked(pool: dict[str, "RepoRecord"]):
    """主排序：综合分降序；并列 star 降序。"""
    return sorted(pool.values(), key=lambda record: (-record.overall, -record.stars))
