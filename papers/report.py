"""papers.report：中文 Markdown 报告 + data.json，落 output/<run_id>/。"""
from __future__ import annotations

import datetime
import json
from pathlib import Path

from .compare import method_matrix, overview, timeline, topic_tension

CAVEAT = ("> ⚠️ 本报告的语料来自 CNKI 的 PDF **文本层**，该文本层本身存在字符级错误"
          "（实测见过 `5里论谱系`、`并进人价值`）。因此下面的抽取结果是**线索**，"
          "每条都标了 (论文, 段号) 便于回核原文；**引用前必须核对 PDF**。")


def render_report(papers: list, corpus_dir: str = "") -> str:
    rows = overview(papers)
    lines: list[str] = []
    lines.append(f"# 文献对照报告：{len(papers)} 篇")
    lines.append("")
    lines.append(f"生成 {datetime.datetime.now():%Y-%m-%d %H:%M} | 语料 {corpus_dir or '（未指定）'} | "
                 f"合计 {sum(r['chars'] for r in rows):,} 字 / {sum(r['paras'] for r in rows)} 段")
    lines.append("")
    lines.append(CAVEAT)
    lines.append("")

    lines.append("## 一、总览")
    lines.append("")
    lines.append("| 年 | 题名 | 刊物 | 类型 | 页 | 段 | 方法类 | 数字断言 | 论断 | 引用 |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|")
    for r in rows:
        lines.append(f"| {r['year']} | {r['title'][:26]} | {r['source'][:14]} | {r['db']} | "
                     f"{r['pages']} | {r['paras']} | {r['methods']} | {r['numbers']} | "
                     f"{r['assertions']} | {r['citations']} |")
    lines.append("")

    lines.append("## 二、方法分布")
    lines.append("")
    for group, docs in method_matrix(papers).items():
        lines.append(f"- **{group}**（{len(docs)} 篇）：" + "；".join(d[:34] for d in docs))
    lines.append("")

    tensions = topic_tension(papers)
    SCOPE_LABEL = {"cross": "跨论文分歧", "within": "单篇内部权衡", "mixed": "混合"}
    lines.append("## 三、张力点（同一字组下判断相反）")
    lines.append("")
    if not tensions:
        lines.append("未发现同一字组下的正负对立论断。可能是语料太少，也可能是极性词表没覆盖"
                     "该领域的表述方式——**这不等于没有分歧**。")
    else:
        counts = {k: sum(1 for t in tensions if t["scope"] == k) for k in SCOPE_LABEL}
        lines.append("分类：" + " · ".join(f"{v} 条{lbl}" for lbl, v in
                                          ((lbl, counts[k]) for k, lbl in SCOPE_LABEL.items()) if v))
        lines.append("")
        for t in tensions:
            lines.append(f"### 「{t['term']}」 — {SCOPE_LABEL[t['scope']]}｜涉及 {t['n_docs']} 篇"
                         f"（正向 {len(t['pos_docs'])} · 负向 {len(t['neg_docs'])}）")
            for i in t["items"]:
                arrow = "＋" if i["polarity"] == "pos" else "－"
                lines.append(f"- {arrow} {i['doc']} 段#{i['ordinal']}：{i['text'][:90]}")
            lines.append("")
        lines.append("**怎么读这一节**：字组是滑动 2-gram（无分词器），所以"
                     "「同一个字组两边都出现」**不等于两篇在谈同一件事**。"
                     "实测就出现过假张力——如「子女」那条，一篇讲再婚概率、一篇讲抚养费支付意愿，"
                     "结果变量根本不同，不是分歧。所以每条都要点开 (论文, 段号) 核对："
                     "先确认两边讨论的是同一个因变量，再判断是否真的对立。"
                     "标为「跨论文分歧」的也只是**候选**，不是结论。")
    lines.append("")

    lines.append("## 四、时间线")
    lines.append("")
    for year, titles in timeline(papers).items():
        lines.append(f"- **{year}**（{len(titles)}）：" + "；".join(titles))
    lines.append("")
    return "\n".join(lines)


def save_output(outdir: str | Path, papers: list, corpus_dir: str = "") -> dict:
    out = Path(outdir)
    out.mkdir(parents=True, exist_ok=True)
    md = render_report(papers, corpus_dir)
    (out / "report.md").write_text(md, encoding="utf-8")
    (out / "data.json").write_text(
        json.dumps({"n": len(papers),
                    "overview": overview(papers),
                    "tension": topic_tension(papers),
                    "papers": [p.to_dict() for p in papers]},
                   ensure_ascii=False, indent=1), encoding="utf-8")
    return {"report": str(out / "report.md"), "data": str(out / "data.json")}
