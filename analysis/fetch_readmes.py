# -*- coding: utf-8 -*-
"""补抓核心池缺失的 README（复用 engine 的 client+cache，重跑零成本）。"""
import json, os, sys, io, time
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from engine.http import load_token, GithubClient
from engine.cache import RequestCache
OUT = os.path.join(BASE, 'output', 'ai-novel-deep')

def main():
    cls = json.load(open(os.path.join(OUT, 'p0-classification.json'), encoding='utf-8'))
    data = json.load(open(os.path.join(BASE, 'output', 'ai-novel-final', 'data.json'),
                          encoding='utf-8'))
    byname = {r['full_name']: r for r in data}
    need = [c['full_name'] for c in cls if c['tier'] in ('core', 'edge')
            and not byname[c['full_name']].get('readme_full')]
    print('待补抓:', len(need))
    token = load_token()
    client = GithubClient(token, RequestCache(os.path.join(BASE, 'output', 'cache.sqlite3')))
    fetched, failed = {}, []
    for i, fn in enumerate(need, 1):
        try:
            txt = client.readme_text(fn)
            if not txt:
                txt = client.readme_via_search_payload(fn)
        except Exception as e:
            txt = None
            print('  [skip] %s: %s' % (fn, str(e)[:80]))
        if txt:
            fetched[fn] = txt
        else:
            failed.append(fn)
        if i % 20 == 0:
            print('  %d/%d (calls=%d, wait=%.0fs)' % (i, len(need), client.calls, client.limited_wait))
    json.dump(fetched, open(os.path.join(OUT, 'readme-extra.json'), 'w', encoding='utf-8'),
              ensure_ascii=False)
    print('成功', len(fetched), '失败', len(failed), failed)

if __name__ == '__main__':
    main()
