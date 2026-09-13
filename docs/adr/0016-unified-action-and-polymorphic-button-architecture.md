# ADR 0016 — 统一操作与多态按钮架构（AppButton Architecture）

- **日期**：2026-09-11
- **状态**：Accepted
- **关联**：扩充 `CONTEXT.md` 基础设施「标准操作与多态按钮（AppButton）」，演进 `DESIGN_NOTES.md` §3.7，关联 `docs/PITFALLS.md` 避坑条目

## 背景

在纸间（Paper Room）的早期演进中，前端定义了基础按钮组件 `AppButton.vue`，但在多个业务视图（详情页、章节页、书架流式折叠卡、画卷余页收整条、模态弹窗）中，存在严重的实现割裂与反模式：

1. **同态未归一化（CSS 类名裸写）**：多达 29 处业务按钮直接手写原生 `<button class="btn btn-primary">` 或 `<button class="btn btn-ghost">`，未复用 `AppButton` 的状态绑定、无障碍和加载态逻辑；
2. **独立图标按钮碎片化**：返回上一页、模态框关闭、封面轮播箭头、识图相机等 7 处图标按钮散落使用 `<button class="* icon-btn">`，缺少正圆/方形外观与标准化尺寸映射；
3. **多态路由跳转断层**：当视觉表现为按钮但底层为路由跳转（如 `DiscoveryCard` 的「已在书架 · 详情」）时，开发者被迫直接编写 `<RouterLink class="btn btn-success ...">`，绕开了组件封装；
4. **阅览室暗室高对比度缺乏系统级支撑**：阅读器末页等纯暗室场景（`--reader-bg`）需要高对比度防御（WCAG AA 级），此前依赖业务组件局部手写私有 CSS 选择器覆写 `.btn-ghost`，容易发生样式泄漏与遗漏；
5. **无障碍隐患**：纯图标按钮经常漏写 `aria-label` 或 `title`，给读屏器用户造成空文本按钮盲区。

## 方案论证与权衡（Grilling Analysis）

围绕按钮收敛的边界、多态性、图标契约与主题防护，团队展开了针对性推演：

### 1. 归一化治理范围与边界

- **路线 A（仅治理同态文字按钮）**：仅将裸写 `class="btn btn-*"` 的 29 处操作按钮替换为 `AppButton`，图标按钮维持原样。
  - _否决理由_：全站 7 处核心图标按钮（返回、关闭、轮播箭头、相机）仍处于无统筹状态，未能解决图标组件尺寸、动效与无障碍统一的问题。
- **路线 B（标准按钮 + 图标按钮双轨收敛，推荐）**：
  - _实现原理_：在 `AppButton` 中增加 `shape?: 'default' | 'circle' | 'square'` 与 `icon?: IconName` 属性；标准操作按钮与独立正圆/方形图标按钮统一通过 `AppButton` 消费；
  - _特化微件边界与最终收敛_：严格区分通用按钮与特化领域控件：`AppChip.vue`（多态状态药丸）、`archive-drawer-header`（具备 `aria-expanded` 的 Disclosure 折叠标头）维持独立职责；而历史上的特化沉浸阅读工具栏按钮 `ReaderButton.vue` 已在后续治理中全面收敛并物理删除，由 `<AppButton theme="reader">` 原生统一承担。

### 2. 多态渲染与禁用态拦截

- **路线 A（坚守纯 button 标签）**：`AppButton` 仅渲染 `<button>`，链接场景使用单独的 `<AppLinkButton>` 或手写样式类。
  - _否决理由_：增加学习成本与胶水组件，破坏开发体验。
- **路线 B（组件内置多态自适应，推荐）**：
  - _实现原理_：若传入 `to` 属性自动以 `<RouterLink>` 渲染；若传入 `href` 自动以 `<a>` 渲染；否则渲染原生 `<button>`。
  - _禁用拦截防卫_：因 `<RouterLink>` 和 `<a>` 原生无 `disabled` 属性，当处于 `disabled` 或 `loading` 时，通过 `aria-disabled="true"`、`tabindex="-1"`、`event.preventDefault()` 与 `event.stopPropagation()` 进行全链路语义与事件拦截，保持 DOM 节点标签稳定且防止非预期导航。

### 3. 图标契约、位置流向与无障碍安全护栏

- **属性与插槽双轨制**：传入 `icon` 且默认插槽为空时，自动进入紧凑居中的纯图标模式（4 档标准尺寸：28px / 32px / 40px / 48px）；
- **图标流向（`iconPosition="left" | "right"`）**：支持前缀与后缀图标快速声明，自动计算自适应尺寸，消除为了按钮图标而手写 `<template #suffix><AppIcon ...></template>` 的样板代码；
- **消除无用引入（Dead Imports Elimination）**：借助 `icon` 与 `iconPosition`，成功在全站 9 个业务组件中彻底删除了原本仅为了按钮而存在的 `import AppIcon`；
- **开发环境运行时门禁**：在 `import.meta.env.DEV` 下，对缺少 `aria-label`、`title` 或 `aria-labelledby` 的纯图标按钮触发 `console.warn` 拦截，杜绝 WCAG 4.1.2 可访问性缺陷。

### 4. 阅读器暗室主题（`theme="reader"`）

- 在 `AppButton` 内部原生声明 `theme?: 'paper' | 'reader'` 契约；
- 在暗室主题下，`ghost` 变体自动绑定 `--reader-surface-strong`、`--reader-ink` 与 `--reader-line-strong`，悬浮态提升至 `--reader-surface-hover`，彻底消除各视图中手动 `:deep(.btn-ghost)` 的私有覆写补丁。

## 核心决策

1. **统一组件真理源**：`src/components/AppButton.vue` 作为全站交互按钮的唯一入口，全面支持 `primary` / `secondary` / `ghost` / `soft` / `danger` / `success` 六色变体；
2. **多态与图标支持**：支持 `to`（Vue Router）与 `href` 外链多态切换；支持 `shape="circle" | "square"` 独立图标模式以及 `iconPosition="left" | "right"` 图标流向；
3. **完成全仓 60+ 处深度治理与伪字符净化**：
   - 彻底消除全站 36 处裸写 `.btn-primary`/`.btn-ghost`、独立 `.icon-btn`；
   - 深挖治理了 访客簿（`GuestCard`、`GuestDeviceList`、`GuestSuccessVoucher`、`GuestModal`、`GuestIssueTab`、`GuestRosterTab`）；
   - 治理了 PWA 更新、离线重置、回到顶部、工坊跳转、画卷余页等周边按钮；
   - 同步清除 `＋`、`⌕`、`➔` 等 Unicode 伪图标字符；
4. **单测与 E2E 双轨全覆盖**：
   - 编写 `AppButton.spec.ts` 核心契约单测（12 组），覆盖多态、禁用拦截、独立图标形态、后缀图标与暗室主题；
   - 新增 `e2e/tests/button-governance-e2e.spec.ts` 专项端到端测试（4 组全流程），涵盖全局浮层、详情操作栏、自建工坊多章节编排与访客簿完整管理流程，100% 绿灯终验。

## 影响与收益

- **一致性**：全站交互按钮在圆角、网格间距、焦点环（`focus-visible`）、悬浮微位移与禁用光标上达到 100% 视觉对齐；
- **健壮性**：彻底阻断了链接在禁用状态下的误触跳转，杜绝了纯图标按钮缺少读屏标签的无障碍风险；
- **代码精简**：消除了 9 个组件冗余的 `import AppIcon` 引入与样板代码，提升了视图轻量化（View Thinness）。
