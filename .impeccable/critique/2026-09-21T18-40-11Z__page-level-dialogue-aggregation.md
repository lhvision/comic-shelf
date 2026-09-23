---
timestamp: 2026-09-21T18-40-11Z
slug: page-level-dialogue-aggregation
---

# 台词检索结果页级聚合（Page-Level Dialogue Aggregation）独立评审与打磨快照

> **目标对象**：
>
> - `src/components/library/DialogueSearchPopover.vue`
> - `src/types/index.ts`（`DialogueSearchItem` / `DialogueSearchResponse`）
> - `src/composables/useDialogueSearch.ts`
> - `backend/app/db.py`（`search_dialogues`）、`backend/app/models.py`
>
> **变更本质**：检索展示粒度从「气泡级」升级为「页级」。FTS5 一行 = 一个 OCR 气泡，
> 搜高频词时同页多个命中气泡并排刷屏；后端改为按 `(source, source_id, page_index)`
> 聚合，一行 = 一页，展示该页 bm25 最高的「代表句」，新增 `bubble_count`。
>
> **双轨执行**：
>
> - A 轨（独立设计总监 Subagent，两轮）：Nielsen 10 项可用性、认知负荷、可及性
> - B 轨（机器确定性规则扫描）：`pnpm detect:slop` → 两轮均返回 `[]`

---

## 📊 一、设计评分与健康度（A 轨独立总监）

**首轮评分**：**24 / 40**（Acceptable · 需实质性整改，P0 无 / P1 两项 / P2 四项）
**复审评分**：**29 / 40**（Good · 可收口，但明确禁止宣布「P1 全清」）

> 复审提出的两处「补两刀再收」已在本轮落地（见第三节），但**未做第三轮重新打分**，
> 因此 29/40 是本轮记录的最终分数，不按修复后自行上调。

---

## 🚨 二、首轮缺陷与修复闭环

### 1. [P1] 「N 处命中」在无排序的 LIKE 兜底路径上是虚假精确

- **现象**：`search_dialogues` 的 LIKE 兜底不只在 2 字短词时触发，`MATCH` 返回 0 行时也会
  落进去（trigram 索引存不下 2 字气泡）。该分支无 `ORDER BY`，候选池是按行号截取的任意
  `fetch_limit` 行。此时 `bubble_count` 与「该页真实命中数」可能相差很远，代表句也只是任意一行。
- **修复**：`db.py` 新增 `ranked` 标志（仅 MATCH 分支且有结果时置真）；`ranked` 为假时在返回前
  从每个页级 dict 中 `pop("bubble_count")`，即该路径整个不上报计数。

### 2. [P1] 点击后契约断裂、零预期管理

- **现象**：面板标「N 处命中」，进阅读器只高亮代表句那一格（多气泡高亮已有意拆到 2B）。
  底栏原文案「进入阅读器自动朱砂金墨高亮」反而强化错觉。
- **修复**：底栏改为「上下键选择 · 回车直达画页 · 阅读器高亮该页代表台词」；命中数 span 加
  `hitCountTitle()` 生成的 `title`；顺带清掉 `↑↓` 这组 Unicode 伪箭头（AGENTS 红线 12）。

### 3. [P2] `.head-badge` 裸数字会被读成「条数」，且三元永久死

- **现象**：`routers/search.py:61` 是 `total=len(results)`，`total > results.length` 恒假。
- **修复**：删死三元，改为 `命中 N 页`，把单位显式说清。

### 4. [P2] 命中数是本轮唯一新增信号却视觉权重最低

- **修复**：`.meta-hit { color: var(--accent-strong); font-weight: 600 }`。刻意不加底色，
  避免与 `.page-tag` 抢层级。实测对比度亮色约 5.9:1、暗色约 7:1，AA 通过。

### 5. [P2] `useDialogueSearch.ts` 的 `limit` / `total` JSDoc 语义未跟上页级化 → 已改「页」。

### 6. [P2] spec 未覆盖「单命中 + 无作者 → 整个 `.item-meta` 行消失」→ 已补该用例与

`.head-badge` 文案断言。

---

## 🔍 三、复审抓出的「修复本身造成的缺陷」（两项，均已闭合）

### A. `pop` 在 HTTP 边界被响应模型补回默认值

`models.py` 原写 `bubble_count: int = 1`（必填带默认），`routers/search.py` 用 `response_model`
重新校验 → db 层 `pop` 掉的字段被**补回 1**。前端恰好在 `1 > 1` 为假才没出事，但「缺失即不可信」
这个契约口径在 API 层是假的，且 db 层单测根本抓不到。

- **修复**：`models.py` 改 `bubble_count: int | None = None`；TS 侧改 `bubble_count?: number | null`
  并把注释从「不返回」纠正为「不可信时为 `null`」。
- **锁死**：`test_page_level_aggregation` 新增 `DialogueSearchItem(**row).model_dump()` 断言，
  分别钉住「相关度路径计数为 3」与「LIKE 路径过模型后仍为 `null`」。

### B. `title` 是鼠标专属，键盘 / 读屏 / 触摸拿不到预期管理

「N 处命中 → 只画 1 格」的落差对这三类用户依旧存在，且读屏会把无保留条件的「3 处命中」直接念出来。

- **修复**：新增 `#dialogue-hit-note`（`.visually-hidden`，`main.css` 既有工具类），span 挂
  `aria-describedby`；`title` 保留给鼠标。该说明节点刻意放在 `.results-list` **之外**——
  `role="listbox"` 内只允许 `role="option"` 子节点。
- 同时移除 `.meta-hit` 的 `cursor: help`（与行的 `cursor: pointer` 竞争，触摸端无效）。

---

## ⚖️ 四、有意取舍与本轮欠的债

- **一行一页 + 点进去只画代表句一格**：产品负责人拍板，2B 再做多气泡高亮。本轮补的是诚实预告，
  不是消除落差。
- **`bubble_count` 是候选池内计数**，非全库该页命中总数。要做全得对 `MATCH` 集再扫一次
  `GROUP BY`，代价不值。已写入后端 docstring 与 `CONTEXT.md`。
- **`total` 达 `limit` 截断时，「命中 N 页」仍是 over-claim**（N 是返回页数不是命中总页数）。
  留作 P2，择机改「显示 N 页」。
- **LIKE 兜底路径的代表句与排序本身仍未治**——那是第 3 步（两字词出路：查询改写 / 结果缓存 /
  热词 bigram）的正题，本轮只做到了「不谎报」。

---

## ✅ 五、验证记录

| 门禁          | 命令                                                                                   | 结果                                  |
| ------------- | -------------------------------------------------------------------------------------- | ------------------------------------- |
| 后端全量      | `bash scripts/test_py.sh`                                                              | EXIT=0                                |
| 台词 FTS      | `.venv/bin/python backend/tests/test_dialogue_fts.py`                                  | 6 组全通过                            |
| 前端相关 spec | `vp test` Popover / useDialogueSearch / WebMCP / useReaderBubble / ReaderBubbleOverlay | 37 passed                             |
| Vue 模板类型  | `pnpm type-check`（vue-tsc --build）                                                   | 0 error                               |
| 静态检查      | `vp check`                                                                             | 414 files formatted / 0 lint / 0 type |
| B 轨 slop     | `pnpm detect:slop src/components/library/DialogueSearchPopover.vue`                    | `[]`                                  |

> `pnpm type-check` 在这一轮抓到了 `vp check` 漏掉的真实错误（`:title` 里 `item.bubble_count - 1`
> 不被 `?? 1` 收窄，TS18048）。两个门禁覆盖面不同，不可互相替代。
