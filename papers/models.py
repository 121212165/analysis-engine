"""papers.models：文献记录（公开侧）。

⚠️ 这个包**不允许出现任何取数细节**——站点域名、登录链、`v=` 令牌一概不进。
它只吃两份文件契约：records.json（元数据）与 corpus/*.md（规范化正文）。
"""
from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path


@dataclass
class Paper:
    key: str = ""
    title: str = ""
    authors: list[str] = field(default_factory=list)
    source: str = ""
    year: str = ""
    pubdate: str = ""
    db: str = ""
    pages: int = 0
    verified: bool = False
    status: str = ""
    paragraphs: list[str] = field(default_factory=list)
    # 分析层填
    facts: dict = field(default_factory=dict)
    evidence: dict = field(default_factory=dict)

    def label(self) -> str:
        return f"{self.year} {self.title[:38]}"

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Paper":
        known = set(cls.__dataclass_fields__)
        return cls(**{k: v for k, v in d.items() if k in known})


_FM = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", re.S)


def parse_front_matter(text: str) -> tuple[dict, list[str]]:
    if not text.startswith("---"):
        return {}, [text.strip()]
    m = _FM.match(text)
    if not m:
        return {}, [text.strip()]
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip().strip('"').strip("'")
    paras = [p.strip() for p in m.group(2).split("\n\n") if p.strip()]
    return meta, paras


def load_corpus(corpus_dir: str | Path) -> list[Paper]:
    """从 corpus/*.md 读文献。缺 front-matter 的文件会被跳过并记名，不静默吞掉。"""
    out, skipped = [], []
    for f in sorted(Path(corpus_dir).glob("*.md")):
        meta, paras = parse_front_matter(f.read_text(encoding="utf-8"))
        if not meta.get("title") or not paras:
            skipped.append(f.name)
            continue
        authors = [a.strip() for a in re.split(r"[,;，、]\s*|\s+", meta.get("authors", "")) if a.strip()]
        out.append(Paper(
            key=meta.get("key") or f.stem.split("_")[0],
            title=meta["title"], authors=authors, source=meta.get("source", ""),
            year=meta.get("year", ""), pubdate=meta.get("pubdate", ""),
            db=meta.get("db", ""), pages=int(meta.get("pages_pdf") or 0),
            verified=meta.get("verified", "").lower() == "true",
            status=meta.get("status", ""), paragraphs=paras,
        ))
    if skipped:
        print(f"[papers] 跳过 {len(skipped)} 个无 front-matter 的文件：{skipped[:5]}", flush=True)
    return out


def load_records(path: str | Path) -> list[dict]:
    """读 records.json，**剥掉 abs_url**（里面是易失令牌，不该进公开仓的分析层）。"""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows = data.get("records", data) if isinstance(data, dict) else data
    return [{k: v for k, v in r.items() if k != "abs_url"} for r in rows]
