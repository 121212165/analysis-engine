# -*- coding: utf-8 -*-
"""P0 全池清洗定级：294 仓 → 核心/边缘/剔除
规则（可复现）：
  R1 简介(desc)或 topics 含赛道词 → 相关
  R2 仅 README 正文命中(readme-only)且 star>10000 → 剔除（通用大仓噪声）
  R3 readme-only 且 star<=10000 → 边缘候选（抽样人工复核）
  R4 phrase 通道命中但 R1 未中 → 边缘候选
  相关内部再分级：核心=赛道词命中且 stars>=50；边缘=其余相关
  覆盖词表见 TRACK_WORDS
"""
import json, re, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, 'output', 'ai-novel-final', 'data.json')
OUT  = os.path.join(BASE, 'output', 'ai-novel-deep')
os.makedirs(OUT, exist_ok=True)

# 赛道词表：强赛道词（命中即相关）
TRACK_WORDS = [
    # EN
    'novel', 'fiction', 'webnovel', 'web-novel', 'story', 'storytelling',
    'writing', 'writer', 'fanfic', 'roleplay', 'screenplay', 'narrative',
    # CN/JP
    '小说', '小説', '网文', '写作', '故事', '同人', '剧本', '续写', '情节',
    '大纲', '人物卡', '世界观', '文字冒险', '互动小说',
]
# 语境共现检查用的过泛词：单独命中不算，需与 AI/写作语境共现
BROAD_WORDS = {'write', 'character', 'story', 'writing', 'author', 'writer',
               'narrative'}
AI_CONTEXT = ['ai', 'gpt', 'llm', 'agent', 'claude', '模型', '智能', '写作', '小说',
              'novel', 'fiction', 'story', 'writing', 'webnovel', 'prompt',
              'write', 'writer', '创作']
# 邻域负词：命中且无创作词 → 小说生态但不做"写"（阅读器/下载/听书/翻译…）
ADJ_NEG = ['阅读', 'reader', 'download', '下载', '书架', '书源', 'audiobook',
           '听书', 'tts', '语音', '朗读', 'translat', '翻译', '漫画', 'manga',
           'cms', '爬虫', 'crawler', '书城', '追书', 'galgame', 'visual novel',
           '视觉小说', 'ocr', 'epub', '书评']
CREATE_POS = ['写作', '创作', '生成', 'generate', 'writ', 'creat', '续写',
              '创作平台', '助手', 'assistant', '工具']
# 非虚构写作：内容创作邻域
NONFICTION = ['公众号', '头条', '知乎', 'tweet', 'twitter', 'blog', '博客',
              '文章', 'article', '文案', 'marketing', '论文', 'academic',
              'essay', '小红书', '自媒体', '媒体', 'news', '新闻', '热文', 'resume', '简历', 'cover letter',
              '爆款文', 'seo', '邮件', 'email']
# 通用编辑器重名（如 steven-tey/novel）
EDITOR_GENERIC = re.compile(r'wysiwyg|notion-style|rich.?text|editor.?component|'
                            r'block.?editor|slate|tiptap', re.I)
NAME_HINT = re.compile(r'ai.?novel|novel.?writ|小说|网文|写作', re.I)
# novel 作形容词（"a novel approach"）假阳性
NOVEL_ADJ = re.compile(r"novel[,.]? (approach|method|way|design|algorithm|framework|"
                       r"genetics?|insight|perspective|solution|strategy|model|"
                       r"implementation|technique|architecture|fast|high)", re.I)
# 中文子串边界：局域网文件 ≠ 网文
CN_BOUNDED = {'网文': re.compile(r'(?<!局)(?<!域)网文(?![件络页站民坛吧盘])')}
# 视觉小说/galgame 游戏生态（非 AI 写作）
VISUAL_NOVEL = ['visual novel', '视觉小说', 'galgame', 'vngame', 'unity', 'kirikiri', '吉里吉里']

def _hit(text, words):
    t = text.lower()
    out = []
    for w in words:
        pat = CN_BOUNDED.get(w)
        if pat:
            if pat.search(text):
                out.append(w)
        elif w in t:
            out.append(w)
    return out

def classify(r):
    desc = (r.get('description') or '')
    name = r['full_name'].split('/')[-1]
    topics = ' '.join(r.get('topics') or [])
    stars = r['stars']
    ch = set(r['channels'])
    reasons = []
    # R1: name/desc/topics 赛道词
    dh = _hit(desc, TRACK_WORDS)
    th = _hit(topics, TRACK_WORDS)
    nh = _hit(name, TRACK_WORDS)
    if dh or th or nh:
        ctx = _hit(desc + ' ' + topics + ' ' + name, AI_CONTEXT)
        dh_strong = [w for w in dh if w not in BROAD_WORDS]
        th_strong = [w for w in th if w not in BROAD_WORDS]
        broad_ok = bool(ctx) or bool(dh_strong) or bool(th_strong) or bool(nh)
        if broad_ok:
            hits = sorted(set(dh_strong) | set(th_strong) | set(nh)
                          | (set(dh) if ctx else set()) | (set(th) if ctx else set()))
            reasons.append('R1 赛道词:%s' % ','.join(hits))
            # R1b 非虚构写作 → 边缘-内容
            all_text = desc + ' ' + topics
            novel_hits = set(hits) & {'小说', '小説', 'novel', 'fiction', '网文',
                                      'story', 'webnovel', 'web-novel', '故事',
                                      'fanfic', '同人', '互动小说'}
            nf = _hit(all_text, NONFICTION)
            if nf and not novel_hits:
                return 'edge', reasons + ['R1b 非虚构写作:%s' % ','.join(nf)], 'relevant'
            # R1c 邻域负词：生态工具不写 → 边缘-邻域
            neg = _hit(all_text, ADJ_NEG)
            cpos = _hit(all_text, CREATE_POS)
            if neg and not cpos:
                return 'edge', reasons + ['R1c 邻域工具:%s' % ','.join(neg)], 'relevant'
            # R1d 编辑器重名假阳性
            if set(hits) <= {'novel'} and EDITOR_GENERIC.search(all_text) \
                    and not _hit(all_text, ['writ', 'fiction', '小说', 'stor', '网文']):
                return 'removed', reasons + ['R1d 编辑器重名(novel)'], 'noise'
            # R1e novel 作形容词的假阳性
            if set(hits) <= {'novel'} and NOVEL_ADJ.search(all_text):
                return 'removed', reasons + ['R1e novel作形容词'], 'noise'
            # R1f 视觉小说/galgame 游戏生态 → 边缘-邻域
            vn = _hit(all_text, VISUAL_NOVEL)
            if vn and not _hit(all_text, ['写作', 'writ', '小说创作', '续写']):
                return 'edge', reasons + ['R1f 游戏生态:%s' % ','.join(vn)], 'relevant'
            tier = 'core' if stars >= 50 else 'edge'
            return tier, reasons, 'relevant'
    # R1g NLP/学术资源仓（小说只是数据集语境）
    if 'nlp' in name.lower().replace('-', '') and not _hit(desc, CREATE_POS):
        return 'edge', ['R1g NLP资源仓'], 'relevant'
    # R6: 官网/文档类仓库
    if _hit(desc, ['官网', '文档', 'documentation', 'homepage', 'website']):
        return 'removed', ['R6 官网文档仓'], 'noise'
    # R2: readme-only + star>10000 → 剔除
    if ch == {'readme'} and stars > 10000:
        return 'removed', ['R2 readme-only且star>10000(通用大仓)'], 'noise'
    # R3: readme-only 低星 → 剔除（人工抽样校准：仅正文命中基本是噪声）
    if ch == {'readme'}:
        return 'edge', ['R3 readme-only低星(待复核)'], 'borderline'
    # R4: phrase 命中但 R1 未中
    if 'phrase' in ch:
        return 'edge', ['R4 phrase命中但无赛道词(待复核)'], 'borderline'
    # R5: loose-only → 剔除（抽样校准：全部为泛技术仓噪声）
    return 'removed', ['R5 loose-only(抽样确认为泛技术噪声)'], 'noise'

def main():
    repos = json.load(open(DATA, encoding='utf-8'))
    out = []
    for r in repos:
        tier, reasons, rel = classify(r)
        out.append({
            'full_name': r['full_name'], 'stars': r['stars'],
            'tier': tier, 'relevance_class': rel, 'reasons': reasons,
            'overall': r.get('overall'), 'license_spdx': r.get('license_spdx'),
        })
    json.dump(out, open(os.path.join(OUT, 'p0-classification.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    from collections import Counter
    c = Counter(x['tier'] for x in out)
    print('total', len(out), dict(c))
    core = sum(1 for x in out if x['tier'] == 'core')
    edge = sum(1 for x in out if x['tier'] == 'edge')
    print('core+edge =', core + edge, '(计划预期 120-160)')

if __name__ == '__main__':
    main()
