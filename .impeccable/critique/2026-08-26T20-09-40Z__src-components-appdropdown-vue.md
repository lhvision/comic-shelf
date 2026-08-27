---
target: 现代浮层体系（AppTooltip / AppPopover / AppDropdown / SegmentedTabs）设计与可用性评审
total_score: 36
max_score: 40
p0_count: 0
p1_count: 2
timestamp: 2026-08-26T20-09-40Z
slug: src-components-appdropdown-vue
---

# Impeccable Critique — 现代浮层体系（Modern Floating System）

Target: `AppTooltip`（`popover="hint"` + Anchor）、`AppPopover`（`popover="auto"` + Anchor）、`AppDropdown`（键盘可访问下拉 / 菜单）、`SegmentedTabs`（CSS Anchor 滑动跟随胶囊）及 `DetailActionBar` / `ThemeSelect`
Method: 按 `docs/agents/ui.md` 规范执行 Impeccable 12345 流程（shape → craft → critique → polish → adapt），结合两轮真实场景截图与浏览器视觉复盘。

## 评审结论

- **grill 与设计系统回顾**：原项目中缺乏统一的浮层基建，`DetailActionBar`、`ChapterView`、`ThemeSelect` 各自手写 `onClickOutside` 与绝对定位，代码冗余且无法穿透宿主 `overflow: hidden`。通过引入 Web 原生 Top Layer（Popover API）与 CSS Anchor Positioning，成功打造零外部三方依赖、轻量且具备原生离焦轻触关闭（Light Dismiss）的现代浮层基建。
- **健康分 36/40（Good）**。各浮层组件正交分层清晰（Tooltip 为单向展示、Popover 为无状态容器、Dropdown 兼顾 Select 与 Action Menu）；键盘导航完整（ArrowUp/Down/Home/End/Enter/Esc）。

| #   | Heuristic                       | Score | 说明                                                                                               |
| --- | ------------------------------- | ----- | -------------------------------------------------------------------------------------------------- |
| 1   | Visibility of System Status     | 4     | Popover 原生伪类 `:popover-open` + `@starting-style` 微动效；选中项高亮与朱砂强调色对齐            |
| 2   | Match System / Real World       | 4     | 符合 OS 原生下拉菜单和提示框行为（ESC 关闭、失焦自闭、滚轮跟随）                                   |
| 3   | User Control and Freedom        | 4     | 完整的键盘快捷键退出（Esc/Tab）与选择（Enter）；无模态焦点陷阱阻碍                                 |
| 4   | Consistency and Standards       | 4     | 全量基于 `src/styles/tokens.css`；边框、阴影、层级统一收敛                                         |
| 5   | Error Prevention                | 4     | 禁用项 `is-disabled` 阻止快捷键激活；危险操作项 `is-danger` 朱砂弱底显眼提示                       |
| 6   | Recognition Rather Than Recall  | 3     | Select 模式下动态展示选中项标签（修复前被静态 `label` 拦截导致用户无法识别当前选中状态）           |
| 7   | Flexibility and Efficiency      | 4     | 支持键盘上下方向键、首尾键导航与快速选择；小屏幕响应式回退                                         |
| 8   | Aesthetic and Minimalist Design | 3     | 修复前纯操作菜单由于无条件预留 `1.25rem` 导致文字怪异居中；修复后自适应剔除前导槽                  |
| 9   | Error Recovery                  | 4     | CSS Anchor 自动边缘反转翻转（`flip-block` / `flip-inline`）；不支持 Anchor 时平滑降级              |
| 10  | Help and Documentation          | 4     | ARIA 语义齐备（`role="listbox/option"` 或 `role="menu/menuitem"`），组件 Props 包含全量 JSDoc 注释 |

## 识别到的问题与优化（P1）

- **[P1] 纯操作菜单文字怪异偏中（DetailActionBar 移除缓存操作）**
  - Why: 先前 `AppDropdown` 无条件渲染 `1.25rem` 前导占位槽，在无勾选/无图标的操作菜单中产生多余空白缩进，与右侧副文本形成拉扯，视觉上显得居中。
  - Fix: 为 `.item-leading` 增加 `v-if="isSelectMode || hasIcons"` 模式判断，非选择模式且无图标时彻底剔除前导槽，文字恢复清爽左对齐。

- **[P1] 首页排序选择后触发按钮文字未更新**
  - Why: `ThemeSelect` 传递的 `label="排序"` 覆盖了 `triggerText` 计算，导致任何选中项切换后按钮仍固定显示 `"排序"`。
  - Fix: 重构 `triggerText`，在 Select 模式下优先展示当前选中项 `selectedOption.label`，`props.label` 仅作为可访问性 `aria-label`。

- **[P1] 更多按钮丢失 `margin-left: auto` 导致排版偏左**
  - Why: `AppDropdown` 错误声明 `inheritAttrs: false`，导致调用方传入的 `.more-menu` 样式类丢失。
  - Fix: 移除 `inheritAttrs: false`，让外部布局类自然透传至根容器生效。

## What's Working

- **Web 标准顶层浮层（Top Layer）**：无任何第三方 Popper/Floating UI 依赖，直接依赖浏览器原生 Top Layer，绝不被任何卡片父级的 `overflow: hidden` 裁剪。
- **CSS Anchor 跟随与反转**：无需任何 JS 帧循环或 resize 监听，浏览器原生处理几何锚定与视口防溢出翻转。
- **SegmentedTabs 跟随胶囊**：采用单伪元素加动态 `anchor-name`，实现 0 JS 算宽、纯 CSS 平滑滑动的分段指示器。
- **无障碍与全键盘支持**：完整支持 WAI-ARIA Listbox / Menu 规范与方向键/Enter/Esc 交互。

## polish（视觉细节打磨）

- 菜单项激活态走 `--accent-soft` 底色 + `--accent-strong` 字色；
- 危险项走 `--danger-soft` 与 `--danger` 朱砂红，副文本统一采用 Mono 紧凑微字 `--text-xs`；
- 浮层容器统一采用 `--paper-0` 与 `--shadow-2` 纸本质感，边框采用 `--line-strong` 保持物理书架层次。

## adapt（多端响应适配）

- 桌面端：CSS Anchor 定位与顶层拓扑；
- 不支持 CSS Anchor 的旧浏览器：自动通过 `@supports not` 降级为相对容器绝对定位；
- 移动窄屏（≤681px）：`.more-menu` 自动去除 `margin-left: auto` 换行平铺，点击菜单具备触控尺寸保护。
