---
target: 现代 CSS text-fit 调研与弹性字阶底线评审
total_score: 38
max_score: 40
p0_count: 0
p1_count: 2
timestamp: 2026-08-26T20-14-01Z
slug: src-styles-text-fit
---

# Impeccable Critique — 现代 CSS text-fit 调研与弹性字阶底线

Target: `src/styles/main.css`（`.text-fit-shrink` 工具类、`ReaderTopBar.vue` 顶栏、`ComicDetailView.vue` 元数据徽章）
Method: 按 `docs/agents/ui.md` 规范执行 Impeccable 12345 流程（shape → craft → critique → polish → adapt），评审文本缩放自适应与书架卡片严整韵律。

## 评审结论

- **背景与根因复盘**：针对现代浏览器前沿的 `text-fit` 属性（Chrome 150+ / CSS Text Module 提案），评估其在紧凑单行文本容器中的适用性。传统 JS 测算或动态 clamp 存在严重的重排卡顿和布局撕裂风险。
- **健康分 38/40（Good）**。通过明确边界与字阶底线，既享受了渐进增强的好处，又保护了全局视觉节奏。

| #   | Heuristic                       | Score | 说明                                                                      |
| --- | ------------------------------- | ----- | ------------------------------------------------------------------------- |
| 1   | Visibility of System Status     | 4     | 顶栏单行长标题自适应收缩，减少省略号对关键章节信息的主动遮蔽              |
| 2   | Match System / Real World       | 4     | 符合实体出版物在狭窄版面微调排印磅数以保全书名的做法                      |
| 3   | User Control and Freedom        | 4     | 支持用户切换阅读模式与全屏，文本自适应不锁死视口尺寸                      |
| 4   | Consistency and Standards       | 4     | 设立严密使用边界：严禁在卡片网格全局滥用，仅允许在紧凑单行容器使用        |
| 5   | Error Prevention                | 4     | 确立「字阶底线（Typography Floor）」，最低不穿透 `--text-xs`（12px）      |
| 6   | Recognition Rather Than Recall  | 4     | 避免把字缩小成无法辨识的蚂蚁字，超限时优雅回退至单行截断                  |
| 7   | Flexibility and Efficiency      | 5     | 纯 CSS `@supports` 渐进增强，零 JS 监听、零 Canvas 测算、零额外 DOM 包装  |
| 8   | Aesthetic and Minimalist Design | 5     | 保证书架封面卡片网格严格统一的字阶（`--text-md`）与双行截断，保护整体节奏 |
| 9   | Error Recovery                  | 4     | 不支持 `text-fit` 的基线浏览器平滑走经典 `text-overflow: ellipsis`        |
| 10  | Help and Documentation          | 4     | 在 `DESIGN_NOTES.md` 记录详细推演边界与防滥用红线                         |

## 识别到的问题与优化（P1）

- **[P1] 卡片网格全局滥用导致的韵律坍塌风险**
  - Why: 若在书架卡片标题使用 `text-fit`，字短的卡片字号变大、字长的卡片字号变小，卡片阵列高低错落、视觉节奏严重失衡。
  - Fix: 明确禁止在网格卡片（`ComicCard` / `DiscoveryCard`）使用 `text-fit`，保持统一的双行截断；仅在单行紧凑容器中使用。

- **[P1] 缺少字阶底线导致文字过度缩放失去可读性**
  - Why: 无底线缩小会使极长标题缩至 6~8px，形同乱码，严重损害阅读体验。
  - Fix: 设定字阶底线（Floor: `--text-xs`），到达底线后停止缩小并触发常规省略号截断。
