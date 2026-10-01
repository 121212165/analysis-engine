# analysis-engine

基于 gh-deep-search 方学的 GitHub 赛道「搜索 → 富化 → 评分 → 报告」引擎。纯 Python 标准库，零第三方依赖。

计划源：`C:\Users\lenovo\Doubao\chats\2026-10-01\new-chat\analysis-engine-plan.md`（豆包起草，已按评审意见修正——技术路径改 REST 直连、去掉 dependents、commits 默认关、两遍评分、并发降 2）。

## 用法

```bash
python cli.py "写小说|网文|AI novel"                    # 默认赛道地图场景
python cli.py "obsidian plugin" --scenario picking      # 选型推荐场景（重维护性+license）
python cli.py "kg" --min-stars 100 --language python    # 限定符
```

产物在 `output/<run>/`：`report.md`（中文人读）+ `data.json`（机器）+ `meta.json`（参数与迭代过程）。

## 链路

1. **采集** `search.py`：多词 × 四通道（短语/泛搜/正文/赛道）→ 挖词（topics 频次，滤噪声+排除已搜）→ 迭代 → 止损（新发现 <30%）
2. **富化** `enrich.py`：每仓 5-6 个请求（meta/releases/issues 90d/contributors/readme 全文），并发 2 + 礼貌间隔，单信号独立容错
3. **评分** `signals.py` + `score.py`：5 信号（activity/maintenance/community/adoption/license）全部可溯源（evidence 记录原始字段）；relevance 通道加权 × quality → overall
4. **交付** `report.py`：Top N 事实+信号+证据、完整候选池、API 用量声明
5. **缓存** `cache.py`：SQLite 请求级缓存（12h TTL），重复运行零新增调用

## 关键设计决策（踩坑实证）

- **富化谁由两遍评分决定**：先按 relevance 预排序再富化 Top enrich_limit，否则富化的是插入顺序前 N 仓、排行榜头部反而没数据
- **并发 4 会触发 GitHub 次级滥用检测**（实测等了 600s）：降到 2 + 每请求 0.3-0.8s 抖动间隔；次级限制无 reset 时间，等 60s 而不是等核心配额重置
- **commits_90d 默认关**：commit 计数用 Link header rel=last 技巧虽是单请求，但 `--commits` 打开后富化预算翻倍；push 衰减 + issue 处理率已够用
- **adoption 用池内分位数**：GitHub dependents 无官方 REST，跨赛道比 star 会失真

## 测试

```bash
python -m unittest discover -s tests   # 18 个离线单测（伪造 client，零网络）
```
