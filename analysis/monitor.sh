#!/usr/bin/env bash
# P4 月度赛道监控：重扫 → 快照 → diff 报告 → 新玩家扫描
# 用法: bash analysis/monitor.sh [YYYY-MM]   # 缺省=当月
# 依赖: python(引擎)、gh CLI（新仓扫描）。缓存 12h TTL，月度重跑即自然增量。
set -euo pipefail
cd "$(dirname "$0")/.."

MONTH="${1:-$(date +%Y-%m)}"
SNAP="output/snapshots/$MONTH"
PREV="$(ls -d output/snapshots/* 2>/dev/null | sort | grep -v "$MONTH" | tail -1 || true)"
[ -z "$PREV" ] && PREV="output/ai-novel-final"   # 首跑基线 = 2026-10 全池

echo "== 1/4 重扫全池 → $SNAP =="
python cli.py "写小说|网文|AI novel" --scenario map --enrich-limit 50 --output "$SNAP"

echo "== 2/4 diff 对比（基线: $PREV）=="
python analysis/monitor_diff.py "$PREV" "$SNAP"

echo "== 3/4 最近创建新仓扫描 =="
SINCE="$(date -d '-60 days' +%Y-%m-%d 2>/dev/null || date -v-60d +%Y-%m-%d)"
gh api -X GET search/repositories -f q="topic:ai-writing topic:novel-writing created:>$SINCE" \
  -f sort=stars -f per_page=30 \
  --jq '.items[] | "\(.stargazers_count)★ \(.full_name) created:\(.created_at) \(.description // "" | .[0:70])"' \
  > "$SNAP/新仓扫描.txt" || echo "(gh 扫描失败，跳过)"

echo "== 4/4 完成 =="
echo "快照: $SNAP  报告: $SNAP/监控报告.md  新仓: $SNAP/新仓扫描.txt"
