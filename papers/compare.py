"""papers.compare：跨文献对照。

最有价值的一件事是**找张力**：同一主题下方向相反的论断。
一份"综合"如果只是把每篇的摘要拼起来，那不如去读摘要。
"""
from __future__ import annotations

from collections import defaultdict

from .facts import STOP_GRAMS


def overview(papers: list) -> list[dict]:
    rows = []
    for p in sorted(papers, key=lambda x: (x.year, x.title), reverse=True):
        f = p.facts or {}
        rows.append({
            "year": p.year, "title": p.title, "source": p.source, "db": p.db,
            "pages": p.pages, "paras": f.get("paras", 0), "chars": f.get("chars", 0),
            "methods": "、".join(sorted(f.get("methods", {}).keys())),
            "numbers": f.get("numbers", 0),
            "assertions": len(f.get("assertions", [])),
            "citations": sum(f.get("citations", {}).values()),
            "key": p.key,
        })
    return rows


def method_matrix(papers: list) -> dict[str, list[str]]:
    """方法类 → 用了它的论文标题。看的是方法分布，不是单篇。"""
    out: dict[str, list[str]] = defaultdict(list)
    for p in papers:
        for group in (p.facts or {}).get("methods", {}):
            out[group].append(p.label())
    return {k: sorted(v) for k, v in sorted(out.items())}


# 只放**功能词/强度词**。别把「婚姻」「育儿」「子女」放进来——那是本领域的主题词，
# 滤掉就等于把要找的东西删了（我第一版就犯了这个错）。过泛的交给下面的 df 阈值处理。
GENERIC = {"影响", "可能", "显著", "研究", "问题", "社会", "关系", "作用", "因素",
           "程度", "认为", "发现", "显示", "表明", "分析", "数据", "结论", "本文",
           "中国", "个体", "过程", "机制", "视角", "理论", "学者", "结果", "方面",
           "同时", "其中", "以及", "相关", "主要", "重要"}


def topic_tension(papers: list, top_terms: int = 12) -> list[dict]:
    """同一高频字组下出现方向相反的论断 → 张力点。

    三条硬约束，都是上一版实测打脸后加的：
      1. 字组必须有区分度——在 GENERIC 表里、或**≥5 篇且篇篇都有**的一律当背景词滤掉
         （上一版「影响」「可能」「显著」占了大半版面）。
         注意不能用固定比例阈值：2 篇语料里"两篇共有"正是要找的信号，
         按比例会把它们全杀掉。
      2. 不做"没命中就随便挑三个字组"的兜底（上一版那个 fallback 会把论断挂到
         根本没出现的主题上，纯造假）；
      3. 必须区分**跨篇对立**与**单篇内部对立**：前者是文献分歧，后者是作者自己在
         权衡。上一版"正向 1 篇 / 负向 1 篇"的标签其实是同一篇，读起来像两篇打架。
    字组是滑动 2-gram（无分词器），只保证"同一个字组两边都出现"，不保证谈同一件事。
    """
    vocab = {p.key: {t for t in (p.facts or {}).get("keywords", [])
                     if t not in STOP_GRAMS and t not in GENERIC} for p in papers}
    n_docs = max(1, len(papers))
    df: dict[str, int] = defaultdict(int)
    for terms in vocab.values():
        for t in terms:
            df[t] += 1
    background = {t for t, c in df.items() if n_docs >= 5 and c >= n_docs}

    by_term: dict[str, list[dict]] = defaultdict(list)
    for p in papers:
        allowed = {t for t in vocab[p.key] if t not in background}
        for a in (p.facts or {}).get("assertions", []):
            if a["polarity"] not in ("pos", "neg"):
                continue
            item = {"doc": p.label(), "key": p.key, "ordinal": a["ordinal"],
                    "polarity": a["polarity"], "text": a["text"]}
            for t in {t for t in allowed if t in a["text"]}:
                if item not in by_term[t]:
                    by_term[t].append(item)

    out = []
    for term, items in by_term.items():
        pos_keys = {i["key"] for i in items if i["polarity"] == "pos"}
        neg_keys = {i["key"] for i in items if i["polarity"] == "neg"}
        if not (pos_keys and neg_keys):
            continue
        only_pos = pos_keys - neg_keys
        only_neg = neg_keys - pos_keys
        both = pos_keys & neg_keys
        # 三态，别糊成一个布尔：上一版把"既非干净跨篇、也非单篇"的情况统叫"单篇内部"，
        # 结果标签和内容对不上（实测「女性」标"单篇内部"却有 3 篇参与）。
        if only_pos and only_neg:
            scope = "cross"          # 有论文单向挺、有论文单向反 → 真正的文献分歧
        elif both:
            scope = "within"         # 同一篇内部正反都有 → 作者自己在权衡/限定
        else:
            scope = "mixed"
        # 按篇取样，否则 items[:6] 会被一篇的 6 条占满，看起来像只有一篇
        picked, by_doc = [], {}
        for i in items:
            by_doc.setdefault((i["key"], i["polarity"]), 0)
            if by_doc[(i["key"], i["polarity"])] < 2:
                picked.append(i)
                by_doc[(i["key"], i["polarity"])] += 1
        out.append({"term": term, "n": len(items), "scope": scope,
                    "n_docs": len(pos_keys | neg_keys),
                    "pos_docs": sorted(pos_keys), "neg_docs": sorted(neg_keys),
                    "items": picked[:6]})
    order = {"cross": 0, "within": 1, "mixed": 2}
    out.sort(key=lambda x: (order[x["scope"]], -x["n_docs"], -x["n"]))
    return out[:top_terms]


def timeline(papers: list) -> dict[str, list[str]]:
    """年份 → 论文，看研究重心的迁移。"""
    out: dict[str, list[str]] = defaultdict(list)
    for p in papers:
        out[p.year or "?"].append(p.title[:30])
    return {k: out[k] for k in sorted(out)}
