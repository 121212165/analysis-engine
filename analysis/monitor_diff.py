# -*- coding: utf-8 -*-
"""P4 监控 diff：对比两份快照 data.json，输出月度赛道变化报告。
用法：python analysis/monitor_diff.py <旧快照目录> <新快照目录> [输出md]
对比：新入池 / 退场仓 / 星标增速榜 / 头部维护性恶化预警
"""
import json, sys, io, os
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def load(d):
    return {r['full_name']: r for r in json.load(open(os.path.join(d, 'data.json'), encoding='utf-8'))}

def main():
    old_d, new_d = sys.argv[1], sys.argv[2]
    out_path = sys.argv[3] if len(sys.argv) > 3 else os.path.join(new_d, '监控报告.md')
    old, new = load(old_d), load(new_d)
    L = ['# 月度赛道监控 diff', '', f'- 旧快照：{old_d}（{len(old)} 仓）', f'- 新快照：{new_d}（{len(new)} 仓）', '']

    entered = sorted(set(new) - set(old), key=lambda fn: -new[fn]['stars'])
    exited = sorted(set(old) - set(new), key=lambda fn: -old[fn]['stars'])
    L.append(f'## 新入池（{len(entered)} 仓，新玩家告警）')
    L.append('')
    for fn in entered[:30]:
        r = new[fn]
        L.append(f"- [{fn}](https://github.com/{fn}) {r['stars']}★ | {(r['description'] or '')[:70]}")
    if len(entered) > 30:
        L.append(f'- …另有 {len(entered)-30} 仓')
    L.append('')
    L.append(f'## 退场（{len(exited)} 仓，搜索不再命中）')
    L.append('')
    for fn in exited[:20]:
        L.append(f"- {fn}（旧 {old[fn]['stars']}★）")
    L.append('')

    common = set(old) & set(new)
    growth = sorted(common, key=lambda fn: -(new[fn]['stars'] - old[fn]['stars']))
    L.append('## 星标增速榜 Top 20（快照差值）')
    L.append('')
    L.append('| 仓库 | Δ★ | 旧→新 | 90天关issue |')
    L.append('| --- | --- | --- | --- |')
    for fn in growth[:20]:
        o, n = old[fn], new[fn]
        if n['stars'] - o['stars'] <= 0:
            break
        L.append(f"| {fn} | +{n['stars']-o['stars']} | {o['stars']}→{n['stars']} | {n['closed_issues_90d']} |")
    L.append('')

    L.append('## 头部维护性恶化预警（Top50 仓 maintenance 信号下降 >0.15）')
    L.append('')
    alerts = []
    for fn in common:
        om = (old[fn].get('signals') or {}).get('maintenance')
        nm = (new[fn].get('signals') or {}).get('maintenance')
        if om is not None and nm is not None and om - nm > 0.15 and new[fn]['stars'] >= 300:
            alerts.append((om - nm, fn, om, nm))
    alerts.sort(reverse=True)
    if alerts:
        for d, fn, om, nm in alerts[:15]:
            L.append(f"- ⚠️ {fn}：maintenance {om:.2f}→{nm:.2f}（open issues {new[fn]['open_issues']}）")
    else:
        L.append('- 无')
    L.append('')
    L.append('## 最近创建新仓扫描（created 近 60 天，topic 命中，防"没 star 没排名"漏检）')
    L.append('')
    L.append('运行 `bash analysis/scan_new_repos.sh` 单独拉取（见该脚本输出），本 diff 不重复请求。')

    open(out_path, 'w', encoding='utf-8').write('\n'.join(L))
    print('written', out_path)

if __name__ == '__main__':
    main()
