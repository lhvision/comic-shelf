# ADR 0004 — 现代浮层体系基于 Popover API 与 CSS Anchor Positioning 规范演进

- **日期**：2026-08-27
- **状态**：Accepted

## 背景

在纸间当前的 UI 体系中：

1. `Modal.vue` 采用手动 `Teleport to body` + VueUse 锁滚动 + 手写 Tab 焦点圈闭；
2. `Tooltip.vue` 虽然已引入 CSS Anchor Positioning 初级属性，但缺乏 `popover="hint"` 顶层管理，且缺乏 `@container anchored(fallback)` 箭头自适应反转；
3. `ThemeSelect.vue` 与操作栏「更多 ⋯」菜单均采用分散的手写绝对定位 + 手写全局 `click` 监听；
4. 选项卡与分段标签（`SegmentedTabs.vue`）缺乏流畅的物理滑动跟随质感。

社区传统做法通常引入 Popper.js 或 Floating UI 等重型第三方定位库（通常增加 10~30KB gzip 体积与大量 JS 计算胶水）。

## 决策

建立**纸间现代浮层体系（Modern Floating System）**，作为全站弹出、下拉与提示的标准基础设施：

1. **三层正交组件设计**：
   - `AppTooltip.vue`（轻量提示）：优先采用 `popover="hint"` + CSS Anchor 定位 + 容器查询回退检测 `@container anchored(fallback: flip-block)` 自适应反转箭角，非互斥顶层展示；
   - `AppPopover.vue`（通用富浮层）：基于 HTML `popover="auto"` + CSS Anchor，提供标准 Top-layer 与原生失焦关闭（Light Dismiss）；
   - `AppDropdown.vue`（操作选单/下拉列表）：基于 `AppPopover` 封装，提供完整的键盘无障碍（上下箭头/回车/Esc）、勾选指示以及动态 Anchor 滑动高亮。
2. **渐进增强（Progressive Enhancement）策略**：
   - 现代浏览器环境全走原生 Top-layer 与纯 CSS Anchor 定位，零 JS 坐标重算；
   - 在不支持 `interestfor` / `popover="hint"` 的环境中，通过 VueUse（`useElementHover` / `onClickOutside`）与 `@supports not` 绝对定位无缝回退，确保 100% 坚固可用；
   - 拒绝引入第三方 Floating 库，坚守零新增外部依赖底线。
3. **视觉与滑动动效**：
   - 全面遵守纸间「私人阅览室 / 物理纸质印刷」设计语言，所有边距、色彩、阴影、圆角收敛至 `tokens.css`；
   - 在 `SegmentedTabs.vue` 与下拉选单中落地 CSS Anchor 动态滑动胶囊指示器，获得流畅物理滑动动效。

## 后果

- **正面收益**：
  - 彻底终结 z-index 层级冲突与父级 `overflow: hidden` 裁剪痛点；
  - 减少大量的 JavaScript DOM 监听与坐标计算胶水代码；
  - 统一全站下拉与气泡体验，符合 W3C 规范与 a11y 标准。
- **注意事项**：
  - 弹窗与微交互仍严格遵守 `AGENTS.md` Rule 8，使用 Vue 原生 `<Transition>`，杜绝根容器快照导致的模糊；
  - Popover ID 与 Anchor Name 在组件内必须使用 `useId()` 保证全局唯一防冲突。
