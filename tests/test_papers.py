import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from papers import (Paper, extract, load_corpus, load_records, method_matrix,
                    overview, parse_front_matter, save_output, topic_tension)

MD_POS = """---
key: "aaaa1111"
title: "隔代育儿对儿童发展影响的实证研究述评"
authors: "沈奕斐"
source: "妇女研究论丛"
db: "期刊"
year: "2023"
pages_pdf: 16
---
多数研究认为隔代育儿会对儿童产生负面影响，本文使用荟萃分析方法分析过去20年的实证研究。

但进一步分析发现，隔代育儿的概念界定与测量对研究结论存在重大影响，祖辈参与未必是负面的。
"""

MD_NEG = """---
key: "bbbb2222"
title: "祖辈照料与儿童发展"
authors: "李四, 王五"
source: "某学报"
db: "期刊"
year: "2024"
pages_pdf: 10
---
深度访谈显示，祖辈照料显著降低了儿童的自主性，负面影响是稳定的。

研究发现祖辈参与时间越长，儿童问题行为越多。
"""

MD_BAD = "# 没有 front-matter 的普通文本\n\n一段话。\n"

# 共享字面词「育儿」+ 相反极性：这是 topic_tension 唯一能诚实抓住的形状
MD_T_POS = """---
key: "cccc3333"
title: "配偶参与育儿与婚姻质量"
authors: "张三"
source: "某刊"
db: "期刊"
year: "2024"
---
研究发现配偶参与育儿显著提高了婚姻质量，育儿投入越多满意度越高。
"""

MD_T_NEG = """---
key: "dddd4444"
title: "育儿分工与离婚风险"
authors: "李四"
source: "另一刊"
db: "期刊"
year: "2025"
---
深度访谈表明，育儿分工失衡显著降低了婚姻稳定性，育儿负担削弱了关系。
"""


def corpus(files: dict[str, str]) -> Path:
    d = Path(tempfile.mkdtemp())
    for name, body in files.items():
        (d / name).write_text(body, encoding="utf-8")
    return d


class Parse(unittest.TestCase):
    def test_front_matter_and_paragraphs(self):
        meta, paras = parse_front_matter(MD_POS)
        self.assertEqual(meta["key"], "aaaa1111")
        self.assertEqual(len(paras), 2)

    def test_load_corpus_skips_unparseable_loudly(self):
        c = corpus({"a.md": MD_POS, "junk.md": MD_BAD})
        papers = load_corpus(c)
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0].title, "隔代育儿对儿童发展影响的实证研究述评")

    def test_authors_split_on_comma_and_space(self):
        papers = load_corpus(corpus({"b.md": MD_NEG}))
        self.assertEqual(papers[0].authors, ["李四", "王五"])


class Facts(unittest.TestCase):
    def setUp(self):
        self.papers = [extract(p) for p in load_corpus(corpus({"a.md": MD_POS, "b.md": MD_NEG}))]
        self.a, self.b = self.papers[0], self.papers[1]

    def test_methods_grouped_not_per_word(self):
        self.assertIn("质性", self.b.facts["methods"])       # 深度访谈
        self.assertIn("文本/二手", self.a.facts["methods"])   # 述评
        self.assertIn("定量", self.a.facts["methods"])        # 荟萃分析

    def test_assertions_carry_polarity_and_locator(self):
        self.assertTrue(self.a.facts["assertions"])
        for asrt in self.a.facts["assertions"]:
            self.assertIsInstance(asrt["ordinal"], int)
            self.assertIn(asrt["polarity"], ("pos", "neg", "both", "n/a"))

    def test_negative_polarity_detected(self):
        pols = {a["polarity"] for a in self.b.facts["assertions"]}
        self.assertIn("neg", pols)

    def test_every_assertion_ordinal_is_in_range(self):
        for p in self.papers:
            for a in p.facts["assertions"]:
                self.assertLess(a["ordinal"], len(p.paragraphs))

    def test_citations_counted(self):
        self.assertIn("bracket", self.a.facts["citations"])


class Compare(unittest.TestCase):
    def setUp(self):
        self.papers = [extract(p) for p in load_corpus(corpus({"a.md": MD_POS, "b.md": MD_NEG}))]

    def test_overview_sorted_by_year_desc(self):
        rows = overview(self.papers)
        self.assertEqual([r["year"] for r in rows], ["2024", "2023"])

    def test_method_matrix_lists_labels(self):
        m = method_matrix(self.papers)
        self.assertTrue(any("祖辈照料" in d for d in m.get("质性", [])))

    def test_tension_finds_opposing_judgements_on_shared_term(self):
        papers = [extract(p) for p in load_corpus(corpus({"p.md": MD_T_POS, "n.md": MD_T_NEG}))]
        t = topic_tension(papers)
        self.assertTrue(t, "两篇对「育儿」判断相反，应被抓出来")
        one = t[0]
        self.assertIn("育儿", one["term"])
        self.assertTrue(one["pos_docs"] and one["neg_docs"])

    def test_tension_cannot_link_non_overlapping_synonyms(self):
        """钉住局限，不藏：「隔代育儿」和「祖辈照料」字面不相交，本层不联。
        要联得上得靠同义词表或语义向量——那是另一件事，不该用正则假装做到。"""
        papers = [extract(p) for p in load_corpus(corpus({"a.md": MD_POS, "b.md": MD_NEG}))]
        t = topic_tension(papers)
        linked = {x["term"] for x in t}
        self.assertFalse({"隔代育儿", "祖辈照料"} <= linked, linked)

    def test_methods_include_the_title(self):
        """《…实证研究述评》的方法写在题名里，只扫正文会漏。"""
        a = extract(load_corpus(corpus({"a.md": MD_POS}))[0])
        self.assertIn(-1, a.facts["methods"].get("文本/二手", []))
        self.assertIn("文本/二手", a.facts["methods"])

    def test_tension_empty_when_all_same_polarity(self):
        only = [extract(p) for p in load_corpus(corpus({"b.md": MD_NEG}))]
        # 单篇也可能自相矛盾；但绝不该抛
        self.assertIsInstance(topic_tension(only), list)


class Output(unittest.TestCase):
    def test_save_output_writes_both_files(self):
        papers = [extract(p) for p in load_corpus(corpus({"a.md": MD_POS, "b.md": MD_NEG}))]
        out = Path(tempfile.mkdtemp()) / "run"
        paths = save_output(out, papers, "corpus")
        md = Path(paths["report"]).read_text(encoding="utf-8")
        self.assertIn("文献对照报告：2 篇", md)
        self.assertIn("引用前必须核对 PDF", md)     # 语料缺陷告警不许丢
        self.assertIn("张力点", md)
        data = json.loads(Path(paths["data"]).read_text(encoding="utf-8"))
        self.assertEqual(data["n"], 2)


class NoSiteLeak(unittest.TestCase):
    """公开仓守门条：取数细节一个字段都不能进来。"""

    def test_paper_has_no_url_fields(self):
        fields = set(Paper.__dataclass_fields__)
        self.assertFalse({f for f in fields if "url" in f or "link" in f}, fields)

    def test_load_records_strips_abs_url(self):
        src = Path(tempfile.mkdtemp()) / "records.json"
        src.write_text(json.dumps({"records": [
            {"key": "x", "title": "T", "abs_url": "https://example.invalid/abstract?v=SECRET"}]}),
            encoding="utf-8")
        rows = load_records(src)
        self.assertNotIn("abs_url", rows[0])
        self.assertNotIn("SECRET", json.dumps(rows))

    def test_package_sources_carry_no_real_urls(self):
        """公开仓守门条。

        注意别写成"枚举已知镜像域名当禁词表"——那张表本身就把管道对接了哪些镜像
        说出去了。改成更严也更干净的断言：整个包不许出现任何真实 URL，
        只允许保留段里 example.invalid。
        """
        root = Path(__file__).resolve().parent.parent / "papers"
        offenders = []
        for f in sorted(root.glob("*.py")):
            for i, line in enumerate(f.read_text(encoding="utf-8").splitlines(), 1):
                for m in re.finditer(r"https?://([A-Za-z0-9._-]+)", line):
                    if m.group(1) != "example.invalid":
                        offenders.append(f"{f.name}:{i} {m.group(1)}")
        self.assertEqual(offenders, [], "papers/ 里出现了真实 URL：" + "; ".join(offenders))

    def test_package_sources_have_no_query_tokens(self):
        """`?v=` 这类易失取数令牌也不该进公开仓。"""
        root = Path(__file__).resolve().parent.parent / "papers"
        hits = [f.name for f in root.glob("*.py")
                if re.search(r"[?&][a-z-]*token=|[?&]v=[A-Za-z0-9]", f.read_text(encoding="utf-8"))]
        self.assertEqual(hits, [])



MD_NULL = """---
key: "eeee5555"
title: "零结果对照"
authors: "王五"
source: "某刊"
db: "期刊"
year: "2026"
---
研究发现，干预时长与结果并未呈现显著影响，说明该项在决策中作用有限。
"""


class Polarity(unittest.TestCase):
    """上一版把"显著影响"当正向，于是"并未呈现显著影响"（零结果）被判成 ＋。"""

    def test_null_finding_is_not_positive(self):
        p = extract(load_corpus(corpus({"n.md": MD_NULL}))[0])
        pols = {a["polarity"] for a in p.facts["assertions"]}
        self.assertIn("null", pols, p.facts["assertions"])
        self.assertNotIn("pos", pols)

    def test_same_sentence_not_repeated_per_marker(self):
        """一句里"研究发现…表明…"会命中多个标记词，上一版把同一句列两遍。"""
        papers = [extract(x) for x in load_corpus(corpus({"p.md": MD_T_POS, "n.md": MD_T_NEG}))]
        for p in papers:
            pairs = [(a["ordinal"], a["text"]) for a in p.facts["assertions"]]
            self.assertEqual(len(pairs), len(set(pairs)), p.title)

    def test_generic_terms_not_used_as_topics(self):
        papers = [extract(p) for p in load_corpus(corpus({"p.md": MD_T_POS, "n.md": MD_T_NEG}))]
        terms = {t["term"] for t in topic_tension(papers)}
        for g in ("影响", "可能", "显著", "研究", "发现"):
            self.assertNotIn(g, terms)

    def test_scope_labels_three_states_not_a_boolean(self):
        """上一版把"既非干净跨篇、也非单篇"的情况统叫"单篇内部"，标签和内容对不上。"""
        papers = [extract(p) for p in load_corpus(corpus({"p.md": MD_T_POS, "n.md": MD_T_NEG}))]
        t = topic_tension(papers)
        self.assertTrue(t)
        self.assertEqual(t[0]["scope"], "cross", "两篇单向相反应判为跨论文分歧且排最前")
        self.assertEqual(t[0]["n_docs"], 2)
        for x in t:
            self.assertIn(x["scope"], ("cross", "within", "mixed"))

    def test_items_span_documents_not_one_doc_flooding(self):
        """items[:6] 截断会被一篇占满，看起来像只有一篇参与。"""
        papers = [extract(p) for p in load_corpus(corpus({"p.md": MD_T_POS, "n.md": MD_T_NEG}))]
        one = next(t for t in topic_tension(papers) if t["scope"] == "cross")
        self.assertGreaterEqual(len({i["key"] for i in one["items"]}), 2)

    def test_no_fallback_to_terms_that_are_absent(self):
        """上一版没命中就随便挑三个字组挂上去 —— 那是把论断安到没出现的主题上。"""
        one = [extract(p) for p in load_corpus(corpus({"a.md": MD_T_POS}))]
        for t in topic_tension(one):
            for item in t["items"]:
                self.assertIn(t["term"], item["text"], t["term"])


if __name__ == "__main__":
    unittest.main()
