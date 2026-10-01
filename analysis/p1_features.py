# -*- coding: utf-8 -*-
"""P1 功能特征矩阵：核心池逐仓从 README/desc/topics 抽取功能词 → 功能×仓库矩阵
规则词表优先（可复现）；覆盖过低的歧义仓另行 LLM 复核留痕。
"""
import json, re, os, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(BASE, 'output', 'ai-novel-deep')

# 功能词表（双语）。key: (中文名, 链路)
LEXICON = {
    '大纲生成': (['大纲', 'outline'], '创作'),
    '章节续写': (['续写', 'continue writing', 'chapter generation', '章节生成',
                  'write chapter', '接着写', 'story continuation', '分段创作'], '创作'),
    '世界观管理': (['世界观', 'worldbuilding', 'world-building', 'world building',
                   '设定集', 'lore'], '创作'),
    '人物卡': (['人物卡', '角色卡', 'character card', 'character profile',
                '人物设定', '角色设定', 'character sheet'], '创作'),
    '伏笔追踪': (['伏笔', 'foreshadow', '伏线', ' plot thread'], '创作'),
    '一致性校验': (['一致性', 'consistency', '连续性', 'continuity', '设定冲突',
                   'state track', '状态追踪', 'timeline track'], '创作'),
    '审稿': (['审稿', 'critique', '评审', 'review agent', 'manuscript review',
              'story review', 'editor feedback', '稿件'], '质量'),
    '去AI味': (['去ai', 'humanize', 'ai味', 'ai 味', 'ai-flavor', 'ai flavor', '降ai',
                'ai痕', '去痕', 'ai检测', 'undetectable', 'ai-generated text',
                'human-like'], '质量'),
    '自动校验': (['自动校验', '校对', 'proofread', 'grammar', '错别字', 'validation'], '质量'),
    '润色': (['润色', 'polish', 'refine', '改写', 'rewrite'], '质量'),
    '多Agent协作': (['多agent', 'multi-agent', 'multi agent', 'agents 协作', 'crewai',
                    'autogen', 'agent 团队', 'multiagent'], '工程'),
    '记忆系统': (['长期记忆', '记忆系统', '记忆库', 'long-term memory', 'memory system',
                 'memory bank', '记忆管理'], '工程'),
    'RAG设定库': (['rag', '向量', 'embedding', '知识库', 'knowledge base', 'vector store',
                  '检索增强'], '工程'),
    '本地模型支持': (['本地模型', 'local model', 'ollama', 'llama.cpp', 'lm studio',
                    '离线', 'offline', '本地运行', 'sakura', '本地部署'], '工程'),
    'API成本控制': (['成本', 'cost control', '费用', '预算', 'budget', '省钱',
                    'token econom', 'free api', '免费api', 'low cost'], '工程'),
    'skill形态': (['claude code', 'claude-code', 'codex', 'opencode', 'cursor',
                   'agent skill', 'agent-skills', 'slash command', '技能库',
                   '.claude', 'agents.md', 'mcp'], '生态'),
    '桌面GUI': (['桌面', 'desktop', 'electron', 'tauri', 'gui', '客户端'], '生态'),
    '网页版': (['网页版', 'web ui', 'webui', '浏览器', 'web interface', '在线使用',
               'web app', 'web-based'], '生态'),
    '导出': (['导出', 'export', 'epub', 'docx', '输出txt', 'txt下载'], '生态'),
    '平台发布': (['番茄', '起点', 'fanqie', 'qidian', '晋江', '飞卢', '纵横',
                 '一键发布', '平台发布', 'site:发布'], '生态'),
}

TAG = re.compile(r'<[^>]+>')
WS = re.compile(r'\s+')

def text_of(r):
    parts = [r.get('description') or '', ' '.join(r.get('topics') or []),
             TAG.sub(' ', r.get('readme_full') or '')]
    return WS.sub(' ', ' '.join(parts)).lower()

def detect(r):
    text = text_of(r)
    feats = {}
    for fname, (words, chain) in LEXICON.items():
        hits = []
        for w in words:
            if w.startswith('site:'):
                continue
            if w.isascii():
                if re.search(r'(?<![a-z0-9])' + re.escape(w) + r'(?![a-z0-9])', text):
                    hits.append(w)
            elif w in text:
                hits.append(w)
        if hits:
            feats[fname] = hits
    return feats

def main():
    cls = json.load(open(os.path.join(OUT, 'p0-classification.json'), encoding='utf-8'))
    data = json.load(open(os.path.join(BASE, 'output', 'ai-novel-final', 'data.json'),
                          encoding='utf-8'))
    extra = json.load(open(os.path.join(OUT, 'readme-extra.json'), encoding='utf-8'))
    byname = {r['full_name']: r for r in data}
    for fn, txt in extra.items():
        if fn in byname and not byname[fn].get('readme_full'):
            byname[fn] = dict(byname[fn], readme_full=txt)
    core = [c['full_name'] for c in cls if c['tier'] == 'core']

    matrix = {}
    for fn in core:
        r = byname[fn]
        matrix[fn] = {'stars': r['stars'], 'overall': r.get('overall'),
                      'features': detect(r)}

    json.dump(matrix, open(os.path.join(OUT, 'feature-matrix.json'), 'w',
                           encoding='utf-8'), ensure_ascii=False, indent=1)

    # 统计
    n = len(matrix)
    covered = sum(1 for m in matrix.values() if m['features'])
    from collections import Counter
    feat_cnt = Counter()
    for m in matrix.values():
        for f in m['features']:
            feat_cnt[f] += 1
    print('核心仓:', n, '至少1功能:', covered, '覆盖率 %.0f%%' % (covered / n * 100))
    print('--- 功能位占位仓库数 ---')
    for f in LEXICON:
        print('%-8s %3d' % (f, feat_cnt.get(f, 0)))
    zero = [fn for fn, m in matrix.items() if not m['features']]
    print('--- 0功能仓（LLM复核候选） ---')
    for fn in zero:
        print(' ', fn)

if __name__ == '__main__':
    main()
