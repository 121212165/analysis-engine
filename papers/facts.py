"""papers.facts：从段落里抽可核对的事实。

纯正则、零模型、零第三方依赖（守 analysis-engine 的纪律）。
每条事实都带 (doc_key, 段号)，这样报告里的每个数都能点回原文——
没有回指的"综合"等于重新编了一遍。

⚠️ 语料来自 CNKI 的 PDF 文本层，**本身有字符级错误**（实测见过 `5里论谱系`、
`并进人价值`）。所以这里抽出来的是**线索**，引用前必须回核 PDF。
"""
from __future__ import annotations

import re
from collections import Counter

from .models import Paper

# 方法词表：社会学/家庭研究常用。分组是为了报告里能按类聚合。
METHODS: dict[str, tuple[str, ...]] = {
    "定量": ("荟萃分析", "meta分析", "Meta分析", "回归", "离散时间", "事件史", "潜类别",
             "结构方程", "logit", "Logit", "卡方", "方差分析", "显著性", "系数"),
    "调查": ("问卷调查", "结构性问卷", "实证调查", "抽样", "样本", "女职工调查", "全国性调查"),
    "质性": ("深度访谈", "访谈", "焦点小组", "参与观察", "民族志", "个案", "口述"),
    "文本/二手": ("文本分析", "内容分析", "话语分析", "文献综述", "述评", "二手资料", "年鉴数据"),
    "理论建构": ("理论谱系", "概念", "框架", "类型学", "理想型", "本土化"),
}

ASSERT_MARK = re.compile(
    r"(认为|发现|表明|显示|结果显示|研究表明|本文提出|本文认为|结论是|结果是|研究发现|可见|说明)")
# 极性词表：只放**方向明确**的词。
# 实测教训：把"显著影响/显著"当正向，会把"并未呈现显著影响"（零结果）判成 ＋。
# 中文学术写作里"显著"是强度词不是方向词，必须排除。
NEG_MARK = re.compile(r"(负面影响|消极影响|不利|降低|负相关|削弱|恶化|阻碍|减少|损害|"
                      r"不显著|没有显著|无显著|未必|不一定|不成立|抑制)")
POS_MARK = re.compile(r"(正向|正相关|提高|促进|改善|积极|增强|有利于|提升|缓冲|缓解)")
# 方向词与强度词共现时的否定式，如"未必是负面的"——单独判会反，标 both 交给人看
NULL_MARK = re.compile(r"(并未|未呈现|不显著|没有显著|无显著|未发现)")

NUM_IN_TEXT = re.compile(r"\d+(?:\.\d+)?\s*(?:%|％|个百分点|人|篇|例|个|年|岁|次|万|亿)")
CIT_BRACKET = re.compile(r"\[\d+(?:[-,，]\d+)*\]")
CIT_AUTHORYEAR = re.compile(r"[（(][^（）()]{0,24}?(?:19|20)\d{2}[^（）()]{0,6}[）)]")

SECTIONS = ("引言", "文献综述", "理论基础", "研究设计", "数据来源", "样本", "方法",
            "实证", "结果", "发现", "讨论", "结论", "余论", "政策建议")


def _sentence_window(text: str, m) -> str:
    """取命中点所在的句子，供人快速判断，不必回全文。"""
    start = max(text.rfind("。", 0, m.start()), text.rfind("\n", 0, m.start())) + 1
    end = len(text)
    for ch in "。！？；":
        i = text.find(ch, m.end())
        if i != -1:
            end = min(end, i + 1)
    return text[start:end].strip()[:160]


def extract_methods(paper: Paper) -> dict[str, list[int]]:
    """方法类 → 段号。标题按段号 -1 记。

    标题必须一起看：《…实证研究述评》《…基于…调查的实证分析》这类题名直接把方法写在外面，
    只扫正文会漏（实测漏掉"述评"）。
    """
    hit: dict[str, list[int]] = {}
    scanned = [(-1, paper.title)] + list(enumerate(paper.paragraphs))
    for i, text in scanned:
        for group, words in METHODS.items():
            if any(w in text for w in words):
                bucket = hit.setdefault(group, [])
                if i not in bucket:
                    bucket.append(i)
    return hit


def extract_assertions(paper: Paper, limit: int = 40) -> list[dict]:
    """核心论断 + 方向极性。同一主题下方向相反的论断是最有价值的产出，见 compare.py。

    同一句常被多个标记词命中（实测"研究发现…表明…"一句出三个），
    所以按 (段号, 句子) 去重，否则报告里会出现重复条目。
    """
    out, seen = [], set()
    for i, para in enumerate(paper.paragraphs):
        for m in ASSERT_MARK.finditer(para):
            sent = _sentence_window(para, m)
            if (i, sent) in seen:
                continue
            seen.add((i, sent))
            neg, pos = bool(NEG_MARK.search(sent)), bool(POS_MARK.search(sent))
            if NULL_MARK.search(sent) and not (neg or pos):
                pol = "null"                        # 零结果不是正向
            elif neg and not pos:
                pol = "neg"
            elif pos and not neg:
                pol = "pos"
            elif neg and pos:
                pol = "both"                        # 自相矛盾或转述他人，交给人判
            else:
                pol = "n/a"
            out.append({"ordinal": i, "marker": m.group(0), "text": sent, "polarity": pol})
            if len(out) >= limit:
                return out
    return out


def count_numbers(paper: Paper) -> tuple[int, list[str]]:
    samples: list[str] = []
    total = 0
    for para in paper.paragraphs:
        ms = list(NUM_IN_TEXT.finditer(para))
        total += len(ms)
        for m in ms[:2]:
            if len(samples) < 8:
                samples.append(_sentence_window(para, m)[:100])
    return total, samples


def count_citations(paper: Paper) -> dict[str, int]:
    joined = "\n".join(paper.paragraphs)
    return {"bracket": len(CIT_BRACKET.findall(joined)),
            "authoryear": len(CIT_AUTHORYEAR.findall(joined))}


def detect_sections(paper: Paper) -> list[str]:
    found = []
    for name in SECTIONS:
        if any(p.startswith(name) or p[:12].find(name) >= 0 for p in paper.paragraphs):
            found.append(name)
    return found


def keywords(paper: Paper, top: int = 15) -> list[str]:
    """高频**字组**（滑动 2-gram），不是分词结果。

    别叫它"关键词"：没有分词器时，`[一-鿿]{2,6}` 的贪婪匹配产出的是
    "研究发现配偶参"这种任意块，跨文档永远对不上（实测 topic_tension 因此恒空）。
    滑动 2-gram 至少保证"同一个字组在两篇都高频"这件事是可判定的——
    代价是它会切出"究发"这类噪声，所以只当线索用。
    """
    c: Counter = Counter()
    for para in paper.paragraphs:
        run = ""
        for ch in para + " ":
            if "一" <= ch <= "鿿":
                run += ch
            else:
                for i in range(len(run) - 1):
                    g = run[i:i + 2]
                    if g not in STOP_GRAMS:
                        c[g] += 1
                run = ""
    return [g for g, n in c.most_common(top) if n >= 2]


STOP_GRAMS = {"研究", "本文", "认为", "发现", "显示", "表明", "通过", "数据", "分析",
              "社会", "中国", "问题", "因此", "可以", "一个", "我们", "其中", "以及",
              "并且", "但是", "如果", "这些", "方面", "主要", "重要", "同时", "例如",
              "然而", "所以", "结果", "结论", "学者", "基于", "于上"}


def extract(paper: Paper) -> Paper:
    numbers, samples = count_numbers(paper)
    assertions = extract_assertions(paper)
    methods = extract_methods(paper)
    paper.facts = {
        "methods": methods,
        "assertions": assertions,
        "numbers": numbers,
        "number_samples": samples,
        "citations": count_citations(paper),
        "sections": detect_sections(paper),
        "keywords": keywords(paper),
        "paras": len(paper.paragraphs),
        "chars": sum(len(p) for p in paper.paragraphs),
    }
    # 回指表：每类事实落在哪几段。报告里的任何一条都能据此点回原文。
    paper.evidence = {
        "assertion_ordinals": sorted({a["ordinal"] for a in assertions}),
        "method_ordinals": {g: sorted(v) for g, v in methods.items()},
        "corpus_file": f"{paper.key}_{paper.year}_{paper.title[:20]}.md",
    }
    return paper
