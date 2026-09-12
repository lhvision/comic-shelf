# 纸间 · Paper Room 设计系统规范与架构基准（Living Design System）

> **文档性质**：纸间设计系统单一真相源（Single Source of Truth）。
> 每次涉及 UI/UX 组件新建、视图重构与视觉打磨前**必读**。
> 历史演进日志（§01 – §52 次迭代记录）已归档至 [`docs/design-archive/MILESTONES_01_TO_52.md`](docs/design-archive/MILESTONES_01_TO_52.md)。

---

## 目录（Index）

1. [设计哲学与品牌隐喻（Design Philosophy & Metaphor）](#1-设计哲学与品牌隐喻design-philosophy--metaphor)
2. [设计系统 Token 契约（Design Tokens System）](#2-设计系统-token-契约design-tokens-system)
3. [核心组件架构与变体规范（Component Architecture）](#3-核心组件架构与变体规范component-architecture)
   - [3.6 通用微件胶囊体系（Universal Chip & Filter System）](#36-通用微件胶囊体系universal-chip--filter-system)
   - [3.7 统一按钮体系（Unified Button Architecture & AppButton）](#37-统一按钮体系unified-button-architecture--appbutton)
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
   - [§56 来源导航单一真理源与收录工作台解耦架构](#sec-56)
   - [§57 条漫无缝拼接与自适应画卷架构](#sec-57)
   - [§58 万级书库流式分页、阅读状态分段胶囊与安全刹车系统](#sec-58)
   - [§59 纸室离线模式与端侧自愈流水线架构](#sec-59)
   - [§60 排版作用域双轨制、存量基线静默自愈与透明化设置架构](#sec-60)
   - [§61 高刷 144Hz 极速性能治理](#sec-61)
   - [§62 阅读器台词对白气泡呼吸高亮与直达定位架构](#sec-62)
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

### 3.6 通用微件胶囊体系（Universal Chip & Filter System）

- **统一原子组件（`AppChip.vue`）**：收敛全站标签、筛选切换器、计数胶囊与可移除微件；
- **多态无障碍渲染（Polymorphic ARIA Rendering）**：
  - 纯展示标签（如作品分类标签）默认渲染为极轻量语义 `<span>`；
  - 绑定交互事件（`@click`）、状态切换（`pressed !== undefined`）或显式声明 `interactive: true` 时，自动升格为 `<button type="button">`；
  - 状态切换模式下原生绑定 `:aria-pressed="pressed ? 'true' : 'false'"`，支持键盘焦点环与活动水墨态；
- **契约解耦与槽位优先**：
  - 支持 `count` 计数字段、`icon` 前置图标快捷声明；
  - 提供 `#prefix`、`#suffix`、`#count` 与 `#remove-icon` 精准插槽，便于扩展心形收藏态与展开旋转折叠箭头；
- **可删除胶囊闭环（Removable Chip）**：
  - `removable: true` 原生挂载无障碍关闭微按钮，点击触发 `emit('remove', event)` 并在底层强制 `event.stopPropagation()`，杜绝点击删除误触父级跳转。

### 3.7 统一按钮体系（Unified Button Architecture & AppButton）

- **单一真相源（`AppButton.vue`）**：全站通用操作、状态提交、二次确认与独立功能图标按钮的统一入口，严禁在业务组件中裸写原生 `<button class="btn btn-*">` 或手写 class 模拟按钮（ADR 0016）；
- **标准变体与尺寸契约**：
  - 六色变体：`variant="primary" | "secondary" | "ghost" | "soft" | "danger" | "success"`（严格映射 `tokens.css` 主色、墨色与状态色，支持 `block` 占满宽度）；
  - 规范四阶尺寸：`size="xs"` (28px) | `"sm"` (32px) | `"md"` (40px, 默认) | `"lg"` (48px)，触控区域结合移动端自适应收缩；
- **多态渲染与跳转安全（Polymorphic ARIA Navigation）**：
  - 传入 `to` 时自动以 `<RouterLink>` 渲染；传入 `href` 时自动以 `<a>` 渲染（支持 `target="_blank"` 自动补齐 `rel="noopener noreferrer"`）；未提供时渲染原生 `<button>`；
  - **链接禁用态拦截铁律**：当处于 `disabled` 或 `loading` 状态时，多态链接自动挂载 `aria-disabled="true"`、`tabindex="-1"`，并在底层强制 `event.preventDefault()` + `event.stopPropagation()`，保持 DOM 节点稳定的同时彻底杜绝链接误触跳转；
  - **原生链接语义纯净律（Semantic Link Purity）**：多态链接严禁滥用 `role="button"` 覆写无障碍树语义，必须保持原生 `link` 语义，杜绝屏幕阅读器误报及缺乏 Space 键拦截引发的视口破坏性滚动（WCAG 2.1.1）；
- **单源图标与独立图标按钮（Icon Button Mode & Dead Import Elimination）**：
  - 支持 `shape="default" | "circle" | "square"`，结合 `icon="<IconName>"` 与 `iconPosition="left" | "right"`（默认 `'left'`）实现属性与插槽双轨制；
  - **形状与内容解耦律**：`shape` 仅控制几何轮廓（圆形/方块），内容模式由插槽与图标共同裁决，支持方块按钮携带自定义文本插槽的标准图文并存；
  - 纯图标模式下自动收敛为 1:1 宽高比与居中排布，开发环境运行时强校验 `aria-label` / `title`，杜绝读屏盲区（WCAG 4.1.2）；
  - **图标单源收敛定律**：通用按钮的前置/后置图标优先通过 `icon` 与 `iconPosition` 声明，禁止在组件层为了单一按钮图标冗余引入 `import AppIcon`，推动业务层消除无用导入（Dead Imports）；
- **阅览室暗室高对比度防御（Reader Dark Room Token Defense）**：
  - 支持 `theme="reader"`，在阅读器暗室背景（`--reader-bg`）下自动激活专属暗室 Token：
    `--reader-surface-strong`（暗室垫层）、`--reader-ink`（防刺眼高对比柔白文字）、`--reader-line-strong`（高对比边框）与 `--reader-surface-hover`（悬浮反馈），确保暗室幽灵按钮达到 WCAG AA 级（≥ 4.5:1）对比度标准，杜绝业务视图手写局部 CSS 补丁。

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
- **尺寸插值与溢出标签顶层浮层演进（interpolate-size & Overflow Tag Popover）**：
  1. **尾部归档抽屉插值**：位于书架尾部、不推挤复杂图形卡片的归档专匣（`.archive-drawer-body`）采用 `interpolate-size: allow-keywords; height: 0 ⇄ auto;` 实现平滑展开，并通过 `@supports not` 降级；
  2. **溢出标签顶层浮层升维（Zero-Reflow Popover）**：标签栏次级溢出标签彻底拔除在主干流中推挤整架卡片的尺寸插值机制，全面收敛为基于 HTML Popover API 与 CSS Anchor Positioning 的 `AppPopover` 顶层浮层；视口高度与下游网格保持绝对静止（0 像素推移、0 几何重排），从根源杜绝 144Hz 高刷屏与核显上的 GPU 合成器卡顿；
  3. **无障碍焦点归还与操作闭环（WCAG 2.4.3 Focus Restoration & Loop Closure）**：次级浮层关闭后自动通过 `nextTick` 归还焦点至触发胶囊；当激活次级标签时，外露触发胶囊显式呈现 `:pressed="true"`，浮层头部提供置顶清除入口与「当前在看」微标，彻底消解“选择墙”找回成本；
  4. **常驻合成层与滤镜瘦身铁律（Zero Idle VT Footprint & De-blurred Stamps）**：网格卡片禁止常驻绑定静态 `viewTransitionName`（仅在激活/点击目标上动态挂载 `comic-cover-active`），避免 Blink 为全架数十张卡片在位移时维护独立合成快照图层；大面积位移重排的微标印章（`.id-stamp`、`.match-stamp`、`.reading-stamp`）严禁滥用 `backdrop-filter: blur(...)`，改用高感知半透明墨色背景（`color-mix(in oklab, var(--ink-0) 88%, transparent)`）配合微阴影，彻底消除低配核显与软解模式下的每秒数千次高斯模糊重采样卡顿；吸顶栏增加 `contain: layout style; isolation: isolate;`，全屏水印增加 `contain: strict; will-change: opacity;`；
- **网格动画安全禁令（No Absolute on Grid Leave）**：`<TransitionGroup>` 的 `shelf-card`、`folio-card` 与 `chapter-card` 动效中，**严禁在 `.leave-active` 中定义 `position: absolute;`**，避免 Grid 布局崩塌与卡片在左上角重叠闪烁；
- **触控靶心底线与防迷航回滚**：
  1. **移动端 WCAG 2.5.5 与次级操作并列（Mobile Action Row Layout）**：在 `max-width: 640px` 下，所有折叠步进与全量展开按钮强制保底 `min-height: 44px;`；次级操作（展开全部与收拢归档）收敛于 `.fold-card-sub-actions` 并列容器中横向均分并排呈现，彻底根治移动端纵向堆叠导致的 48px 异常拉伸与画页视野挤占；
  2. **视口锚点自愈与动效无障碍（Reduced Motion Adaptation）**：点击收起时通过 `window.matchMedia('(prefers-reduced-motion: reduce)').matches` 探测读者系统动效偏好，在开启减少动效时以 `behavior: 'instant'` 瞬间就位，关闭时以 `behavior: 'smooth'` 平滑回退至网格顶部锚点，兼顾防迷航与前庭功能障碍读者的视觉舒适度。

<a id="sec-56"></a>

### §56. 来源导航单一真理源与收录工作台解耦架构（Source SSOT & Provider Ingest Decoupling Architecture）

- **双层嵌套 Tab 根治与单一真理源（Single Source of Truth）**：
  1. 彻底废除 Hero 内部 `ImportPanel` 自主维护的 `.panel-tabs` 与全局 Header 来源导航冲突的“嵌套选项卡”（Tab-in-Tab）反模式；
  2. 确立 `activeSource = computed(() => route.query.source || '')` 为全局唯一驱动源。各站点 Provider 与通用书架彻底解耦；
- **全景视图与单源工作台分治**：
  1. **全部视图（All View, `/?`）**：Hero 回归优雅的单栏典藏大片版式（`hero--single`），不常驻收录输入框，聚焦于书房精神 lede、三项统计指标与阅读氛围；在统计区下方提供轻巧典雅的「录入新卷：`[+ 禁漫] [+ 哔咔] [+ 本地]`」导航胶囊，点击顺滑切入对应源专属工作台；
  2. **单源视图（Provider View, 如 `/?source=jm`, `/?source=picacg`, `/?source=local`）**：Hero 右侧专精呈现对应站点的收录/扫描面板（`.is-source-locked` 单列紧凑编排），隐藏内部多余 Tab，消除中屏视口（961px~1180px iPad 横屏）的双列轨道冲突（664px 刚性下限溢出）；
- **操作自由度与逃生通道闭环（Escape Hatch）**：
  1. 单源模式下在 Hero 左上方显式提供 `〔 ← 返回全部藏书 〕` 面包屑路由锚点，避免用户因过滤后无处退回产生被劫持感；
  2. 移动端折叠抽屉严格声明 `:inert="!isDesktop && !isMobileExpanded"` 并配合 `visibility: hidden` 过渡，彻底根除不可见隐藏表单与按钮引发的无障碍幽灵焦点（Ghost Focus）；
  3. 移动端快捷药丸严格遵守 WCAG 2.5.5，保底 `min-height: 44px;` 触控物理判定区。

### <a id="sec-57"></a>§57 条漫无缝拼接与自适应画卷架构（Webtoon Seamless Stitched View & Floating Pill Architecture）

- **业务背景与物理割裂根治**：
  条漫（韩漫/国漫/Webtoon）在创作源头为单一连续垂直长卷，但在分发与收录时被切片成离散图片（如 3200px + 1912px）。若沿用普通分页漫画的行内装订页脚（`<footer class="page-footer"><span>021</span></footer>`）、页间外边距（`padding-top: var(--reader-gap)`）与单页阴影（`box-shadow`），原本连续的画格、衣服折痕与对白气泡会被硬生生腰斩截断。
- **排版硬约束防撕裂（Constraint Guard）**：
  1. 切片高度往往极不规律，若按「适应高度（fit: height）」缩放会导致相邻切片宽度失配并产生横向错位。系统在开启无缝模式（`seamless === true`）时强制锁定为「适应全宽（`fit: 'width'`）」且「单列呈现（`pagesPerView = 1`）」；
  2. 设置面板中相应互斥项呈现为禁用态并挂载朱砂微标（`〔 条漫已锁定单页全宽 〕`），避免冲突。
- **亚像素微咬合与零缝咬合（Micro-Overlap）**：
  1. 对非首图施加 `margin-top: -1px` 微咬合，彻底消除高 DPR 视网膜屏与浏览器缩放（125%/150%）下的浮点舍入背景漏缝；
  2. 物理拔除行内占位页脚，剥离阴影并去除进场位移动画，确保滚动平滑顺畅。
- **浮动画卷页标（Floating Page Pill）**：
  1. 替代行内页码，采用视口右下角半透明水墨胶囊（高不透明度半透明纯色背景 `var(--reader-scrim)` 加微投影，彻底移除高频滚动期间 GPU 高斯模糊滤镜开销 + 单源等宽字体 `021 / 045`）；
  2. 滚动时感应淡入（`opacity: 0.92`），停止滚动 1.5 秒后静默淡出；呼出全局 HUD 时主动隐退，杜绝视觉冲突；内置 `role="status"` 与 `prefers-reduced-motion` 契约。
- **单本偏好记忆与智能启发感知（Per-Comic Overrides & Heuristics）**：
  1. 本地持久化单本阅读偏好（`comic-shelf:reader-overrides:v1`），维护严格的单本与全局基线状态机隔离，单本偏好决不反向污染全局用户默认；
  2. 引入 `MAX_OVERRIDES = 100` 的 FIFO/LRU 驱逐策略，防止本地存储无界膨胀；
  3. 首次进入尚未配置偏好的漫画时，若标签命中 `条漫` / `韩漫` / `Webtoon`，自动默认启用无缝拼接，读者开箱即享沉浸长卷。

### <a id="sec-58"></a>§58 万级书库流式分页、阅读状态分段胶囊与安全刹车系统（Large-scale Paginated Shelf, Segmented Reading Status & Safety Brake System）

- **业务背景与架构升级（承接 ADR 0015）**：
  藏书规模迈入万级后，全量下发导致传输风暴与前端卡顿；读者在浏览过程中反复手动点击「再看 12 本」割裂感强烈；阅读状态原仅有「只看已读」，缺少「只看在读」，且布尔开关并列容易造成交集为空的非预期白屏。
- **阅读状态单选收敛（Segmented Reading Status）**：
  1. 彻底废弃「只看已读」与「只看在读」的多布尔并列反模式，收敛为互斥的**三态分段胶囊（SegmentedTabs）**：`[ 全部 | 在读 | 已读 ]`（`readingStatus: 'all' | 'reading' | 'completed'`）；
  2. 「只看喜欢」保持为正交独立的偏好微件，互不干扰；
  3. 状态通过 URL Query（`?status=...&favorite=...`）双向同步，刷新或从详情页回跳时无损还原。
- **阈值流式展开与安全刹车（Safety Brake）**：
  1. 前 5 批（共 60 本 / 240 张封面图）由 `useIntersectionObserver` 触底哨兵自动无感平滑加载，读者滚动即加载，彻底消除点击阻滞；
  2. 达到 60 本安全阈值后，主动触发**安全刹车**：暂停贪婪滚动，在网格末尾露出折叠函套卡，提供「继续向下探索 24 本」与「展开全部」的主动掌控权，同时确保底部的卷末归档专匣（已读完作品）可平滑触达；
  3. 全量展开设定 240 本安全上限（Safety Cap），彻底杜绝万级图片导致移动端标签页 OOM 崩溃闪退。
- **识图穿透与跨端同步闭环**：
  1. 以图搜图命中历史藏书时，通过 `/api/library?ids=...` 精准定向拉齐，杜绝分页导致的“搜得出但看不见”历史断层；
  2. 跨端 SSE 事件（增删本子、重装订）联动刷新首屏切片与全貌统计（Facets），保持多端一致。

### <a id="sec-59"></a>§59 纸室离线模式与端侧自愈流水线架构（Offline-First Resilience & Reconciliation Pipeline）

- **业务背景与架构升级（承接 ADR 0005 决议 3）**：
  传统 PWA 缓存静态资源后，由于书架首屏和详情页强依赖 `/api/library` 远端接口，一旦断网便陷入白屏空架或强退首页；粗暴在 Service Worker 缓存 API 又会因缺乏鉴权头隔离导致多租户数据泄露与权限穿透。
- **端侧元数据持久化与 0ms 水合（IndexedDB SWR）**：
  1. 建立轻量 `comic-shelf-meta` IndexedDB 引擎，书架快照（`shelf_${userId}`）与漫画详情（`${userId}:${source}:${sourceId}`）按用户身份物理分区；
  2. 漫画详情内置 200 本 LRU 淘汰机制，杜绝端侧存储无限膨胀；
  3. 冷启动或断网时 0ms 水合 IndexedDB 快照，网络请求失败时不破坏已有 DOM，平滑展示「〔 纸室离线模式 〕」暗印状态；
  4. 彻底废弃常态工具栏的「只看离线」手动开关，全面收敛为静默离线接管（Zero-Toggle Offline Resilience）：断网时由后台自动触发快照呈现与离线模式提示，消弭在线状态下的交互割裂。
- **全链路离线漫游与水墨缺页骨架**：
  1. 详情页与章节页在离线断网时自动降级读取 IndexedDB 详情或概要占位（`createPlaceholderDetail`），彻底拔除 `router.replace('/')` 强退首页逻辑；
  2. 阅读器未下载画页展示典雅的「〔 画页未离线缓存 〕」水墨纸印骨架（`.page-error.is-offline`），拒绝原生破图图标。
- **离线记账与联网自愈回写流水线（Reconciliation Pipeline）**：
  1. 离线翻页进度（`useLastRead`）与喜欢变动（`FavoriteButton`）打上当前 `userId` 签名并自动暂存至本地 `offline_actions` 事务队列，UI 保持瞬时乐观响应；
  2. 由 `App.vue` 顶层统一挂载的 [`useOfflineSync`](src/composables/useOfflineSync.ts) 监听 VueUse `useNetwork().isOnline`；
  3. 网络重连时执行身份校验（`item.userId === currentUid`），安全批量回写后端 SQLite 并触发 SWR 后台静默刷新。

### <a id="sec-60"></a>§60 排版作用域双轨制、存量基线静默自愈与透明化设置架构（Dual-Scope Reader Preference, Stale Baseline Healing & Transparent Settings Architecture）

- **业务背景与痛点根因**：
  为防范条漫（Webtoon）反向污染日漫基线引入单本独立偏好（`overrides`）后，因阅读器设置面板仅在阅读时唤起，`activeComicKey` 恒为真，导致用户在此所做的任何调节只能落入单本字典，全局基线 `stored` 在 UI 上沦为死锁黑盒。存量设备若因历史漏洞写入了 `fit: 'width'`，后续所有新开的普通日漫均会被强制以宽度适配展示，用户误以为“设置不生效”，产生强烈的割裂感与不透明感。
- **作用域双轨制交互规范（Dual-Scope UI Model）**：
  1. 阅读设置面板顶部设立分段切换胶囊：`[ 📖 本作偏好 ]` 与 `[ 🌐 全局默认 ]`（集成原子矢量图标 `IconGlobe.vue`）；
  2. **智能感知与状态指示**：本作偏好胶囊动态标注当前状态（`条漫` / `已自定义` / `跟随全局`），并搭配上下文感知提示条说明修改所影响的范围；
  3. **即改即分离（Detached on Edit）**：本作处于继承态时，修改任意排版项立即为本作生成专属偏好，底部常驻「恢复跟随全局」操作通道，随时可一键撤销；
  4. **所见即所得实时联动（Live Viewport Sync）**：读者在「全局默认」标签下修改配置时，若当前漫画处于继承状态，视口画卷立即实时响应，实现所见即所得；
- **存量设备一次性静默自愈（Baseline Healing Pipeline）**：

### <a id="sec-61"></a>§61 高刷 144Hz 极速性能治理：捕获缝隙瞬时归零、CSS @starting-style 声明式进场与 2D/3D 按需升维（144Hz Zero-Reflow Pipeline, In-Flight Pre-Capture Scroll & Lazy 3D Elevation）

- **业务背景与 144Hz 显卡瓶颈复盘（Trace-20260911）**：
  在配备 144Hz 高刷屏幕与较弱集成显卡的终端上，单帧渲染预算从常规 60Hz 的 16.67ms 骤降至极其严苛的 **6.94ms**。任何超过 7ms 的主线程强排或 GPU 片元滤镜着色，都会造成肉眼可见的卡顿顿挫。经 Chrome DevTools MCP 性能火焰图与 4x 降速洞察，系统定位出三大性能黑洞：
  1. **跨页面路由推进 209ms 同步重排**：Vue Router 同步滚顶在新组件挂载未排版时调用 `window.scrollTo`，触发整屏新视图强制重排；
  2. **书架分类标签切换 168ms FLIP 布局抖动**：Vue `<TransitionGroup>` 在 30+ 张卡片上循环读取 `getBoundingClientRect` 与 `getComputedStyle`；
  3. **首屏吸顶栏 57ms 几何重排**：`AppHeader` 初始化时 `useScroll` 强读 `scrollLeft` 与 `clientWidth`。
- **捕获缝隙瞬时归零架构（In-Flight Pre-Capture Instant Scroll）**：
  1. 在保留全局 View Transitions 丝滑推进质感的前提下，于 `router.beforeResolve` 的 `performUpdate` 回调入口（此时旧视图已由浏览器生成离屏 GPU 纹理冻结在屏幕上，新视图尚未开始挂载）执行 `window.scrollTo({ top: 0, behavior: 'instant' })`；
  2. 结合模块级 `hasPreScrolled` 锁，`router.scrollBehavior` 探测到后直接返回 `false`，0 几何属性读取，**209ms / 134ms 强制重排彻底清零**；
  3. 新视图挂载即处于原点，`::view-transition-new(root)` 截取的新页面无撕裂、无位移畸变。
- **CSS `@starting-style` 声明式动效与闲置 2D / 交互 3D 按需升维（Lazy 3D Elevation）**：
  1. 彻底废除 `.shelf-card-move`，跳过 Vue FLIP 在 JS 层的密集几何属性轮询；
  2. 采用现代 Baseline 2024 标准 CSS `@starting-style` 与 `transition-behavior: allow-discrete`，卡片筛选入场直接由浏览器合成器线程执行 GPU 硬件补间，**168ms 布局抖动直接降至 8ms**（下降 95.2%）；
  3. 卡片常态下剥离昂贵的 `perspective: 60rem` 与 `.deck-leaf` 的片元着色器 `filter: saturate() brightness()`，以高性能原子色彩混合 `color-mix` 替代；仅在读者鼠标悬停（`:hover`）或触碰聚焦时激活 3D 透视折叠，将 GPU 每一帧常驻 3D 纹理开销压减为 0。
- **IntersectionObserver 隐形双哨兵边缘感知（Zero-Reflow Sentinels）**：
  在吸顶导航列表前后嵌入 1px 透明哨兵节点（`sentinelStartEl` / `sentinelEndEl`），通过 VueUse `useIntersectionObserver` 异步感知边缘可见性，彻底剔除 `useScroll` 与 `useResizeObserver`，**首屏 57ms 强制重排彻底归零**。

### <a id="sec-62"></a>§62 阅读器台词对白气泡呼吸高亮与直达定位架构（Breathing Bubble Overlay & Dialogue Direct-Jump Architecture）

- **业务背景与设计隐喻**：
  读者在全站通过台词全文检索（SQLite FTS5 + Trigram）定位经典台词时，需要从命中结果直达阅读器具体页码（`?page=42&bubble_box=0.1,0.2,0.3,0.4` 或 `?page=42&highlight_bubble=1`）。系统在此对白分镜位置呈现纸间专属的**朱砂金墨呼吸高亮气泡**（`ReaderBubbleOverlay.vue`），重现传统书房典籍批注中“朱砂圈点”的温润墨印质感。
- **排版几何锚点与零黑边偏移（Aspect-Ratio Lock Frame & Zero Letterbox Drift）**：
  1. 气泡归一化坐标 `[ymin, xmin, ymax, xmax]` ∈ [0, 1] 以漫画原图实际像素为基准；
  2. 在 `ComicPageImage.vue` 底图解码后，动态注入真实物理宽高比 `:style="{ aspectRatio: naturalRatio }"` 并设为 `display: block; width: auto; height: auto; max-width: 100%; max-height: 100%`；
  3. `ReaderViewport.vue` 中 `vertical-paged` 与 `horizontal` 模式将底层 `img` 设为 `width: 100%; height: 100%`，确保外层 `.comic-page-img-frame` 与 `img` 边界绝对贴紧，百分比定位彻底与外层视口 Letterbox / Pillarbox 留白解耦，在任何模式与屏幕高宽比下实现 0 像素误差咬合。
- **时序同步与加载期防夭折门禁（Image Ready Gate）**：
  1. 通过 `ComicPageImage` 的插槽向外透传 `:ready="!loading && !failed"` 状态；
  2. 仅当大图完成网络下载与 `@load` 解码渲染上屏后，才触发 2.2 秒 `@keyframes breathing-pulse` 动效，彻底杜绝大图加载期将高亮动画在骨架屏背后消耗殆尽的体验断层。
- **无障碍与边界防碰撞防护**：
  1. 全链路声明 `pointer-events: none`，翻页触控、双击缩放与滚动交互零感穿透；
  2. 顶部分镜（`ymin < 0.12`）微标胶囊自适应翻转至气泡框下方，右侧分镜（`xmin > 0.65`）自适应靠右对齐；
  3. 原生挂载 `role="status"` 与 `aria-live="polite"`，保障辅助技术屏幕阅读器对命中文本的即时感知。

### <a id="sec-63"></a>§63 阅读器全模式图片适配约束与刚性吸附体系（Reader Modes Fit Constraints & Rigid Snap Architecture）

- **业务背景与交互心智**：
  读者在切换阅读模式（纵向连续 / 纵向翻页 / 横向翻页）时，曾出现翻页模式下“图片适配选项消失”与“翻页变连续滑移”的认知困惑。排版系统据此建立离散翻页与连续长卷的正交设计约束。
- **翻页模式整屏锁定（Full-Frame Discrete Constraint）**：
  1. **离散翻页视野确定性**：翻页模式（`vertical-paged` / `horizontal`）以“一次一屏”为核心契约，排版强制锁定为「整屏完整入目（适应高度）」，杜绝在单屏内产生二次纵向滚动甚至手势撕裂；
  2. **设置面板约束显式透出**：设置面板（`ReaderSettingsPanel.vue`）对图片适配选项全模式常驻，在翻页模式下呈置灰锁定态，展示胶囊徽标 `〔 翻页已锁定整页入目 〕` 并辅以自解释说明，根除选项丢失疑惑；
  3. **条漫长卷自适应锁定**：在条漫无缝拼接（`seamless`）模式下，同样以徽标 `〔 条漫已锁定适应宽度 〕` 显式明示全宽长卷约束。
- **刚性翻页吸附（Rigid Mandatory Snap）**：
  1. 竖向翻页（`vertical-paged`）废除松散的 `y proximity`，全面升级为刚性强吸附 `scroll-snap-type: y mandatory`；
  2. 与横向翻页（`x mandatory`）保持绝对一致的物理翻页手感，无论滚轮或滑动手势快慢，停手后必严格吸附对齐至单页边界，消除停滞在两页缝隙间的伪连续假象。

### <a id="sec-64"></a>§64 前台台词全文检索与联想浮层体系（Dialogue FTS5 Search & Popover System）

- **业务背景与双重搜索意图解耦（Dual Intent Quiet Coexistence）**：
  书架搜索栏承担「本地藏书书名/作者/标签过滤」与「全书 OCR 台词分镜全文检索」双重意图。为避免通用搜索联想破坏本地书架心智，确立静默伴生原则：
  1. **零打扰静默门禁**：输入关键词时，后台 300ms 防抖执行 FTS5 异步检索；若台词返回 0 条，浮层**严格保持静默隐藏**，绝不弹出侵入性空状态弹窗遮挡书架已命中的漫画列表；
  2. **命中显式唤醒**：仅当台词检索命中实际分镜对白，或用户主动下按方向键（`ArrowDown`）探寻台词时，才在搜索栏正下方展开水墨纸本联想浮层。
- **纯声明式分镜高亮与零 XSS（Tokenized Declarative Highlight）**：
  1. 废除 `v-html` 潜在漏洞，构建专属 `parseSnippetTokens` 结构化切分器，将后端 `<mark>` 标签安全解析为 `{ text: string, isMark: boolean }[]`；
  2. 命中字词采用朱砂印泥金墨质感微标（`background: color-mix(in oklab, var(--accent) 22%, transparent); color: var(--accent-strong)`），行内优雅高亮。
- **WAI-ARIA Combobox 标准与键盘无障碍视口对齐（Accessible Viewport Tracking）**：
  1. 宿主输入框完整声明 `role="combobox"`、`aria-autocomplete="list"`、`aria-controls` 与 `aria-activedescendant`；浮层声明 `role="listbox"` 与带唯一 ID 的 `role="option"`；
  2. 键盘上下方向键导航时，监听 `focusedIndex` 并执行 `scrollIntoView({ block: 'nearest', behavior: 'smooth' })`，彻底消除长列表盲人摸象式盲航；
  3. 回车键支持智能首项兜底（未手动选中时默认直达最佳匹配项），兑现“输入回车即达分镜”交互承诺；
  4. 移动端防护：限制浮层高度在软键盘呼出时不挤压遮挡（`max-height: min(16rem, 38dvh)`），触控按钮判定热区统一满足 `≥ 44×44px`。

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
