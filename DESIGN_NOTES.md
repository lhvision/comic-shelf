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
   - [§53 卷末归档专匣与双分区抽屉架构](#sec-53)
   - [§54 阅读器末页接卷推荐架构](#sec-54)
   - [§55 画卷折叠架与尾格余量收纳架构](#sec-55)
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
- **微标与字阶底线（Typography Floor & Caption）**：全站正文字阶受限于 `--text-xs` (12px) 底线；极小徽章与微标采用 `--text-caption: 0.6875rem` (11px)，借助 `font-size-adjust` 渐进增强突破传统 12px 限制并保持盒模型稳定，**严禁使用 `transform: scale()`**（避免引发盒模型不收缩、文字亚像素发虚与定位漂移反模式）；
- **自适应长文本防折行边界**：单行长文本自适应压缩（未来 `text-fit: shrink per-line`）严格局限于阅读器 HUD / 紧凑工具栏等单体场景，**绝对禁止侵入书架卡片网格阵列**（书架卡片标题坚守固定字阶 + `<AppTextClamp :lines="2">` 截断，杜绝卡片间字号忽大忽小破坏视觉节律）。

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
   - 架构基建：基于 HTML5 原生 `<dialog>` 顶层渲染体系（Top Layer）与原生无障碍焦点陷阱，辅以 `<Transition>` 保持淡出平滑度；
   - 交互契约：支持 `closeOnBackdrop`、`closeOnEsc`、`showCloseButton`、`preventClose` 与 `ariaLabel`，阻止关闭时触发 `is-shaking` 优雅微弹反馈；
   - 焦点归还：关闭后自动将光标送回触发源（遵循 WCAG 2.1 2.4.3 Focus Restoration）；
   - 声明式指令：关闭按钮原生挂载 `:commandfor="dialogId" command="close"`，并监听原生 `command` 事件；
2. **系统安全门禁（`GateView.vue` & `src/components/gate/`）**：
   - 根级 Zero-DOM 物理隔离大门（未鉴权时应用骨架与阅读器物理 0 挂载），三态表单（口令/首次认领设 PIN/已认领输 PIN）模块化收敛；会话凭据 `sessionStorage` 暂存自愈，移动端切屏误刷 0 掉态；
3. **轻量浮层与 Popover（`AppPopover.vue` / `Tooltip.vue`）**：
   - 基于 HTML Popover API + CSS Anchor Positioning（`anchor-name` / `position-anchor`）构建；
   - 触发器原生扩展 `commandfor` 与 `command="toggle-popover"`，具备 `@supports not (anchor-name: ...)` 绝对定位回退与 WCAG 1.4.13 悬停安全桥（Hover Bridge）保护。

### 3.2 矢量图标单源契约（Unified Iconography）

- 全站图标统一收敛至 `src/components/icons/`（如 `IconClose.vue`, `IconCheck.vue`, `IconArrowLeft.vue`, `IconBookmark.vue`）；
- 所有图标原子组件基于 `BaseIcon.vue`（规范 `size="1em"` 与 `viewBox="0 0 24 24"`）；
- 严禁在模板中内联书写未封装的 SVG 或 Unicode 字符。

### 3.3 视口渲染性能与预算（Rendering Budget）

- **书架 48 图预算（Shelf 48-Cover Budget）**：首页每本漫画包含 4 张展示封面（1 主封面 + 3 叠牌封面），采用 12 本/批（严格对应 12 × 4 = 48 张封面图）的增量渲染机制（VueUse `useIntersectionObserver` 监听底部哨兵）；
- **详情页 48 页切片（Detail Index Chunking）**：详情页缩略图按 48 页增量展开，避免千页巨作一次性阻塞主线程；
- **Canvas 重绘防抖（Canvas Redraw Debounce）**：Canvas 卡片采用 `redrawKey` + 80ms 防抖调度，消除高频进度重绘带来的掉帧；
- **响应式阶梯封面（Responsive Stepped Covers）**：封面与缩略图遵循 `Cover Dimension Budget`（720px 物理基线）；未来多阶分发严格遵循 `srcset`（`360w`, `720w`）+ `sizes` 规范，**严禁只写 `w` 漏写 `sizes`**（防浏览器默认 100vw 拉取超大图），渐进增强支持 `sizes="auto"` 与 `loading="lazy"` 原生尺寸联动。

### 3.4 现代进度条与拟真加载体系（Progress Bar System）

- **统一原子组件（`AppProgressBar.vue`）**：收敛全站进度条形态（`track` 3px 药丸槽 / `line` 3px 贴边细线 / `gauge` 6px 标尺槽）；
- **双轨渲染架构**：以 CSS Custom Property `--progress: 0~1` 与 `--value / --max` 驱动 GPU 合成层 `transform: scaleX(...)`，并在现代浏览器中渐进增强为原生 CSS `progress()` 数学函数，实现零 Reflow 开销；
- **拟真未定态（Indeterminate Mode）**：结合 `--ease-progress`（`cubic-bezier(.08, .81, .29, .99)`）与关键帧实现先快后慢的心理学非线性进度模拟，彻底替代 JS 定时器伪刷新。

### 3.5 文本多行自适应截断与纸印气泡体系（Text Clamping & Paper Tooltip Architecture）

- **统一原子组件（`AppTextClamp.vue`）**：收敛全站单行/多行超长文本截断与悬停气泡提示；
- **行数预算准则**：
  - **书架卡片**：标题 2 行（`line-clamp-2`）、作者与页数严格 1 行（`line-clamp-1`），气泡呼出延迟拉长至 `350ms`（离开缓冲 `250ms`），杜绝光标漫游误触与卡片网格高低不齐；
  - **详情页卡片**：大标题 2 行、元数据网格（作品/登场人物/作者等）2 行截断，超长文案悬停显示气泡；长篇叙述（`description`）升级为内联手风琴折叠（`Inline Disclosure`，3 行折叠 +「展开全文 ▾ / 收起 ▴」），绝不使用半空浮层破坏书籍呼吸感；
- **零开销性能铁律（Zero-DOM & Zero-Listener Overhead）**：
  - 默认状态仅渲染原生语义标签，Tooltip 浮层节点延迟挂载（`lazy: true` 为全局默认），休眠状态 0 额外 DOM；
  - `Tooltip.vue` 的 `window` 滚动与尺寸监听器仅在 `isVisible === true` 时按需挂载，休眠时监听器开销精确为 0，彻底免疫百张卡片滚动卡顿；
  - **JIT 纯按需测量架构（JIT Layout Measurement & Zero Forced Reflow）**：彻底废除挂载期（`onMounted`/`nextTick`）与无差别 `useResizeObserver` 对全量静态文本的无差别排版测量，实现首屏渲染 0 次 DOM 几何访问与 0 毫秒 Forced Reflow 阻塞；几何尺寸测量严格推迟至读者意图触发时刻（`pointerenter` / `touchstart` / `focusin`）；结合 Tooltip 的延迟生效评估（`Deferred Disabled Evaluation`），在 `delay` 结束时二次核验 `props.disabled`，并解耦 `props.disabled` 与 `props.delay === 0` 的逻辑判定，支持触控端 `touchstart` 显式唤起气泡，兼顾 0 掉帧与 0 误弹出；
- **物理分层与横向翻转对齐（Physical Separation & Dynamic Alignment）**：
  - **装饰与内滚物理分层**：根容器 `.tooltip__tip` 保持 `overflow: visible; padding: 0;`，保护 `::before`（45° 指示小三角）与 `::after`（WCAG 悬停安全桥）自由延伸而不被计入盒模型滚动范围；内部独立内容容器 `.tooltip__content` 承载 `padding` 与 `max-height + overflow-y: auto`，从底层杜绝短文本“幽灵滚动条”；
  - **横向碰撞箭头自适应**：浮层响应式监测几何相对位置（`actualAlign`），当视口边界触发 `flip-inline` 导致浮层向左翻转时，小三角自动从左端（`start`）动态翻转至右端（`end: right 0.85rem`），精准指向触发源；详情页 2 列网格右列天然支持 `:tooltip-align="end"` 默认端对齐。

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

<a id="sec-53"></a>

### §53. 卷末归档专匣与双分区抽屉架构（Shelf Archive Drawer & Read Deemphasis Architecture）

- **分桶与排序契约**：书架仅在「最近收录（未读优先）」默认排序下执行两层分桶（案头未读藏书区 `activeComics` 独占主书架，卷末已读书卷移入底部的归档专匣 `completedComics`）；在切换为按标题、页数、本地完整度时保持纯粹字典序单一网格；
- **卷末归档专匣（Archive Drawer）**：
  1. **语义化 Disclosure 按钮**：抽屉标题栏为语义化 `<button type="button" class="archive-drawer-header">`，标配 `:aria-expanded="archiveOpen"` 与焦点环，告别无障碍不可达的 `div` 点击反模式；
  2. **绝对断绝幽灵焦点（Ghost Focus Elimination）**：抽屉主体容器配置 `:inert="!archiveOpen"` 并在 CSS 中配合 `visibility: hidden; transition: visibility ...`，确保闭合状态下读者键盘 Tab 键或读屏器直接越过收拢抽屉，杜绝在不可见卡片上迷航；
  3. **智能感应展开**：当书架全部书目均已翻阅完毕（`allCompleted`）时，抽屉默认自动展开，无需读者多余手动拉开；
- **微降权质感**：归档抽屉内卡片应用克制的微降权（`opacity: 0.88; filter: grayscale(0.08)`），并在读者悬浮或聚焦时平滑还原为 100% 彩色与不透明度，兼具典雅书脊陈列感与新鲜阅读重心。

<a id="sec-54"></a>

### §54. 阅读器末页接卷推荐架构（Reader End Next Reads Architecture）

- **视口真实触达感知**：严禁在 `onMounted` 钩子中盲目将作品标记为「已读完」；必须使用 VueUse `useIntersectionObserver` 监听末页卡片容器（`cardEl`），仅当读者真正滚动至书末并进入视口后才触发完成事件；
- **暗室多端响应**：桌面端采用三联卡片网格，移动端（≤680px）采用垂直图文列表排列（封面在左、书名作者在右、右侧附详情入口），兼顾单手点选便捷性与一屏紧凑呈现；底部统一提供「回到详情」与「返回书架」双向离开出口；
- **触控安全与双向出口**：详情辅助按钮通过 `::before` 伪元素扩展至 ≥ 44×44px 物理判定热区，与大卡片直接开读解耦；底部统一提供「回到详情」与「返回书架」双向离开出口；
- **阅览室暗室按钮对比度防御（Reader Dark Room Button Isolation）**：阅读器暗室背景（`--reader-bg`）与全站默认浅色模式隔离。全站通用的 `.btn-ghost`（浅色模式下为近黑墨色文本）在暗室环境下会与纯黑底色混为一体导致完全不可见；必须基于暗室专有 Token 为 `.end-btn.btn-ghost` 提供明确的文本墨色（`var(--reader-ink)`）、暗室垫层（`var(--reader-surface-strong)`）与高对比度边框（`var(--reader-line-strong)`），并补充悬浮与激活态反馈，确保末页操作具备 WCAG AA 级（≥ 4.5:1）无障碍可读性。

<a id="sec-55"></a>

### §55. 画卷折叠架与尺寸插值动效架构（Collapsed Thumbnail Rack & Size Interpolation Architecture）

- **滚动逃逸根治**：页面索引与书架网格彻底废除长距离 `useIntersectionObserver` 引起的贪婪无节制自动追加，避免读者在浏览时纵向滚动条持续失控伸长；
- **尾格余量折叠卡与单源焦点**：
  1. **页面索引（PageIndexGrid）**：超出首屏预算的画页在网格末尾以独立的 `.page-fold-card`（保留 `.page-tile-overflow` 兼容）收纳卡呈现，视觉与交互完全与书架函套卡对齐（朱砂徽印、标题说明、主步进 `btn-primary`、展开全部 `btn-ghost` 与收拢出口）；折叠态严禁在网格外部同时渲染底部控制条（消除认知混淆与双重控件），仅在全量展开后于底部呈现 `.page-sentinel` 典雅收整条；严禁以透明蒙层盖死最后一个内容画页，彻底杜绝 DOM `RouterLink` 幽灵焦点与读屏语音冲突；
  2. **书架网格（ComicGrid）**：未展开藏书在网格末尾以函套收纳卡（`.shelf-fold-card`）呈现，严格采用 `var(--radius-3)` 与 26rem 最小高度，彻底根治单卡成行时的断层塌陷；全部展开后底部呈现 `.shelf-sentinel` 单按钮收整书架；
- **现代平滑尺寸插值（interpolate-size: allow-keywords）**：
  1. **CSS 原生高度插值**：归档抽屉主体声明 `interpolate-size: allow-keywords; height: 0;` 并在展开时通过 `height: auto;` 与 `transition: height var(--duration-3) var(--ease-spring)` 实现 GPU 合成层平滑膨胀与收缩，告别手写 JS 获取 `scrollHeight` 导致的强制同步重排；
  2. **弹性网格优雅降级**：通过 `@supports not (interpolate-size: allow-keywords)` 对旧版内核降级为 `display: grid; grid-template-rows: 0fr -> 1fr;` 零成本平滑适配；
- **网格动画安全禁令（No Absolute on Grid Leave）**：`<TransitionGroup>` 的 `shelf-card`、`folio-card` 与 `chapter-card` 动效中，**严禁在 `.leave-active` 中定义 `position: absolute;`**，避免 Grid 布局崩塌与卡片在左上角重叠闪烁；
- **触控靶心底线与防迷航回滚**：
  1. **移动端 WCAG 2.5.5 与次级操作并列（Mobile Action Row Layout）**：在 `max-width: 640px` 下，所有折叠步进与全量展开按钮强制保底 `min-height: 44px;`；次级操作（展开全部与收拢归档）收敛于 `.fold-card-sub-actions` 并列容器中横向均分并排呈现，彻底根治移动端纵向堆叠导致的 48px 异常拉伸与画页视野挤占；
  2. **视口锚点自愈与动效无障碍（Reduced Motion Adaptation）**：点击收起时通过 `window.matchMedia('(prefers-reduced-motion: reduce)').matches` 探测读者系统动效偏好，在开启减少动效时以 `behavior: 'instant'` 瞬间就位，关闭时以 `behavior: 'smooth'` 平滑回退至网格顶部锚点，兼顾防迷航与前庭功能障碍读者的视觉舒适度。

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
