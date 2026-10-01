# -*- coding: utf-8 -*-
"""P2: 抓 Top15 竞品的 open issues（标题+标签+正文摘要），供抱怨聚类。"""
import json, os, sys, io
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from engine.http import load_token, GithubClient
from engine.cache import RequestCache
OUT = os.path.join(BASE, 'output', 'ai-novel-deep')

TOP15 = [
    "zenstory-ai/oh-story-claudecode", "EthanYoQ/AI-Novel-Writer",
    "PenglongHuang/chinese-novelist-skill", "lingfengQAQ/webnovel-writer",
    "Nigh/show-me-the-story", "ExplosiveCoderflome/AI-Novel-Writing-Assistant",
    "yilujian/easy-writing", "yuanbw2025/storyforge",
    "YILING0013/AI_NovelGenerator", "Tomsawyerhu/Chinese-WebNovel-Skill",
    "Deng-m1/MaliangAINovalWriter", "blader/humanizer",
    "Narcooo/inkos", "RhythmicWave/NovelForge", "ydsgangge-ux/dramatica-flow",
]

def main():
    token = load_token()
    client = GithubClient(token, RequestCache(os.path.join(BASE, 'output', 'cache.sqlite3')))
    all_issues = {}
    for fn in TOP15:
        url = (f"https://api.github.com/repos/{fn}/issues?state=open&sort=comments"
               f"&direction=desc&per_page=50")
        items = client.get_json(url, ttl_hours=24) or []
        issues = []
        for it in items:
            if 'pull_request' in it:
                continue
            issues.append({
                'number': it['number'], 'title': it['title'],
                'labels': [l['name'] for l in it.get('labels', [])],
                'comments': it.get('comments', 0),
                'created': it.get('created_at'),
                'body': (it.get('body') or '')[:500],
            })
        all_issues[fn] = {'open_total': None, 'issues': issues}
        print('%-45s open issues(热门50): %d' % (fn, len(issues)))
    json.dump(all_issues, open(os.path.join(OUT, 'p2-issues.json'), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('saved p2-issues.json, calls=%d' % client.calls)

if __name__ == '__main__':
    main()
