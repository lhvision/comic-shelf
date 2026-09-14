# ADR 0021 — 现代 CSS 架构治理：设计令牌、@property 与原生层叠规范

- **日期**：2026-09-14
- **状态**：Accepted
- **关联**：演进 `DESIGN_NOTES.md` §2 与 §2.5，更新 `docs/CSS_RADAR.md`，对齐 `CONTEXT.md` 设计哲学

## 背景

在纸间（Paper Room）早期的渐进式演化过程中，虽然全局建立了以 `tokens.css` 和 `main.css` 为基础的色彩体系（暖纸色、墨色、朱砂红与 `color-mix(in oklab, ...)`），但随着业务微件与管理界面的快速迭代，样式层出现了若干亟待治理的架构债务与硬编码散落现象：

1. **微距数值散落与魔法值暗疾**：在多个组件（如 `GuestCard`、`GuestDeviceList`、`DialogueSearchPopover`、`ImportConcurrencyStepper` 等）中散落着硬编码的 `2px`、`4px`、`6px` 以及 `0.15rem 0.5rem` 等微观间距；
2. **渐变与数值动效无法被 GPU 合成线程原生插值**：传统的 CSS 自定义属性在浏览器中被解析为任意字符串 Token，无法直接在 `conic-gradient`、`linear-gradient` 的百分比或角度上进行平滑动画插值，以往需要借由 JS `requestAnimationFrame` 轮询或繁复的 DOM 重排模拟；
3. **样式联动依赖繁琐的 JS 胶水状态**：为实现诸如“弹窗打开时页面背景冻结”、“输入框非法高亮”、“卡片复选框选中时边框加亮”等纯展示需求，Vue 组件内部往往堆砌了无意义的响应式布尔状态与事件监听；
4. **原生 CSS 嵌套（CSS Nesting）缺乏工程约束**：缺乏深度的明确上限，容易产生嵌套过深、特异度（Specificity）失控的隐患。

## 方案论证与权衡（Grilling Analysis）

结合 MDN Web Docs 权威兼容性数据（MDN BCD），团队围绕现代 CSS 治理展开了深度论证：

### 1. 样式收敛与提取范式

- **路线 A（纯原子类 / utility 优先）**：在 `main.css` 中大面积手写 utility 类名。
  - _否决理由_：容易破坏纸间 SFC 单文件组件的高内聚性，产生类似 Tailwind 的类名膨胀。
- **路线 B（双轨混合制，推荐）**：
  - 纯排版级样式（布局、网格、卡片结构）收敛到 `main.css` 的 `@layer components`；
  - 微标、芯片、状态指示等语义控件严格复用 `AppChip.vue` 与 `main.css` 现存的 `.badge` / `.pill` 规则。

### 2. 4pt 间距与微距 Token 刚性收敛

- **4pt 阶梯对齐**：全面废除非 Token 偶数像素，严格对齐 `--space-0-5` (2px)、`--space-1` (4px)、`--space-1-5` (6px)、`--space-2` (8px)；
- **微标专属间距**：在 `tokens.css` 中声明 `--space-badge-y: 0.15rem;` 与 `--space-badge-x: 0.5rem;`，使徽章和微缩药丸拥有单源度量。

### 3. `@property` 现代特性落地（Baseline 2024）

MDN 数据显示 `@property` 在 Chrome 85+、Firefox 128+、Safari 16.4+ 均已全面就绪。在纸间“私人阅览室 / 图书馆卡片目录”克制典雅的美学框架下，落地关键场景：

- **`--progress-ratio` (`<percentage>`)**：用于纯 CSS 扇形与环形进度条（`conic-gradient` / `.progress-ring`）平滑过渡，为离线缓存与阅读器加载提供 GPU 级百分比插值能力；
- **`--shimmer-pos` (`<percentage>`)**：用于 120Hz GPU 硬件加速的纸质骨架屏平滑微光，配合对称渐变色标（`calc(var(--shimmer-pos) - 25%)` 至 `calc(var(--shimmer-pos) + 25%)`）形成无拖尾、无停顿的匀速光带，废除昂贵的主线程重排；
- **`--card-glow-color` (`<color>`) 与 `--card-glow-size` (`<percentage>`)**：用于 `DiscoveryCard` 等组件径向渐变（`radial-gradient`）光晕在 Hover 时的平滑色彩与范围插值，解决原生 CSS 无法跨不同 Gradient `<image>` 补间平滑过渡的历史痛点。

### 4. 现代选择器与高级架构

- **`:has()` 与双轨滚动锁（Baseline 2023）**：
  - 在 `main.css` 中使用 `body:has(dialog[open]:not([aria-hidden='true'])) { overflow: clip; }` 实现声明式原生锁屏；
  - 同时在 `Modal.vue` 中保留 `useScrollLock` 作为老旧环境的渐进增强双轨防御；
  - 优化输入框与复合卡片的关联状态选择。
- **CSS Anchor Positioning 原生关键字与 `@position-try` 分层策略**：
  - 首选采用标准 `position-try-fallbacks: flip-block, flip-inline;`，满足绝大多数上下/左右视口越界镜像自适应，消除全局冗余手写规则；
  - 保留 `@position-try` 技术规范与落地范式于 `docs/CSS_RADAR.md` §2.8，供未来非对称避让或特殊方位越界时按需在组件局部声明。
- **原生 CSS 嵌套三层深度定律**：
  - 严格限制原生嵌套深度最大为 3 层（`Block -> Element -> State/Modifier`），锁定特异度权重。
- **CSS Subgrid**：
  - 用于列表与网格卡片（如 `DiscoveryCard`）跨卡片行高刚性对齐。
- **`@scope` 边界守则**：
  - 日常组件坚守 Vue SFC `<style scoped>`；`@scope` 仅作为甜甜圈隔离（Donut Scoping）技术储备，用于富文本与对白插槽防穿透。

### 5. 过渡属性收敛与变量 Fallback 清剿

- **严禁滥用 `transition: background`**：纯色背景必须使用明确的 `transition: background-color`，杜绝触发布局与背景 8 项长写属性的无效重排；渐变背景过渡统一升级为 `@property` 变量插值；
- **清剿硬编码 Fallback Hex**：单源 Token 架构下彻底清除类似 `var(--accent, #b34a36)` 的暗度陈仓式回退，保证主题与 Token 修改时 100% 单源生效。

## 核心决策

1. **Token 单源完备化**：`src/styles/tokens.css` 增加 `--space-badge-y`、`--space-badge-x`、`--radius-pill` 与 `--accent-contrast: #fff8f2;`，并注册 `@property --progress-ratio`、`@property --shimmer-pos`、`@property --card-glow-color` 与 `@property --card-glow-size`；
2. **全局基建增强与死代码清理**：
   - `src/styles/main.css` 注入 `body:has(dialog[open])` 原生声明式锁屏、全局 `@keyframes spin` 以及 `.skeleton-shimmer` / `.progress-ring` 现代组件微光与进度样式；
   - 彻底删除历史遗留废弃类名 `.icon-btn` 及其响应式媒体查询（已被 `AppButton.vue` 统一取代）；
3. **完成存量组件硬编码与散落 Keyframes 清剿**：
   - 彻底治理了各业务组件中的微距硬编码与 4 处重复定义的 `@keyframes spin`（`UpdateBanner`、`GuestRosterTab`、`ImageSearchChip`、`StoragePwaCard`、`AppButton`、`ComicGrid`）；
   - 清除了 `DiscoveryView.vue` 中冗余重复的骨架屏渐变与手写 `@keyframes shimmer`，全面并轨到全局 `.skeleton-shimmer`；
   - 彻底清剿了所有业务组件与样式表中的非 Token 硬编码 Hex 颜色，全站非 `tokens.css` 文件内 Hex 颜色达到 **0 残留**；
4. **组件动效集成**：
   - `AppProgressBar.vue` 注入 `--progress-ratio` 响应式 CSS 变量契约；
   - `DiscoveryCard.vue` 接入 `--card-glow-color` 与 `--card-glow-size` 径向渐变过渡；
   - 全局规范化 `transition: background-color` 与 `transition: all` 的精确属性收敛。
