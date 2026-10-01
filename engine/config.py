"""Central config: channel weights, scenario profiles, thresholds.

两个场景预设（--scenario 选择）：
- map     赛道地图：这个赛道有哪些玩家、格局如何 → 重活跃度+社区
- picking 选型推荐：哪个项目适合我拿来用 → 重维护性+license
"""
from dataclasses import dataclass, field

# 通道精准度权重（与 dsh-plugin-deep-scan 口径一致）
CHANNEL_WEIGHTS = {"phrase": 1.0, "loose": 0.7, "readme": 0.5, "topic": 0.3}
CHANNEL_PRIORITY = {"phrase": 0, "loose": 1, "readme": 2, "topic": 3}

NOISE_TOPICS = {
    "ai", "llm", "llms", "gpt", "chatgpt", "openai", "anthropic", "claude", "gemini",
    "python", "typescript", "javascript", "nodejs", "rust", "go", "java",
    "machine-learning", "deep-learning", "nlp", "agent", "agents", "ai-agents",
    "open-source", "awesome", "awesome-list", "tutorial", "cli", "api", "sdk",
    "windows", "linux", "macos", "android", "ios", "web", "react", "vue",
    "self-hosted", "docker", "productivity", "automation",
}

OSI_LICENSES = {
    "MIT", "Apache-2.0", "BSD-2-Clause", "BSD-3-Clause", "GPL-2.0", "GPL-3.0",
    "LGPL-2.1", "LGPL-3.0", "MPL-2.0", "AGPL-3.0", "Unlicense", "CC0-1.0",
    "ISC", "EPL-2.0", "Artistic-2.0", "Zlib",
}


@dataclass
class Config:
    scenario: str = "map"
    per_channel: int = 30
    mine_rounds: int = 2            # 首轮之后自动挖词迭代的轮数
    max_queries: int = 6            # 每轮搜索词上限
    new_keep_ratio: float = 0.30    # 一轮新发现占比低于此值 → 止损（SKILL.md 口径）
    enrich_limit: int = 50          # 最多富化多少仓（配额保护）
    concurrency: int = 2            # 富化并发（4 会触发 GitHub 次级滥用检测，实测）
    top_n: int = 10
    cache_ttl_hours: float = 12.0
    commits_90d: bool = False       # 默认关：commit 列表对活跃仓库会翻页烧配额
    quality_weights: dict = field(default_factory=dict)
    relevance_mix: tuple = (0.7, 0.3)   # (max通道权重, 命中词覆盖度)
    overall_mix: tuple = (0.4, 0.6)     # (relevance, quality)


# 质量信号内部权重（activity/maintenance/community/adoption/license）
PROFILES = {
    "map": {
        "quality_weights": {
            "activity": 0.30, "maintenance": 0.10, "community": 0.30,
            "adoption": 0.20, "license": 0.10,
        },
    },
    "picking": {
        "quality_weights": {
            "activity": 0.25, "maintenance": 0.30, "community": 0.10,
            "adoption": 0.15, "license": 0.20,
        },
    },
}


def build_config(**overrides) -> Config:
    scenario = overrides.pop("scenario", "map")
    cfg = Config(scenario=scenario, **overrides)
    preset = PROFILES.get(scenario, PROFILES["map"])
    cfg.quality_weights = dict(preset["quality_weights"])
    return cfg
