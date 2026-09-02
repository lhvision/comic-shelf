# 纸间 · Paper Room 设计系统规范与架构基准（Living Design System）

> **文档性质**：纸间设计系统单一真相源（Single Source of Truth）。
> 每次涉及 UI/UX 组件新建、视图重构与视觉打磨前**必读**。
> 历史演进日志（§01 – §52 次迭代记录）已归档至 [`docs/design-archive/MILESTONES_01_TO_52.md`](docs/design-archive/MILESTONES_01_TO_52.md)。

---

## 目录（Index）

1. [设计哲学与品牌隐喻（Design Philosophy & Metaphor）](#1-设计哲学与品牌隐喻design-philosophy--metaphor)
2. [设计系统 Token 契约（Design Tokens System）](#2-设计系统-token-契约design-tokens-system)
3. [核心组件架构与变体规范（Component Architecture）](#3-核心组件架构与变体规范component-architecture)
4. [核心设计红线与避坑定律（Permanent Laws & Anti-Regression Anchors）](#4-核心设计红线与避坑定律permanent-laws--anti-regression-anchors)
   - [§13 Composable 顶层解构定律](#sec-13)
   - [§12 破坏性操作双重防护定律](#sec-12)
   - [§08/§09 多章节全局页码与目录切片体系](#sec-08)
   - [§21 全局 View Transitions API 安全边界](#sec-21)
   - [§31 纸间单源矢量图标集](#sec-31)
   - [§50 全站弹窗与暗室主题隔离](#sec-50)
   - [§51 阅读器滚动驱动动画双轨架构](#sec-51)
   - [§52 视图轻量化与装配树编排](#sec-52)
5. [历史演进里程碑归档索引（Historical Milestones Archive）](#5-历史演进里程碑归档索引historical-milestones-archive)

---

## 1. 设计哲学与品牌隐喻（Design Philosophy & Metaphor）

### 1.1 品牌定位与受众

- **定位**：本地优先的个人私有漫画收藏夹（Personal Quiet Archive）。不是泛化爬虫，不是公开图床，不搞社交推荐。
- **视觉隐喻**：**私人阅览室（Reading Room）+ 图书馆卡片目录（Card Catalog）+ 旧书脊与朱砂印（Vermilion Ink）**。
- **设计基调**：Quiet, Tactile, Archival, Unobtrusive. 界面隐身退后，让位于画卷、封面与目录纸质质感。

### 1.2 显式禁止清单（Anti-Patterns & Slop Redlines）

- ❌ **严禁紫色渐变 / 霓虹极光**（严禁 AI 高频模板默认的紫蓝渐变背景与发光描边）；
- ❌ **严禁玻璃拟态堆叠**（严禁全屏滥用重度 `backdrop-filter: blur` 造成文字亚像素发虚与层次混乱）；
- ❌ **严禁 Unicode 伪字符 / Emoji 当图标**（严禁 `'✕'`, `'✓'`, `'×'`, `'⋯'`, `'←'`, `'→'` 或手写内联 SVG，全站统一基于 `src/components/icons/` 矢量单源扩展）；
- ❌ **严禁无节制的巨型圆角胶囊**（限制为系统统一的 4 档 Radius 规范）；
- ❌ **严禁无意义的英文 Eyebrow 标签**（如在主标题上生硬堆砌小写灰色英文造成视觉噪音）；
- ❌ **严禁引入第三方重量级轮播库**（轮播统一采用原生 CSS `scroll-snap` 实现）。

---

## 2. 设计系统 Token 契约（Design Tokens System）

所有样式必须严格收敛至 `src/styles/tokens.css`，禁止在组件中书写非 Token 魔法值：

### 2.1 色彩体系（Color Palette）

- **纸张底色（Paper）**：`--paper-0`（纯白卡片）、`--paper-1`（暖纸底色）、`--paper-2`（深层纸背）、`--paper-warm`（泛黄书页质感）；
- **墨色层级（Ink）**：`--ink-0`（主标题浓墨）、`--ink-1`（正文浓淡）、`--ink-2`（次要信息与元数据淡墨）、`--ink-3`（边框淡墨与分割线）；
- **品牌点缀（Accent）**：`--accent`（朱砂朱红 `oklch(0.59 0.17 38)`）、`--accent-soft`（朱砂印泥淡底）、`--accent-strong`（深朱砂选中态）；
- **状态感知（Status）**：`--success`（松石绿已缓存/就绪态）、`--danger`（朱红警示与危险操作）、`--line`（纸质装订压痕线）；
- **阅览室暗室（Reader Dark Room）**：`--reader-bg`（纯黑暗室底）、`--reader-panel`（暗调磨砂控制面板）、`--reader-text`（防刺眼高对比柔白）。

### 2.2 间距与字阶体系（Spacing & Typography）

- **4pt 黄金网格**：间距全部采用 `--space-1` (4px) 至 `--space-12` (48px)，禁止奇数 margin/padding；
- **字体分工**：
  - **标题与典藏名**：Serif Display（衬线体，营造书籍装订典雅感）；
  - **正文与控件**：Sans-serif（高可读性现代无衬线体）；
  - **页码与统计元数据**：Monospace 等宽字体（如 `01 / 24 P`，保证排版整齐不抖动）。

### 2.3 动效与触控底线（Motion & Touch Floor）

- **时长与缓动**：动效时长仅限 `--duration-1` (150ms)、`--duration-2` (250ms)、`--duration-3` (400ms)；缓动曲线使用 `--ease-out` 与 `--ease-spring`；
- **无障碍降级**：所有 CSS 动画与 View Transitions 必须对 `prefers-reduced-motion: reduce` 进行静默降级；
- **触控底线**：移动端与平板触控热区严格保证 **≥ 44×44px**（可通过负 margin + padding 扩充触控区）。

### 2.4 响应式断点（Breakpoints）

- **桌面视口（> 960px）**：1200px 居中容器，双栏卡片与大网格布局；
- **平板视口（681px ~ 960px）**：单栏自适应，目录与详情纵向排布；
- **移动视口（≤ 680px）**：紧凑单列排布，顶部导航栏简化，阅读器强制归一化为单列（`pagesPerView = 1`）；
- **超窄抽屉（≤ 480px）**：弹窗自动切换为底部抽屉贴边形态。

---

## 3. 核心组件架构与变体规范（Component Architecture）

### 3.1 弹窗与浮层分层（Modal & Floating Hierarchy）

1. **通用业务弹窗（`Modal.vue`）**：
   - 变体属性 `variant="paper" | "reader"`：`paper` 为典藏纸张亮色主题，`reader` 为阅读器暗室模式（深底、无亮白水印、高对比焦点环）；
   - 尺寸属性 `size="sm" | "md" | "lg" | "xl"`（适配简单确认至多字段大面板）；
   - 水印开关 `watermark: boolean`（纸间默认开启，暗室默认关闭）；
2. **系统安全门禁（`GateView.vue` & `src/components/gate/`）**：
   - 根级 Zero-DOM 物理隔离大门，挂载 `MutationObserver` 反 DevTools 篡改哨兵，三态表单（口令/首次认领设 PIN/已认领输 PIN）模块化收敛；
3. **轻量浮层与 Popover（`Popover.vue` / `Tooltip.vue`）**：
   - 基于 HTML Popover API + CSS Anchor Positioning（`anchor-name` / `position-anchor`）构建；
   - 具备 `@supports not (anchor-name: ...)` 绝对定位回退与 WCAG 1.4.13 悬停安全桥（Hover Bridge）保护。

### 3.2 矢量图标单源契约（Unified Iconography）

- 全站图标统一收敛至 `src/components/icons/`（如 `IconClose.vue`, `IconCheck.vue`, `IconArrowLeft.vue`, `IconBookmark.vue`）；
- 所有图标原子组件基于 `BaseIcon.vue`（规范 `size="1em"` 与 `viewBox="0 0 24 24"`）；
- 严禁在模板中内联书写未封装的 SVG 或 Unicode 字符。

### 3.3 视口渲染性能与预算（Rendering Budget）

- **书架 48 图预算（Shelf 48-Cover Budget）**：首页每本漫画包含 4 张展示封面（1 主封面 + 3 叠牌封面），采用 12 本/批（严格对应 12 × 4 = 48 张封面图）的增量渲染机制（VueUse `useIntersectionObserver` 监听底部哨兵）；
- **详情页 48 页切片（Detail Index Chunking）**：详情页缩略图按 48 页增量展开，避免千页巨作一次性阻塞主线程；
- **Canvas 重绘防抖（Canvas Redraw Debounce）**：Canvas 卡片采用 `redrawKey` + 80ms 防抖调度，消除高频进度重绘带来的掉帧。

### 3.4 现代进度条与拟真加载体系（Progress Bar System）

- **统一原子组件（`AppProgressBar.vue`）**：收敛全站进度条形态（`track` 3px 药丸槽 / `line` 3px 贴边细线 / `gauge` 6px 标尺槽）；
- **双轨渲染架构**：以 CSS Custom Property `--progress: 0~1` 与 `--value / --max` 驱动 GPU 合成层 `transform: scaleX(...)`，并在现代浏览器中渐进增强为原生 CSS `progress()` 数学函数，实现零 Reflow 开销；
- **拟真未定态（Indeterminate Mode）**：结合 `--ease-progress`（`cubic-bezier(.08, .81, .29, .99)`）与关键帧实现先快后慢的心理学非线性进度模拟，彻底替代 JS 定时器伪刷新。

---

## 4. 核心设计红线与避坑定律（Permanent Laws & Anti-Regression Anchors）

<a id="sec-13"></a>

### §13. Composable 顶层解构定律（Top-Level Destructuring Law）

- **根因**：Vue 3 模板对顶层变量会自动解包 `Ref`（Unwrap），但如果将 Composable 返回的整包对象传给模板（如 `setup() { return { state }; }` 模板中写 `state.prop`），会导致深层 Ref 解包失败，触发 `undefined is not a function` 或响应式断裂。
- **铁律**：**所有 Composable 的返回值必须在 `<script setup>` 顶层解构后直接绑定到模板或在脚本中使用**。
- **引用**：`AGENTS.md` Rule 5, `src/views/LibraryView.vue`, `src/views/DiscoveryView.vue`.

<a id="sec-12"></a>

### §12. 破坏性操作双重防护定律（Destructive Action Safety Gate）

- **根因**：单次点击直接删除/清空本地文件极易引发用户误触灾难。
- **铁律**：**所有破坏性操作（如「移除本地缓存」、「清空设备离线」）必须具备二次交互防护**：弹窗中明确展示删除范围与风险警示，强制勾选「我已了解此操作不可逆」后方可激活危险动作按钮。
- **引用**：`docs/agents/frontend.md`.

<a id="sec-08"></a>
<a id="sec-09"></a>

### §08/§09. 多章节全局页码与目录切片体系（Multi-Chapter Global Indexing & Route Slicing）

- **体系架构**：
  1. **全书页码拍平**：多章节漫画在底层拍平为单一大书（`1..page_count`），每页元数据记录所属 `chapter_id` 与 `chapter_index`；
  2. **详情页章节目录化**：详情页只呈现「章节目录」网格，点击具体章节进入子路由（`/comic/:src/:id/chapter/:cid`）查看该话缩略图；
  3. **阅读器全局统揽**：阅读器、封面生成、以图搜图与本地缓存始终基于全局页码，保证跨话阅读零摩擦过渡。

<a id="sec-21"></a>

### §21. 全局 View Transitions API 安全边界（View Transitions Safety Boundary）

- **铁律**：
  1. **全屏路由过渡仅限跨页面跳转**（书架 ⇄ 详情 ⇄ 章节 ⇄ 阅读器）；
  2. **严禁在阅读器内部翻页、切话或 HUD 显隐时触发 `startViewTransition`**（彻底杜绝微任务调度抢占导致的 `AbortError` 崩溃）；
  3. 所有 `document.startViewTransition` 调用必须显式捕获并静默处理 `ready`、`finished`、`updateCallbackDone` 的 Promise 异常。

<a id="sec-31"></a>

### §31. 矢量图标单源收敛定律（Unified Iconography Law）

- **铁律**：严禁在模板中书写 Unicode 伪图标字符（`✕`, `✓`, `×`, `⋯`, `←`, `→`）或散落手写内联 `<svg>`；统一基于 `src/components/icons/` 扩展原子图标。

<a id="sec-50"></a>

### §50. 全站弹窗与暗室主题隔离（Modal Variants & Theme Isolation）

- **铁律**：业务功能弹窗全面收敛至 `Modal.vue`（通过 `variant="paper" | "reader"` 与 `size` 变体控制），禁止在阅读器内手写独立遮罩导致亮色穿透与视觉割裂。

<a id="sec-51"></a>

### §51. 阅读器滚动驱动动画双轨架构（Dual-Track Scroll Architecture）

- **架构契约**：
  1. **A 轨（GPU / CSS Scroll-Driven）**：利用 `scroll-timeline`、`view-timeline` 与 `timeline-scope` 由合成器线程 120Hz 驱动顶部进度条与页面进场纸质微动；
  2. **B 轨（Vue Reactivity / JS Composable）**：利用 `useReaderNavigation` 结合 `requestAnimationFrame` 节流调度本地进度持久化（`useLastRead`）与相邻画卷后台预热（`preloadAround`），消除高频 DOM 读取引起的 Layout Thrashing。

<a id="sec-52"></a>

### §52. 视图轻量化与装配树编排（View Thinness & Assembly Tree Law）

- **铁律**：`src/views/*.vue` 单文件脚本严格 ≤ 150 行，只负责顶层生命周期编排与装配树挂载；核心业务状态机下沉至 `src/composables/`，复杂子视口与交互横幅抽离为专职子组件（如 `ReaderViewport.vue`, `ReaderChapterBanners.vue`）。

---

## 5. 历史演进里程碑归档索引（Historical Milestones Archive）

本项目 1 至 52 次历史设计评审、挑刺分析与重构推演记录已完整收录于归档文档：

📂 **[`docs/design-archive/MILESTONES_01_TO_52.md`](docs/design-archive/MILESTONES_01_TO_52.md)**

| 历史小节范围  | 核心主题与代表性里程碑                                                        | 对应归档定位                                                                                                                                                            |
| :------------ | :---------------------------------------------------------------------------- | :---------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **§01 – §04** | 纸间品牌哲学起步、初版代码评审、设计系统对齐与端适配                          | [归档 §01–§04](docs/design-archive/MILESTONES_01_TO_52.md#1-frontend-design-脑前区思考)                                                                                 |
| **§05 – §15** | 实时缓存进度、并发控制、多章节切片、危险操作门禁与 §13 顶层解构定律           | [归档 §05–§15](docs/design-archive/MILESTONES_01_TO_52.md#5-live-cache后台缓存实时进度critique--polish--adapt)                                                          |
| **§16 – §27** | 物理纸本质感升级、Loading 插画、双口令门禁、View Transitions 与错题本体系     | [归档 §16–§27](docs/design-archive/MILESTONES_01_TO_52.md#16-全局组件与-ui-质感系统性升级纸质典藏物理感拒绝-8-bit-割裂)                                                 |
| **§28 – §39** | 48 图预算增量加载、Popover/Anchor 浮层、PWA 离线存储与意图预热                | [归档 §28–§39](docs/design-archive/MILESTONES_01_TO_52.md#28-高并发冷热加载优化--多章节缓存-ui-体系化--文本截断与-hover-提示grill-with-docs-确认--impeccable-2345-规范) |
| **§40 – §52** | 访客借阅证、Lighthouse 审计治理、移动端阅读器重构、暗室弹窗与滚动驱动双轨架构 | [归档 §40–§52](docs/design-archive/MILESTONES_01_TO_52.md#40-访客通行证唯一使用lru-多设备漫游与防重发放预警impeccable--adr-0007)                                        |
