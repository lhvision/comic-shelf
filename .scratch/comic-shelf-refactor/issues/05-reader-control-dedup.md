# 05 — 阅读器控件样式去重（.reader-btn / .segmented 收敛）

**What to build:** `ReaderTopBar` 与 `ReaderSettingsPanel` 各自重复了
`.reader-btn`（以及面板内 `.segmented`/`.switch`/`.mode-card` 等）的整套样式。
把阅读器控件基础样式收敛到一处共享来源（如 `src/components/reader/reader.css`
或提取 `ReaderButton` 小组件），两处引用同一实现，消除漂移隐患。

**Blocked by:** None — 可以立即开始（拆分已完成，纯样式收敛）。
**Status:** ready-for-agent

- [ ] `.reader-btn` 不再在两个组件里各写一份（任意方案：共享 css / 小组件）
- [ ] 视觉无回归：阅读器顶栏与设置面板按钮外观一致
- [ ] `vp check` 通过

## 相关评审上下文

critique 29/40 一致性（H4）与 Minor：ReaderSettingsPanel 重复
.reader-btn/.segmented，已是漂移隐患。
