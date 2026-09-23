---
timestamp: 2026-09-21T20-29-46Z
slug: step2b-sibling-bubble-outlining
---

# 同页多气泡一次描全（2B Sibling Bubble Outlining）独立评审与打磨快照

> **目标对象**：
>
> - `src/composables/useReaderBubble.ts`（`bubble_boxes` 解析/序列化、`TargetBubble.others`、封顶常量）
> - `src/components/ReaderBubbleOverlay.vue`（`.reader-bubble-ghost` 描边层、`ghost-mark`、aria 口径）
> - `src/components/library/DialogueSearchPopover.vue`（`hitCountTitle`、底栏、读屏说明）
> - `src/composables/useDialogueSearch.ts`、`src/composables/useShelfWebMCP.ts`、`src/types/index.ts`
> - `backend/app/db.py`（`other_boxes` 聚合与 `MAX_PAGE_BOXES` 封顶）、`backend/app/models.py`
>
> **要还的债**：上一轮把检索展示粒度改成页级后，浮层标「N 处命中」、点进阅读器只画 1 格。
> 上一轮 A 轨连提两次，当时仅用文案做预期管理，未真正解决。本轮落地。
>
> **双轨**：A 轨独立设计总监 Subagent 两轮（首轮 24/40 → 复审 33/40）；
> B 轨 `pnpm detect:slop` 对两个组件均返回 `[]`。

---

## 📊 评分

**首轮**：**24 / 40**（Acceptable，P0 无 / P1 三项 / P2 两项）
**复审**：**33 / 40**（状态可见 4、承诺一致性 3、防错 3、美观极简 3）

---

## 🚨 首轮缺陷与修复闭环

### [P1-1] 本轮自己引入的回归：watch 回调按位置解构

`useReaderBubble.ts` 的 watch 源数组在 index 1 插入 `bubble_boxes` 后，回调仍写
`([box, b1, b2])`，`highlight_bubble` 被挤出触发条件——`?page=42&highlight_bubble=1` 这条
无 box 的遥控 URL 会渲染出基准假框却**永不自愈、参数永不擦除**。

- **修复**：回调改为 `const q = route.query; if (q.bubble_box || q.bubble_boxes || q.bubble || q.highlight_bubble)`
  按名读取，并加注释禁止位置解构。
- **反证**：把回调退回 `([box, b1, b2])`，新增用例
  `auto-dismisses a highlight_bubble-only URL that carries no bubble_box` 立即变红
  （`expected { page: 42, box: [...] } to be null`），装回则绿。
- **根因判词**（复审语，采信）：这是「把 `others` 塞进 `TargetBubble` 复用透传链」这类隐式耦合的
  现世报。收益是 `useReaderInteraction` / `useReaderHydration` / `ReaderViewport` 三处零改动，
  代价是处处要记得字段存在。

### [P1-2] 上一轮的诚实文案被本轮变成虚假陈述

「阅读器仅高亮代表句那一格」等三处措辞与本轮行为直接矛盾；覆盖层 ariaLabel 又用
`others + 1` 冒称命中数（封顶后 6≠8），契约断裂只是从 `1/N` 缩小成 `6/N`。

- **修复**：① 覆盖层只报「同页一并描出 N 处气泡」，不冒用 `bubble_count`；
  ② `hitCountTitle()` 按 `Math.min(bubble_count, MAX_HIGHLIGHT_BOXES)` 出两种句式；
  ③ 底栏改「阅读器描出该页命中气泡」；④ 读屏说明插值 `MAX_HIGHLIGHT_BOXES - 1`；
  ⑤ 同步 `ReaderBubbleOverlay.spec.ts` 与 `DESIGN_NOTES.md` §64-5 / §62 新块。

### [P1-3] 描边压在暗场等于没画

1px `--accent` 45% 在深色场 / 密网点上对比不足，而本轮交付物就是「画全」，看不见即未交付。

- **修复**：提到 70%，外加 `box-shadow: 0 0 0 1px rgb(0 0 0 / 55%), inset 0 0 0 1px rgb(255 255 255 / 40%)`
  双色对比键线。这两道**刻意不随主题翻转**——它们要对的是漫画图片，不是纸面 UI。

### [P2-①] 前端无段数上限

`parseBubbleBoxes` 不夹、MCP schema 只有声明性 `maxItems`，手改 URL 或 MCP 投喂 200 段即画 200 框。

- **修复**：新增前端共享常量 `MAX_HIGHLIGHT_BOXES = 6`（注释绑定后端 `MAX_PAGE_BOXES`），
  `parseBubbleBoxes` 与 `serializeBubbleBoxes` **双侧对称** `slice(0, 5)`，schema 补 `maxItems: 5`。
  序列化侧也夹是复审追出来的：只夹解析端，MCP 仍能拼出「画面封顶、地址栏不封顶」的超长 URL。

---

## ⚖️ 本轮明确记下的欠债（未修）

1. **动效字面量 2.2s / 2.0s / 2.8s 散落三处**，违反「动效走 tokens」红线。属既有债务，本轮只新增了
   `ghost-mark 2.2s` 一处实例，未做收敛。
2. **`bubble_count` 是候选池内计数**，极端高频页会少报。本轮把「至少」口径收进 `hitCountTitle`
   的 title 详情面，行内徽标仍保持简洁。
3. **`hitCountTitle` 的「全部描出」分支隐含代表格 box 有效**：若全部坐标畸形，画面一格不描而
   title 已作承诺。边缘场景，未处理。
4. **程序性硬伤（复审当场抓到）**：首轮修复后未重跑 `vp check` 就宣称门禁全绿，`DialogueSearchPopover.vue`
   确有格式化违例。已补跑并 `--fix`，此条记为流程教训——**polish 之后必须重跑门禁，不能沿用修复前的绿灯**。

---

## ✅ 验证记录

| 门禁                         | 结果                                  |
| ---------------------------- | ------------------------------------- |
| `vp check`                   | 416 files formatted / 0 lint / 0 type |
| `pnpm type-check`（vue-tsc） | 0 error                               |
| `vp test` 6 个相关 spec      | 57 passed                             |
| `bash scripts/test_py.sh`    | EXIT=0                                |
| `pnpm detect:slop` ×2 组件   | 均 `[]`                               |
| 反证 P1-1                    | 退回位置解构 → 用例红；装回 → 绿      |
| 反证封顶                     | 20 段洪水 URL 解析与序列化均只余 5 组 |
