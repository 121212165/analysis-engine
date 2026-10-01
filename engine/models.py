"""RepoRecord: 统一数据模型。search 阶段填基础+溯源字段，enrich 阶段补信号原料，score 阶段补分数。"""
from dataclasses import asdict, dataclass, field


@dataclass
class RepoRecord:
    full_name: str
    stars: int = 0
    forks: int = 0
    language: str | None = None
    topics: list[str] = field(default_factory=list)
    description: str | None = None
    updated_at: str | None = None
    pushed_at: str | None = None
    # 溯源
    channels: list[str] = field(default_factory=list)
    matched_queries: list[str] = field(default_factory=list)
    # 富化字段
    license_spdx: str | None = None
    open_issues: int | None = None
    closed_issues_90d: int | None = None
    latest_release_at: str | None = None
    contributors: int | None = None
    commits_90d: int | None = None
    readme_full: str | None = None
    readme_len: int | None = None
    # 分数（可溯源：evidence 里记录每个信号的原始输入）
    relevance: float | None = None
    quality: float | None = None
    overall: float | None = None
    signals: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)
