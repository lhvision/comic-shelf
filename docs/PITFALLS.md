# 错题本与避坑红线（Pitfalls Ledger）

> 纸间核心避坑速查表。全仓重构、审查或提交前必须逐条核对，严禁踩踏红线。

---

### 1. 后端依赖清理与全局权限断层

- **本质**：全局中间件隐式依赖的符号被当作无用 import 误删，击穿请求鉴权管道。
- **复现场景**：重构清理 import 时误删 `auth.py` 中的符号。
- **红线与防误伤**：**不要**在清理未引用 import 时删除中间件隐式依赖的全局符号，禁止使用 `is_admin` 别名；**放行/改用**局部未引用的变量可安全删除，权限校验统一收敛为 `is_curator` 并强制跑通 `pnpm test:py`（曾导致写接口全线报 500 NameError）。

### 2. JM 漫画下架 404 容错拦截

- **本质**：将外部 HTTP 200/302 默认假定为合法内容，未对下架异常重定向做前置守卫。
- **复现场景**：用户输入原站已下架的 JM 车号，原站重定向至 `/error/album_missing`，HTML 解析抛出正则不匹配。
- **红线与防误伤**：**不要**未经验证直接对远端 HTML 执行正则提取；**放行/改用**正常 200 漫画页面放行解析，但必须前置嗅探错误页特征并转换为 HTTP 404 友好提示（曾导致解析崩溃报 500）。

### 3. 多章节全局页码单调递增

- **本质**：局部追加数据时破坏了全书平铺页码的全局单调递增不变量（`Monotonicity`）。
- **复现场景**：自建漫画在已有章节中间或末尾追加新图时，仅在该章节局部自增页码。
- **红线与防误伤**：**不要**对多章节漫画仅做章节级局部自增；**放行/改用**单章节扁平漫画可直接追加，但多章节无论在哪一话追加都必须触发全书 `rebuilt_pages` 重排，保持 `ch.start` 与 `page.index` 严格从 1 单调递增（曾导致翻页跳页）。

### 4. 服务端路径导入沙箱隔离

- **本质**：直接透传用户物理路径导致系统安全边界被击穿。
- **复现场景**：在自建图集或服务器路径导入中传入敏感系统目录（如 `/etc/`、`/root/`）。
- **红线与防误伤**：**不要**将未受限的用户输入路径直接交给文件遍历或读取；**放行/改用**合法目录放行，但必须通过 `_is_path_allowed()` 白名单校验，受限于 `DATA_DIR`、项目根目录与 `ALLOWED_DIRS` 沙箱（防止任意文件扫描与目录遍历）。

### 5. Vue 3 响应式解包与顶层解构

- **本质**：Vue 3 模板的自动 unwrap 仅对 `<script setup>` 顶层变量生效，嵌套对象内部 Ref 不解包。
- **复现场景**：在 `<script setup>` 中写 `const workshop = useLocalWorkshop()` 并在模板读取 `workshop.title`。
- **红线与防误伤**：**不要**向模板传递未在顶层解构的 Composable 包装对象；**放行/改用**普通响应式对象（reactive / 纯数据属性）在模板正常读取放行，Composable 返回的 Ref 必须在 `<script setup>` 顶层显式解构后绑定（曾导致模板渲染为 `[object Object]` 或失去响应性）。

### 6. View Transitions 边界与阅读器防抢占

- **本质**：浏览器全局快照排他，旧快照未决时触发新快照会被底层主动 `AbortError` 击穿。
- **复现场景**：读者在阅读器中连续快速按键盘左右翻页或快速跳话。
- **红线与防误伤**：**不要**在阅读器内部翻页切话时使用 `document.startViewTransition`；**放行/改用**跨页面大路由跳转（书架 ⇄ 详情 ⇄ 阅读器）正常使用全屏过渡（必须 catch 兜底），页面内局部微交互改用 Vue `<Transition>` 或局域 `element.startViewTransition`（曾导致快速翻页白屏崩溃）。

### 7. 硬件图层裁剪（contain: paint 陷阱）

- **本质**：CSS 合成层规范中 `contain: paint` 会强行裁切所有超出容器 padding-box 的像素。
- **复现场景**：在卡片容器声明 `content-visibility: auto`（隐式开启 `contain: paint`），同时卡片 Hover 向上浮动（`-0.35rem`）并投射柔和外阴影。
- **红线与防误伤**：**不要**在包含 Hover 浮动、叠牌倾斜或投影弥散的卡片上设置 `contain: paint` 或 `content-visibility: auto`；**放行/改用**纯扁平无溢出的静态列表放行，带立体浮动的卡片改用 `contain: layout style` 并借助 48 图预算分批增量渲染（曾导致上浮边缘与投影被硬切黑边）。

### 8. useMemoize 失败缓存残留与参数签名

- **本质**：`useMemoize` 默认将 rejected promise 留存于内存池中，导致下游重试永远命中历史异常。
- **复现场景**：快速切页导致请求被 `AbortController` 取消，随后再次点击该条目读取。
- **红线与防误伤**：**不要**允许异步 memoize 函数在 Promise reject 时保留缓存；**放行/改用**成功请求长期缓存放行，但必须在 catch 中调用 `.delete(key)` 清理失败记录，且包装函数必须显式声明完整参数签名（曾导致用户重试永久报 AbortError）。

### 9. 书架切页回源骨架屏闪烁（SWR 保持）

- **本质**：切页时无条件重置局部 `loading` 状态，破坏了已有数据的视觉连续性。
- **复现场景**：从详情页或阅读器返回书架首页，Store 重新拉取数据。
- **红线与防误伤**：**不要**在内存已有书架数据时将 `loading` 设为 true 触发 DOM 销毁重绘；**放行/改用**首次无数据进入或用户主动下拉刷新时正常展示骨架屏，日常切页改用 SWR 保持旧数据并在后台静默回源更新（曾导致切页瞬间卡片消失闪现骨架屏）。

### 10. UI 变体与 Composable 类型契约一致性

- **本质**：组件 Props 与底层状态机 TS 联合类型出现定义脱节，破坏了编译期类型安全屏障。
- **复现场景**：在模板中调用 `variant="solid"`，而底层组件仅定义了 `primary / secondary / ghost / soft / danger`。
- **红线与防误伤**：**不要**在组件调用处书写未在 Props 与 Composable 类型中定义的别名或弃用字段；**放行/改用**标准规范内的变体完全自由使用，任何新增变体必须在组件 Prop 与对应 Composable 的 TypeScript 联合类型中保持 1:1 声明。

### 11. 零伪图标字符与单源字典收敛

- **本质**：Unicode 字符受宿主操作系统字重/基线差异影响无法保持视觉一致，且散落的内联 SVG 破坏代码开闭原则。
- **复现场景**：在模板中直接书写 `'✕'`、`'✓'`、`'×'`、`'⋯'` 代替图标，读屏器将 `'×'` 读作“乘号”造成无障碍崩溃。
- **红线与防误伤**：**不要**在模板中使用文本伪字符或散写内联 `<svg>`；**放行/改用**常规标点符号与文字内容正常放行，所有图标必须统一收敛至 `src/components/icons/`（`BaseIcon` 底座 + 原子组件 + `AppIcon` 分发器）。

### 12. 零宿主机本地绝对路径（Zero Local Path Leakage）

- **本质**：将宿主机私有文件树或协议固化到受控文档中，破坏了代码资产的可移植性与隐私隔离。
- **复现场景**：AI 助手在对话中生成 `file:///home/miku/...` 点击链接后，直接原样落盘到 Markdown 文档、配置或代码中。
- **红线与防误伤**：**不要**在仓库任何受控代码、文档或配置中写入包含宿主机盘符（`file:///home/...` 或 `C:\...`）的绝对路径；**放行/改用**服务端代码内部在运行时通过 `Path(__file__).resolve()` 或 `os.path.abspath()` 动态解析路径完全合法，仓库文档与跨文件引用一律使用相对路径（防止他人 clone 或部署时失效泄露）。

### 13. 详情页骨架屏与共享封面形变预热

- **本质**：在跨页动画关键帧尚未就绪时全屏切换占位，切断了 View Transition 的图层追踪连续性。
- **复现场景**：从书架点击漫画进入详情页，详情接口尚未返回时。
- **红线与防误伤**：**不要**在详情数据返回前全屏呈现纯灰骨架屏；**放行/改用**利用书架已有 `LibrarySummary` 先渲染 Hero 头部（标题与封面），使 View Transition 能精准捕获并连贯完成共享封面形变（`comic-cover-active`），且在卡片上增加 `@pointerenter.once` 意图预热（杜绝白屏/骨架屏二次闪烁与排版跳动）。

### 14. PWA 鉴权端点与离线缓存隔离（API Metadata Cache Ban & Apple Touch Icon）

- **本质**：将状态敏感型 API 纳入 Service Worker 离线缓存策略，导致客户端身份被陈旧响应持久劫持；或 iOS PWA 缺失标准 180px PNG 根文件导致添加到主屏幕图标变截图。
- **复现场景**：Workbox 将 `/api/*`（如 `/api/library`、`/api/settings`）纳入 `NetworkFirst`，反向代理或弱网下命中未授权缓存导致馆长权限丢失且必须全量重置；iOS Safari 找不到 180x180 图标回退抓取网页截图。
- **红线与防误伤**：**不要**在 Service Worker（Workbox）中缓存任何 `/api/` 数据端点（严禁配置 `api-metadata-cache`），**不要**在 `index.html` 仅书写 192px 尺寸图标；**放行/改用**Service Worker 仅缓存静态 App Shell 与二进制漫画画页（`manga-images-cache`），动态 API 统一走内存 SWR（`useMemoize`）直连后端；`public/` 与 `index.html` 必须提供标准 180×180 `apple-touch-icon.png` 与通配链接。

### 15. 后台轮询容错与熔断隔离

- **本质**：未对网络或服务异常设置阻尼与熔断机制，引发无意识的客户端自挂式拒绝服务（DDoS）。
- **复现场景**：后端停机、重启或发生 401 鉴权失效时，前端 `useIntervalFn` 依然每 2 秒高频死循环重试。
- **红线与防误伤**：**不要**在后台定时轮询任务遇到网络或鉴权报错时静默重试；**放行/改用**正常状态轮询放行，但 catch 必须调用 `poll.pause()` 立即熔断，且跨路由共享的状态必须使用 `createGlobalState` 单例化管理（防止浏览器高频重试引发自挂式请求风暴与 WAF 封锁）。

### 16. CDN 静态路由别名与穿透防线

- **本质**：主流 CDN 对无扩展名的 URL 默认视为动态不可缓存内容，导致边缘节点强缓存规则失效。
- **复现场景**：图片与缩略图请求采用无扩展名的裸 API 路径（如 `/file`、`/thumbnail`）。
- **红线与防误伤**：**不要**让图片与缩略图仅使用无静态扩展名的裸 API 路径；**放行/改用**普通数据接口保持 RESTful 规范，静态媒体必须提供 `.webp`、`.jpg` 路由别名并在 Cloudflare 等 CDN 配置静态规则（防止跨洋公网单张图片卡顿数十秒）。

### 17. 容器探针日志静音（Noise Suppression）

- **本质**：高频机械性探活流水打满进程 stdout，淹没真实的业务异常与访问审计日志。
- **复现场景**：Kubernetes / TrueNAS 容器每隔几秒发起一次 `/api/health` 探针检查，控制台狂刷 200 OK。
- **红线与防误伤**：**不要**让心跳探针的 200 OK 正常流水日志打满 Uvicorn 控制台；**放行/改用**业务 API 正常记日志，心跳探针必须通过 `QuietAccessLogFilter` 过滤静音，并在部署时支持 `COMIC_SHELF_ACCESS_LOG=false` 彻底消除刷屏。

### 18. SQLite 静态请求写放大与 WAL 单写者锁竞争（Write Amplification in Read Hotpaths）

- **本质**：在每页图片/二进制只读请求中同步执行数据库写事务（如高频更新 `last_active_at`），使 WAL 模式全局单写者的特性成为系统吞吐瓶颈。
- **复现场景**：访客阅读漫画时瞬时预加载 10~20 张图片，每个请求同步执行 `UPDATE guest_devices` 并 commit，导致多线程排队争抢 SQLite 写锁触发 `busy_timeout` 与图片加载卡顿。
- **红线与防误伤**：**不要**在静态资源读取或高频只读请求路径上无条件同步写数据库；**放行/改用**业务写操作正常提交，活跃时间与心跳等审计字段必须基于内存已有数据做阈值防抖（如时间间隔 > 60s 或 IP 发生漂移才执行一次写入），消除 95%+ 的磁盘与锁开销。

### 19. 批量并发静态资源误触发令牌桶限流（Rate Limiting False Positives on Bulk Views）

- **本质**：将针对单连续阅读流（如顺序翻页）的限流桶错误套用到聚合首屏（如书架多本漫画封面并发加载），单次聚合请求瞬间耗尽突发桶。
- **复现场景**：访客进入书架时浏览器并发请求 50+ 本漫画封面 `/cover`，耗尽 45 张突发配额，导致后续封面 429 裂图，并在管理端名册被误打上“〔 ⚠️ 速率受限 〕”警示印章。
- **红线与防误伤**：**不要**将首屏聚合展示资源（如书架封面）与单流程翻页限流绑定在同一突发桶中；**放行/改用**正文大图（`/file`、`/thumbnail`）实施严格令牌桶限流防范爬虫与带宽拉满，但书架封面等首屏聚合视图必须独立解耦或单设预算，杜绝正常浏览破图。

### 20. Check-Then-Act (TOCTOU) 并发穿透配额上限（Deferred Transaction Race Condition）

- **本质**：依赖 SQLite 默认延迟事务（DEFERRED）的先查后插逻辑无法互斥排他，并发请求同时读到未满额状态，双双插入导致突破配额。
- **复现场景**：同一访客通行证并发发起多次设备登入，多线程同时执行 `SELECT count` 均发现小于 `max_devices`，导致绑定设备数超出配额上限且逃逸 LRU 淘汰与熔断锁。
- **红线与防误伤**：**不要**在多线程或并发请求中依赖普通的 `SELECT` 做配额守卫；**放行/改用**进入临界区必须开启 `BEGIN IMMEDIATE` 排他事务或进程互斥锁，确保“查额度-淘汰旧端-插入新端”严格原子化执行。

### 21. 移动端折叠动效与隐藏表单的键盘焦点穿透（A11y Focus Leakage in Collapsible Components）

- **本质**：纯 CSS 高度动画（如 `grid-template-rows: 0fr ⇄ 1fr` 搭配 `overflow: clip`）仅在视觉渲染层收起尺寸，但内部聚焦元素（`<input>`、`<button>`）仍停留在 DOM 可访问性与 Tab 导航树中。
- **复现场景**：移动端折叠卡片在折叠状态下，用户使用外接键盘或读屏设备按 `Tab` 键，光标意外跳入视觉上已折叠不可见的输入框中，引发视口异常滚动与失焦。
- **红线与防误伤**：**不要**仅依赖 `height: 0`、`overflow: clip` 或 `opacity: 0` 来实现无障碍组件折叠；**放行/改用**展开态保持 `visibility: visible`，折叠态必须配置 `visibility: hidden` 并搭配延时过渡（`transition: visibility 0s var(--duration-2)`），确保在动画收起结束后彻底剥离 Tab 焦点流。

### 22. 多数据源表单上下文隔离与非相关设置污染（Contextual Settings Leaks Across Import Sources）

- **本质**：将特定数据源特有的操作（如远端抓取的并发限制与离线预热）全局平铺在通用表单中，破坏了「本地自建」与「远端收录」的领域模型边界。
- **复现场景**：切换到「本地自建 / 拆帧」时，界面仍暴露「同时缓存全部页面」与「下载并发（X 路/次）」，让用户误以为本地图集需要走远端网络并发通道。
- **红线与防误伤**：**不要**在跨数据源导入面板中无条件展示特定 Provider 的网络专属设置；**放行/改用**全局偏好（如「新入库默认对访客隐藏」）保持常驻，但网络并发与预拉取选项必须严格限定在远端 Provider（`activeTab === 'jm'`）作用域内。

### 23. 组件拆分真空与 Composable 无脑全量解构（Doc Vacuum & Indiscriminate Destructuring）

- **本质**：在追求组件瘦身与 Composable 下沉时，只做代码物理搬移而缺失 JSDoc/TSDoc 契约注释，并在消费层将 Composable 返回值一股脑全量解构，引发 TS6133 冗余声明与模板漏绑。
- **复现场景**：从阅读器抽离出 `useReaderNavigation`、`useReaderKeyboard`、`useReaderPaging` 等 Hook 后，在 `ReaderView.vue` 中无脑解构所有内部状态（如 `isWideViewport`、`chapters`、`startAutoTurnCountdown`），且新建的 10+ 个子组件未写 Props/Emits 描述与职责注释，导致后续维护黑盒化。
- **红线与防误伤**：**不要**在新建/重构 Composable 与子组件时裸写无注释代码，**不要**在消费处全量解构未使用的内部状态；**放行/改用**每个 Composable 必须提供头部职责说明、入参/返回值 JSDoc，子组件必须声明 Props 业务含义与 Emits 契约，视图消费层必须**按需精准解构**实际使用的 Ref 与函数。

### 24. ARIA 角色属性与无障碍名称规范（ARIA Roles & Accessible Names Mismatch）

- **本质**：在非交互无语义容器（如 generic `<div>` / `<span>`）上放置仅适用于交互控件的状态属性（如 `aria-haspopup`、`aria-expanded`、`aria-controls`），破坏了 W3C HTML-ARIA 语义模型；以及定义 `role="progressbar"` 时缺少可访问名称（`aria-label` / `aria-labelledby`），导致读屏器通用化识别与 Lighthouse / Axe-core 审计报错。
- **复现场景**：`AppPopover.vue` 将 `aria-haspopup` / `aria-expanded` 直接放置在作为 CSS Anchor 容器的 `<div class="app-popover-trigger">` 上；`CacheProgress.vue` 与 `StorageGaugeSection.vue` 声明了进度条角色但未配置 `aria-label`。
- **红线与防误伤**：**不要**在 generic `<div>` / `<span>` 上挂载控件状态属性，**不要**让 `role="progressbar"` 缺少可访问名称；**放行/改用**浮层的展开状态与控制关系统一收敛至插槽内部真实的 `<button>` 触发器节点，进度条轨道必须显式挂载 `:aria-label="label"` 提供清晰的无障碍读屏语义。

### 25. 静态传输未压缩与初始关键请求链预热污染（Render-Blocking CSS & Eager Prefetch Contamination）

- **本质**：单容器部署时未在后端开启 GZip 动态压缩导致大体积静态文件未压缩传输，且在组件挂载阶段（`onMounted`）同步 `import()` 目标路由 chunk，将未来视图的 JS/CSS 强行拉入当前页面的关键请求链（Critical Request Chains），引发首屏 LCP 与 FCP 严重降速。
- **复现场景**：FastAPI 未挂载 `GZipMiddleware` 使得 `index.css`（78 KiB）未压缩直传；`ComicDetailView.vue` 在 `onMounted` 中同步调用 `import('@/views/ReaderView.vue')`，导致 `ReaderView.css` 混入详情页首屏加载瀑布流。
- **红线与防误伤**：**不要**在服务端缺失传输层压缩中间件，**不要**在组件 `onMounted` 阶段同步预热未来路由；**放行/改用**后端挂载 `GZipMiddleware(minimum_size=1000)` 压缩静态资产与 API，前端路由预热改用 `requestIdleCallback` 闲时调度与 `pointerenter`/`focusin` 意图预热（Intent Prefetch），确保首屏关键链路轻量纯净。

### 26. 移动端阅读器高度塌陷与替换元素内生尺寸坍塌（CSS Flex/Grid Basis Collapse & Replaced Element Intrinsic Sizing）

- **本质**：在弹性盒/网格父容器高度为 `auto` 时，`flex: 1; min-height: 0;` 子元素的计算基准（flex-basis）解析为 0，导致内部百分比高度的 `<img>` 替换元素坍塌触底至兜底 `min-height: 40px`，并按原生宽高比反向收缩为 28px × 40px 的微缩邮票。
- **复现场景**：原样式仅在 `@media (min-width: 681px)` 声明了 `.reader-page` 高度，移动端（<681px）缺失显式高度；且将连续条漫流（`vertical-continuous`）与分页 Contain 模式混写，并在画面中央悬浮遮挡画卷的药丸折叠按钮。
- **红线与防误伤**：**不要**在移动端 `height: auto` 的弹性父级下给替换元素设百分比高度，**不要**在阅读器中放置遮挡正文的悬浮折叠控件，**不要**将条漫模式与分页模式尺寸规则强行混杂；**放行/改用**连续滚动流采用自然文档流（`width: 100%; height: auto`），图片外层采用 Flexbox 居中并配合 `aspect-ratio: 0.72` 预占位，工具栏显隐统一由全屏轻触（Tap/Click-to-Toggle）驱动并在无操作 2.6s 自动淡出（杜绝首屏 9+ 页邮票排版崩溃与画卷遮挡）。

### 27. CSS ScrollTimeline 坐标镜像反转与主线程重排抖动（RTL Scroll Coordinates Inversion & Layout Thrashing in Dual-Track Scroll Architecture）

- **本质**：在 RTL 横向模式下，`scrollLeft` 物理原点与阅读逻辑相反，未做关键帧镜像会导致 CSS 进度条从 100% 倒退至 0%；且在双轨架构中，若 JS `onScroll` 每帧同步密集读取 `offsetLeft/offsetTop`，会引发主线程 Layout Thrashing，击穿合成器线程（Compositor Thread）的性能红利。
- **复现场景**：在日漫模式从右往左翻页时，CSS 进度条一打开就是 100% 满格，往左翻反而越来越短；长图集快速滑动时 `onScroll` 高频读取 DOM 导致滑动掉帧卡顿。
- **红线与防误伤**：**不要**在 RTL 模式下直接复用 LTR 的 0%->100% 关键帧，**不要**在滚动事件处理函数中无节流密集读取 DOM 几何属性；**放行/改用**RTL 模式使用 `@keyframes reader-progress-rtl { from { transform: scaleX(1); } to { transform: scaleX(0); } }` 搭配 `transform-origin: 100% 50%`，JS 轨必须通过 `requestAnimationFrame` 调度节流并配合 `onScopeDispose` 清理定时器（确保 120fps 满帧与双轨 100% 逻辑一致）。

### 28. 视口挂载与初次定位时序脱节导致阅读进度重置（DOM Mount Timing & Initial Positioning Failure Under v-if="loading"）

- **本质**：在 Composable（如 `useReaderData`）生命周期中，若数据到达后先执行 `onLoaded` 回调、之后才将 `loading.value` 置为 `false`，而视图层的真实画卷视口（`ReaderViewport`）受 `v-if="!loading"` 控制；导致 `onLoaded` 内部即使调用 `await nextTick()`，DOM 滚动容器（`scrollEl`）也尚未挂载，使得物理瞬时定位 `scrollToGroup(..., 'instant')` 静默失败并停留在第 1 页，随后滚动容器的默认 0 偏移量反向触发 `handleScroll` 冲刷覆写用户的 `lastRead` 阅读历史。
- **复现场景**：读者从漫画详情页「页面索引」或「继续阅读」点击跳转至 `/comic/:source/:id/read/:page` 时，无论点击第几页，阅读器均被重置到第 1 页且历史记录被冲刷为 1。
- **红线与防误伤**：**不要**在数据加载 Composable 中将 `loading = false` 延迟到依赖 DOM 的 `onLoaded` 之后；**放行/改用**遵循「数据就绪 → 先解除 `loading = false` → 触发 `onLoaded` / `await nextTick()` 物理瞬时定位」的单向流水线原则；并在路由未携带 `:page` 时优先回落至本地持久化 `lastRead.value`，纵向连续模式下由 `recalibrateTargetOffset` 在图片异步加载时微调位移（确保 0 丢帧与 100% 精确进场定位）。

### 29. PWA Prompt 模式装订更新死锁与 Service Worker controlling 事件缺失兜底（PWA Prompt Mode Update Deadlock & Missing Fallback Reload）

- **本质**：在 PWA Prompt 模式下，调用 `updateServiceWorker(true)` 仅向 Service Worker 发送 `SKIP_WAITING` 消息，完全依赖底层 `workbox-window` 监听的 `controlling` 事件且其内部要求 `event.isUpdate == true` 才能执行 `window.location.reload()`。在单容器静态托管、本地开发历史缓存或特定浏览器生命周期边缘态下，`controlling` 事件可能无法满足条件或未能触发，而业务层将 `isUpdating` 置为 `true` 后缺乏安全熔断与超时重载保底，导致装订按钮陷入无限旋转动画死锁。
- **复现场景**：在浏览器检测到新版本并弹出「纸间已有新卷本装订就绪」横幅时，点击「立即装订」，按钮显示「装订中…」并一直转圈，页面未自动刷新。
- **红线与防误伤**：**不要**仅将页面刷新的控制权完全交给未设超时的底层第三方 SW 事件监听；**放行/改用**在 `usePwaUpdate.ts` 中显式绑定 `navigator.serviceWorker` 的 `controllerchange` 监听，向 `waiting` Worker 直接派发 `SKIP_WAITING` 信号，并设立 **1.2s 安全熔断定时器（Fallback Reload）**，无论底层事件是否准时到达均保证窗口平滑重载生效（彻底根治装订无限转圈死锁）。

### 30. 后台缓存长任务与前台进度时序竞态（High-Water Mark & Live Cache Lock Race Condition）

- **本质**：在后台轮询任务完成时，先移除了进行中状态锁，而全量快照尚未回源落地，导致视图层瞬间降级回退至旧快照值（如初始 4 张封面）；或在轮询网络抖动时无序覆写进度值。
- **复现场景**：后台预缓存任务完成时，书架卡片进度条从 100% 突然跳回 4%，几百毫秒后等 `loadItems()` 返回才再次跳回 100%；或详情页初次进入时章节缓存数瞬间归 0。
- **红线与防误伤**：**不要**在后台任务从运行列表消失时立即释放前端实时缓存状态；**放行/改用**必须先异步执行 `await loadItems(true)` 同步最新快照再原子化解封 `liveCache`，在轮询闭环中引入 `Math.max(cached, prevMax)` 高水位单调递增防护，并在 SWR 占位初始化时预填对应长度的占位页（彻底杜绝进度骤降跳变与闪烁）。

### 31. Uvicorn StatReload 全仓扫描假死与轮询无锁导致浏览器 Socket 连接池耗尽（Uvicorn StatReload Scan Deadlock & Browser 6-Socket Starvation）

- **本质**：
  1. 后端 Uvicorn 未安装 `watchfiles` 时降级为低效的 `StatReload`，未配置 `reload_dirs` 时默认扫描全仓（含 30,000+ 文件的 `node_modules/` 与海量图片的 `backend/data/`），CPU 占用飙满且在 SQLite 写入 `comic_shelf.db` 时频繁引发误重启，造成“后端不热更新或假死”；
  2. 前端 `useIntervalFn` 异步轮询缺失并发互斥锁（`isPolling`），在服务重启或网络延迟时定时器无脑发射新请求，快速超出 HTTP/1.1 浏览器单域名 6 个并发 TCP Socket 上限，导致连接池被彻底打满，后续全站接口（如 `/api/library`、`/api/auth/status`）全被 Chrome 强行挂起在 `(待处理)` 状态；
  3. 前端 `fetch` 缺少默认超时保护，挂起的连接永久占死浏览器连接槽位。
- **复现场景**：启动开发环境后修改 Python 代码服务无反应或频繁假死；网络面板中 `jobs` 接口每隔 2 秒发起一次且全部处于 `(待处理)` 状态，累积十余个后连正常页面 `library` 接口也变成 `(待处理)` 无法加载。
- **红线与防误伤**：
  - **不要**让 Uvicorn 在未安装 `watchfiles` 的情况下裸跑全仓 `StatReload`，**不要**在 `reload` 中监听 `data/` 和 `node_modules/`；
  - **不要**在前端异步轮询定时器（`useIntervalFn`）中直接裸调 `await api.xxx()` 而不设 `isPolling` 防并发重入锁；
  - **不要**使用无超时的原生 `fetch` 处理关键 API；
  - **放行/改用**：
    1. 虚拟环境强制安装 `watchfiles>=1.0.0`，Uvicorn 显式指定 `reload_dirs=[backend/app]` 并严格配置 `reload_excludes`；
    2. 所有轮询方法（书架 `refreshLiveCache`、详情/章节 `cacheProgress`）必须挂载 `isPolling` 并发锁，未决时丢弃新 tick，并绑定 `AbortController`；
    3. 全局 API 请求统一封装 15s 超时控制器（`combineSignals` + `TimeoutError`），杜绝霸占浏览器 Socket 槽位。

### 32. 盒模型伪元素导致浮层误触滚动条与尖角装饰裁切（Pseudo-Element Scrollbar Leakage & Arrow Clipping）

- **本质**：具有绝对定位负边距/偏移的伪元素（如指示小三角 `::before`、WCAG 悬停安全桥 `::after`）属于容器盒模型的溢出部分。若浮层根节点声明了 `overflow-y: auto`，浏览器会将其一律判定为纵向溢出（`scrollHeight > clientHeight` 恒成立），导致即使仅有 1~2 行短文本也会被强行渲染出灰色垂直滚动条，且将伸出盒外的尖角箭头硬切消失。
- **复现场景**：悬停在仅有两行文字的作品名气泡上，右侧常驻禁用样式的垂直滚动条，指示箭头消失不见。
- **红线与防误伤**：
  - **不要**在包含外部定位伪元素（小三角、安全桥）的浮层根容器上直接设置 `overflow: auto` 或 `overflow-y: auto`；
  - **放行/改用**根容器严格保持 `overflow: visible; padding: 0;`，由内部独立的内容容器 `.tooltip__content` 承载 `padding` 与 `max-height + overflow-y: auto`，实现几何装饰与内部滚动的物理分层。

### 33. CSS Anchor 碰撞翻转与静态类名脱节导致指示箭头指错方向（Anchor Inline-Flip & Desynced Arrow Alignment）

- **本质**：CSS Anchor Positioning 在视口边界触发 `position-try-fallbacks: flip-inline` 水平翻转（如 `span-right` 翻转为 `span-left`）时，若 Vue 模板中的对齐类名仍然静态绑定 `props.align`（`align-start`），会导致指示小三角继续停留于左侧（`left: 0.85rem`），而触发源已由于翻转位于浮层右侧，形成“指鹿为马”的严重视觉脱节。
- **复现场景**：在详情页右列（如作品、作者）悬停时，浮层因右侧空间不足翻转至左边，但小三角依然在左侧指向左列车号，与右列触发文字完全错位。
- **红线与防误伤**：

### 34. 路由历史栈污染与子视图层级回退混淆（Up Navigation vs History Back Loop）

- **本质**：将具有明确树状包含关系的“向上返回父级视图”（如章节子视图返回漫画详情页）实现为通用的浏览器后退 `router.back()`。当用户从子视图进一步深入（如进入阅读器）又退出后，历史栈中留存了阅读器条目，此时在子视图点击“返回本子详情”会被 `router.back()` 回弹推入阅读器，产生死循环。
- **复现场景**：从漫画详情页进入第 3 话子详情，点击阅读进入阅读器，退出阅读器回到第 3 话子详情；此时点击左上角“返回本子详情”，页面重新跳转进入阅读器。
- **红线与防误伤**：
  - **不要**在明确语义为“向上返回父级”的按钮上使用通用 `router.back()`；
  - **不要**在子模块退出（如阅读器退出）时使用 `router.push` 累加中间游走历史；
  - **放行/改用**：
    1. 子详情返回父详情统一使用确定性路由 `router.push('/comic/:source/:id')`；
    2. 退出深层临时界面（阅读器、全屏浮层）使用 `router.replace` 就地替换历史栈；
    3. 父级视图配合 `onBeforeRouteLeave` 记录滚动高度，返回时精准还原，杜绝跳顶。

### 35. 长篇未缓存作品的无休止轮询空转（Job-driven Polling Guard）

- **本质**：将 `cached < total` 单纯作为轮询启动条件。在后台并无任何下载任务（`job.running === false`）且长篇漫画（如数千页）尚未完全离线时，前端进入 1s 间隔的无休止轮询死循环，白白消耗后端连接池与前端主线程资源。
- **复现场景**：读者打开包含 7000 页的未缓存漫画详情页，虽然并未点击任何下载按钮，但浏览器网络面板每秒持续发起 `GET /cache` 请求，CPU 负载无法回落。
- **红线与防误伤**：
  - **不要**仅凭页码未满开启自动轮询；
  - **放行/改用**严格的任务驱动机制：仅当 `job.running === true` 时才启动轮询，一旦后台任务完成或进入页面探测到无活跃任务，立即执行 `pause()` 暂停轮询，静默状态 CPU 占用归零。

### 36. 盲从 IDE 警告双写未熟 CSS 属性与前缀级联倒置（Vendor-Prefix False Alarms & Cascade Inversion）

- **本质**：盲从 IDE 静态语法检查的通用提示，在尚未落地的规范过渡期盲目双写伪标准属性（如尚未普及且规范演进中的无前缀 `line-clamp`），或将标准属性声明置于前缀属性之前，导致现代标准行为被遗留前缀语法反向覆盖。
- **复现场景**：
  1. VS Code 报 `Also define the standard property 'line-clamp' for compatibility`，开发者顺从提示盲目补上 `line-clamp: 2`；
  2. 在组件样式中先写标准属性 `mask-image` / `backdrop-filter`，后写 `-webkit-` 前缀，导致标准行为被前缀覆盖；
  3. 残留 2011 年 iOS 5 时代的 `-webkit-overflow-scrolling: touch` 废弃死代码。
- **红线与防误伤**：
  - **不要**盲目顺从 IDE 提示双写尚未全浏览器正式 Baseline 的标准属性（如 `line-clamp`）；在 `.vscode/settings.json` 中配置 `"css.lint.vendorPrefix": "ignore"` 消除虚假噪音；
  - **不要**在同一规则块中将标准属性写在 `-webkit-` 前缀前面；
  - **不要**保留已废弃且现代移动端默认自带的原生特性（如 `-webkit-overflow-scrolling`）；
  - **放行/改用**：
    1. 文本截断统一收敛至 `<AppTextClamp>` 原子组件或全局 `.line-clamp-N` 实用类；
    2. 多浏览器前缀与标准并存时，严格执行“前缀在前、标准在后”的级联顺序（前缀兜底，标准覆盖）。

### 37. 单话离线画页缓存误标与非连续页码污染（Chapter-Scoped Cache Page Index Pollution）

- **本质**：在引入单话按需离线缓存后，若前端轮询盲目复用全书顺序下载时假设的 `p.index <= progress.cached` 进行本地就地更新。单话缓存任务通常从中间章节页码（如 `index = 46`）开始下载，而全局累加的已缓存数（如已下完 5 页，`progress.cached = 5`）会导致第 1 话的前 5 页被虚假误标为 `cached = true`，而真正下载的第 3 话画页因 `index >= 46` 始终无法被标记，且任务结束时由于全书 `progress.complete` 为 false 导致单话状态永久脱节。
- **复现场景**：用户点击第 3 话「缓存本话」，第 1 话画页角标突然亮起，第 3 话画页进度纹丝不动，直到手动硬刷新才同步。
- **红线与防误伤**：
  - **不要**在单话缓存任务中使用全局页码阈值 `p.index <= progress.cached`；
  - **放行/改用**：轮询时识别 `job.chapter_id`，基于 `job.prefetched` 精确计算并仅标记该话范围内的画页（`p.chapter === ch.id && p.index <= ch.start + job.prefetched - 1`）；并在任务结束或完成时触发一次静默 `load(true)` 同步最新权威状态。

### 38. 误将跨路由持久状态置于 `<script setup>` 实例闭包内（`<script setup>` State Persistence Trap）

- **本质**：误将跨路由需要恢复的内存状态（如离开视图时的滚动位点 `detailScrollPositions`、虚拟/分批渲染的展开折叠计数 `expandedChapterCounts`）以普通顶级变量声明在 `<script setup>` 内部。在 Vue 3 中，`<script setup>` 的顶层代码属于组件实例的 `setup()` 函数内部闭包，每次跨路由离开并再次进入时组件重新实例化，状态被重置为空对象 `{}`，记忆机制完全失效。
- **复现场景**：读者在包含 150 话的详情页展开至第 80 话并滚动到下方，点击某话进入 `ChapterView` 再点击返回，详情页重置回第 1 屏 24 话并滚到顶部。
- **红线与防误伤**：
  - **不要**在 `<script setup>` 声明需要跨组件销毁/挂载存活的页面级状态；
  - **放行/改用**：将跨路由/跨实例持久状态提升至独立的 Composable / Store 模块顶层单例，并提供规范的 getter/setter 与清理函数。

### 39. 原生 `<dialog>` 顶层浮层陷阱与 CSS 覆盖（Top Layer & User-Agent Stylesheet Collision）

- **本质**：原生 `<dialog>` 的 User-Agent 样式（`dialog:not([open]) { display: none }`）优先级极低，极易被常规 CSS 类选择器（如 `.modal-root { display: grid }`）意外覆写；且 `dialog::backdrop` 作为独立的 Top Layer 渲染盒，绝不自动继承 `<dialog>` 容器的 `opacity` / `transform`，与 Vue 响应式卸载时机脱节导致全屏点击锁死或黑屏硬闪。
- **复现场景**：
  1. 将普通模态窗迁移为 HTML5 `<dialog>` 时，为尝试纯 CSS 离散属性过渡而移除了 `v-if="open"`；
  2. 外层 CSS 类显式声明了 `.modal-root { display: grid; position: fixed; inset: 0; }` 且内部遮罩带有 `pointer-events: auto`；
  3. 导致页面在默认关闭状态下，被一层全屏透明的幽灵遮罩截断全部鼠标点击，平台所有交互瘫痪；
  4. 此外，直接使用 `::backdrop` 承接视觉黑色高斯模糊时，Vue `<Transition>` 只能改变 `<dialog>` 本身透明度，离开时黑色蒙层无法同频淡出，DOM 卸载瞬间产生生硬黑屏闪退。
- **红线与防误伤**：
  - **不要**在复杂声明式框架（Vue/React）中为追求纯 CSS 动画而移除 `<dialog>` 的 `v-if="open"` 物理隔离；
  - **不要**让组件 CSS 类无条件给未打开的 dialog 赋予 `display: grid/flex`；
  - **放行/改用**：
    1. 模态窗外层必须使用 `<dialog v-if="open">` 配合 `<Transition>`，确保关闭态物理脱离 DOM 树，从物理根源杜绝幽灵遮罩；
    2. 将 `dialog::backdrop` 保持透明，仅利用其顶级原生阻断点击能力，将视觉墨色与 4px 模糊交由内部 `.modal-scrim` 管理，实现蒙层与面板 100% 同频丝滑淡入淡出；
    3. 在 CSS 中补充 `dialog:not([open]) { display: none !important; }` 作为样式级双重防线；
    4. **即便使用了原生 `<dialog>`，模态窗外层仍需坚守 `<Teleport to="body">`**：Top Layer 仅改变屏幕渲染层叠，不改变 DOM 树父子拓扑。保留 Teleport 是为了：① 彻底隔绝宿主节点的 CSS 属性与局部 `--*` 变量继承；② 阻断内部原生点击事件向调用处祖先冒泡击穿；③ 免疫祖先节点 `display: none`（如 `v-show="false"` 或未激活 Tab）导致无法生成盒模型（Box Generation）使顶层弹窗无法渲染；④ 确保自动化单测（JSDOM）与降级模式下的全屏 fixed 视口依然稳固。

### 40. HTML Invoker Commands API 与 Click 冒泡的双重触发冲突（Invoker Commands & Bubble Race）

- **本质**：HTML Invoker Commands API（`commandfor` / `command`）是现代浏览器（Baseline 2025/2026）的声明式交互规范。当包含 `commandfor` 的按钮被点击时，浏览器在底层会原生派发 `CommandEvent` 驱动目标弹窗/浮层状态，但原生 `click` 事件仍会照常产生并向上冒泡。若外层父容器同时监听了 `@click="toggle()"`，会导致同一次点击内状态被连续翻转两次（例如打开后立刻被再次关闭，造成“点击无反应”或闪退）。
- **此外**：原生 `command="close"` 默认行为会直接同步调用目标 `<dialog>` 的 `close()` 方法，抹去其 `open` 属性，导致 User-Agent 样式（`dialog:not([open])`）立即生效，硬生生掐断 Vue `<Transition>` 的离场淡出过渡动画；且原生的直接关闭会绕过业务侧的 `preventClose` 保护。
- **红线与防误伤**：
  - **不要**在带有 `commandfor` 的组件中，在外层 `@click` 中无条件执行二次 `toggle()`；
  - **不要**在 `<dialog>` 的 `@command` 事件监听中遗漏 `event.preventDefault()`；
  - **放行/改用**：
    1. 在触发器容器点击处理中，检测若触发源包含 `[commandfor]` 且当前浏览器原生支持 `commandForElement`，由浏览器原生处理，跳过手动的 JS `toggle()`；
    2. 在 `<dialog>` 的 `@command` 处理器中执行 `event.preventDefault()` 接管关闭流程，并在此阻断 `props.preventClose`（触发微弹提醒），随后通过响应式变量驱动 Vue `<Transition>` 优雅离场。

### 41. PWA 预缓存动态多媒体资产泄漏与虚拟模块隔离（Precache Media Bloat & Virtual Module Isolation）

- **本质**：使用 `import.meta.glob('/public/...')` 扫描 public 静态资产时，Vite 会将其判定为工程依赖并无差别克隆拷贝至 `dist/assets/` 中；同时 VitePWA 的 Workbox 预缓存探测默认会将其全部纳入 App Shell 静态预缓存清单，导致首屏静态预缓存（Precache）瞬间从原本的 ~900 KiB 暴涨至近 10 MB（例如 Live2D 动画 `loading-tiya.webp` 3.98 MB 与多张插画），严重阻断首屏网络并浪费读者手机流量。
- **红线与防误伤**：
  - **不要**对 `public/` 目录下的大体积多媒体、动图或按需资产使用 `import.meta.glob`；
  - **不要**将运行时动态插画无条件塞入 `includeAssets`；
  - **放行/改用**：
    1. 在 `plugins/illustrations.ts` 中编写 Vite 虚拟模块插件（`virtual:illustrations`），在编译期仅扫描文件系统并输出轻量纯文本路径数组（`['/loading-1.webp', ...]`），零资产克隆；
    2. 在 Workbox 配置中将 `globIgnores: ['**/loading-*']` 排除核心预缓存，改为通过 `runtimeCaching` 注册 `illustration-pool-cache`（`CacheFirst`），实现运行时按需懒加载并离线驻留。

### 42. iOS WebKit 针对 Web App Manifest 凭据限制（iOS PWA Manifest Credential Drop）

- **本质**：iOS Safari / WebKit 在解析 `<link rel="manifest">` 时对凭据配置（`crossorigin="use-credentials"`）有极其严苛且反直觉的阻断行为。当在 VitePWA 中配置了 `useCredentials: true` 时，WebKit 会判定请求需要同源认证而直接静默丢弃该 Manifest 响应，导致在 iOS Safari 点击“分享 ➔ 添加到主屏幕”时完全不识别 PWA 特性，仅能生成一个普通的 Safari 网页快捷方式，且无法以 Standalone 独立视口启动。
- **红线与防误伤**：
  - **不要**在不需要跨域鉴权的 Web App Manifest 上配置 `useCredentials: true`；
  - **放行/改用**：保持 Manifest 公开无凭据获取（默认 `crossorigin="anonymous"` 或不传凭据），并在 `index.html` 的 `viewport` 中补充 `viewport-fit=cover` 以支持 iPhone 灵动岛/刘海屏安全边距自适应。

### 43. Service Worker 活跃连接阻断与浏览器缓存重置竞态（SW Active Connection & Storage Teardown Race）

- **本质**：在客户端执行“重置全部离线环境”时，若直接调用 `indexedDB.deleteDatabase()`，正在运行中的 Service Worker 或当前页面并发请求极易持有 open 数据库连接，导致删除操作永久停留在 `blocked` 挂起态；此外，若未注销 Service Worker 或注销后未刷新页面，页面上已挂载的 `<img>` 标签会立即触发活跃 Service Worker 的 Fetch Handler 重新抓取并写回 `CacheStorage`，导致用户点击“清空”后数据看似完全没有被清空。
- **红线与防误伤**：
  - **不要**在重置时仅调用 `indexedDB.deleteDatabase()` 而不预先清空内部存储表；
  - **不要**在注销 Service Worker 后停留在当前页面不触发刷新；
  - **放行/改用**：
    1. 区分细粒度清理与整库重置：局部清理（如清空画页）仅清空目标 `objectStore.clear()`（保护插画池等其他 Runtime 缓存的元数据），仅在全局重置时清空并注销整库；
    2. 对 IndexedDB 打开与事务操作绑定 1.5s 兜底超时与 `onabort` 监听，防止连接或锁死导致 UI 永久 loading；
    3. 注销 Service Worker 注册项并调用 `caches.delete()` 遍历清理；
    4. 在全局重置末尾设置 600ms 定时器强制执行 `window.location.reload()`，彻底斩断 Service Worker 的幽灵线程连接并刷新所有前端内存状态。

### 44. Vite 虚拟模块在 load() 钩子误调 this.addWatchFile 触发目录导入解析崩溃（Vite Virtual Module addWatchFile Directory Panic）

- **本质**：在 Rollup 中，`this.addWatchFile(path)` 仅作为监听外部文件/目录变化的构建辅助；但在 Vite 的开发服务容器（`LoadPluginContext`）中，`addWatchFile` 会将传入的路径直接推入 `this._addedImports`。随后在 Vite 的 `vite:import-analysis` 插件对虚拟模块进行转换时，会无差别遍历 `_addedImports` 并调用 `this.resolve(id, importerFile)` 将其解析为 ES 模块依赖。若在 `load()` 中对目录路径（如 `public/`）或非模块静态资源调用了 `this.addWatchFile(publicDir)`，Vite 的解析器会因为目录无法被当作 JavaScript 模块 resolve 而直接崩溃，抛出 `Internal server error: Failed to resolve import ".../public" from "virtual:illustrations". Does the file exist?`。
- **红线与防误伤**：
  - **不要**在 Vite 插件的 `load()` 或 `transform()` 中对目录路径或非模块静态资源调用 `this.addWatchFile()`；
  - **放行/改用**：
    1. 静态目录或非模块文件的变更监听统一迁移到插件的 `configureServer(server)` 钩子中，利用 `server.watcher` 监听文件事件（`add`、`unlink`、`change`）；
    2. 探测到目标文件过滤匹配后，通过 `server.moduleGraph.getModuleById(resolvedVirtualModuleId)`（或 Vite 6 环境 API 的 `client.moduleGraph`）精准标记失效（`invalidateModule`），并通过 `server.ws.send({ type: 'full-reload', path: '*' })` 平滑触发重载；
    3. 模块内部解析目录时，使用兼容 Node 原生与 JSDOM 测试环境的协议安全检测（检查 `url.protocol === 'file:'` 后再调用 `fileURLToPath`，否则降级回 `path.resolve(process.cwd(), ...)`），杜绝测试环境中 `TypeError: The URL must be of scheme file` 报错。

### 45. 现代异步 API 认知误区与宏任务错误逃逸（Promise.try & Promise.withResolvers Invariants）

- **本质**：
  1. 误以为 `Promise.try` 能捕获所有异步错误：`Promise.try()` 仅统一捕获同步抛错（`throw`）与返回的 Promise 拒付（`reject`），脱离当前执行栈的宏任务（如 `setTimeout`、未封装的 DOM 事件监听回调）内部抛错依然会沦为未捕获异常并击穿主事件循环；
  2. 误以为 `Promise.withResolvers()` 解决后无需清理外部定时器：虽然 Promise 状态一旦 Settled（Resolved/Rejected）后具有不可变幂等性，但与其配合的后台竞争定时器（如 1.5s 兜底、网络超时）若不显式 `clearTimeout()`，仍会驻留在全局定时器堆中，在极端高频轮询或快速切页时导致无意义的回调唤醒与闭包内存滞留；
  3. 试图在构建层引入 Babel 实验性插件转译 Stage 1-2 草案语法（如模式匹配、管道运算符），破坏 Vite+ 纯净架构并引入不可逆的技术负债。
- **红线与防误伤**：
  - **不要**在宏任务内未包裹 Promise 的情况下依赖 `Promise.try` 做全局错误兜底；
  - **不要**在使用 `Promise.withResolvers()` 配合超时控制时省略 `clearTimeout`；
  - **不要**为了语法糖在生产引入非标准 TC39 Stage 1-2 转译工具链；
  - **放行/改用**：
    1. 门面回调与 Composable 注入函数使用 `promiseTry` 包裹，并在末尾绑定 `task.catch(() => {})` 隔离非业务层异常；
    2. 任何与 `Promise.withResolvers()` 配合的超时定时器，在业务 resolve 或 reject 时一并显式清除；
    3. 多源取消采用“可控定时器（`clearTimeout`）+ 原生 `AbortSignal.any`”，兼具立即销毁定时器与零事件胶水代码；
    4. 所有 Stage 1-2 草案仅在 `docs/JS_RADAR.md` 实验区归档观测，生产代码坚决恪守 Baseline 2024/2025 标准。

### 46. 现代 AbortSignal 认知误区与不可撤销定时器隐患（AbortSignal.timeout vs Managed AbortController）

- **本质**：
  1. 误以为 `AbortSignal.timeout(ms)` 可以完全无脑替代传统的 `setTimeout + clearTimeout`：根据 W3C DOM 与 MDN 规范，`AbortSignal.timeout()` **不提供任何取消机制（No early cancellation）**。即便请求在 5ms 内成功兑现，底层的系统超时定时器依然会在浏览器引擎中挂满设定的超时时间（如 15 秒），并在底层对信号对象和事件监听器保持强引用；
  2. 在短生命周期、高频并发的 RPC 场景（如搜索防抖请求、漫画翻页元数据拉取）中，盲目裸用 `AbortSignal.timeout()` 会导致事件循环中堆积大量未触发的悬空定时器，阻碍垃圾回收（GC），甚至在开发服务器热重载或快速切换页面时引发连接竞争；
  3. 误以为 `AbortSignal.any(signals)` 可以容纳非 Signal 对象：若传入了 `null`、`undefined` 或测试用例中的非标准 mock 对象，底层会直接抛出 `TypeError` 中断执行。
- **红线与防误伤**：
  - **不要**在频繁触发的短生命周期 RPC 中裸用 `AbortSignal.timeout()` 且放弃 `cleanup()` 清理；
  - **不要**给 `AbortSignal.any()` 传入未过滤的 falsy 值或非 `AbortSignal` 实例；
  - **放行/改用**：
    1. 超时控制采用受控的 `AbortController` + `setTimeout`，在请求 `finally` 阶段立即执行 `clearTimeout(timer)`，杜绝无意义定时器空转；
    2. 信号合成使用 Baseline 2024 原生 `AbortSignal.any([controller.signal, callerSignal])`，免去手写 `addEventListener('abort')` 与 `removeEventListener` 的样板胶水，彻底杜绝闭包泄漏；
    3. 异常提示保持一致：使用自定义 `new DOMException('请求超时，请重试', 'TimeoutError')` 提供一致的人性化报错提示。

### 47. 前端 CacheStorage 存储配额“逆向减法归因”与首部抽样偏差陷阱（CacheStorage Subtraction Attribution & Head Sampling Bias）

- **本质**：
  1. **首部顺序抽样严重低估（Sequential Head Sampling Bias）**：为了防止在成千上万张画页时因遍历 IPC 阻塞主线程，对 CacheStorage 请求使用固定头部采样（`SAMPLE_LIMIT = 40`，从 index 0 顺次读取）。由于用户浏览生命周期总是先加载缩略图（`thumbnail.jpg`，20~50 KB）与小封面，头部样本平均体积仅 ~60 KB，导致估算体积与真实物理占用产生 50+ MB 的严重低估；
  2. **逆向减法归因污染核心资产（Subtraction Anti-Pattern）**：在分项账单计算中，使用 `coreAssetBytes = usage - mangaImageBytes` 反求 App Shell。当浏览器真实物理占用为 87 MB，而画页被低估为 31 MB 时，剩余的 56 MB 画页物理占用被全额误标为“纸间核心资产”，使用户误以为 PWA 静态预缓存膨胀失控或图片泄漏进预缓存；
  3. **非标准 Runtime 缓存桶遗漏（Orphaned Cache Pools）**：动态插画池（如 `illustration-pool-cache`，含 4 MB WebP）缓存名称未匹配 `manga-images` 或 `images` 过滤关键字，在既未算入画页又被减法兜底的情况下，直接落入核心资产。
- **红线与防误伤**：
  - **不要**用 `totalUsage - sampledImages` 逆向推导不可变的轻量核心资产；
  - **不要**在存在多种尺寸分布的非同质缓存数组上使用头部前 N 项顺序抽样；
  - **不要**在图片缓存扫描中漏掉自定义命名的 Runtime 媒体桶；
  - **放行/改用**：
    1. **正向独立直接度量 Precache**：直接打开 `workbox-precache-*` 缓存桶（仅 ~40 项静态文件，毫秒级读取）测量真实的 App Shell 体积（固定在 ~1 MB 上下），与媒体图片实现物理级隔离；
    2. **物理存储扣减反转（Top-down Physical Attribution）**：优先从 `usageDetails.caches` 或 `usage` 中扣除已测出的极小核心资产，将真实物理磁盘占用全额如实归因于「漫画阅览缓存」；
    3. **全量媒体缓存统一生命周期管理**：在清理图片缓存与注销 IndexedDB 记录时，覆盖所有媒体桶（`manga-images`、`illustration-pool`），保持视图与物理存储彻底自洽。

### 48. 长列表与画卷收折中的“无限滚动失控”与“遮罩幽灵焦点”陷阱（Runaway Infinite Scroll & Ghost Focus Anti-Pattern）

- **本质**：
  1. **滥用基于 `useIntersectionObserver` 的贪婪无限滚动**：在藏书规模扩张或长篇连载（100+ 话）及单章节多画页（上百页）场景中，一旦用户快速滚动页面，哨兵在几百毫秒内连续触发多次批量追加，瞬间挂载几百个带封面图的 DOM 节点，触发大批并发图片解码网络请求与重排重绘，造成主线程掉帧卡死、滚动条失控拉长、滚动位置跳跃（Scroll Jitter），且无法收起回退；
  2. **遮罩层盖死末尾卡片的“幽灵焦点”（Ghost Focus）**：试图通过纯 CSS 在第 24 张画页上覆盖半透明 `+N` 遮罩来示意超出，导致底层原属于第 24 页的 `RouterLink` 仍存在于可聚焦树中。视障读屏软件与键盘 Tab 导航会误聚焦到被盖住的隐形链接，造成无障碍灾难与键盘导航逻辑混乱；
  3. **纯 CSS 计数器（CSS Counters）的“掩耳盗铃”缺陷**：虽然通过 CSS `:has()` 与 `counter-reset / counter-increment` 可以在纯样式层计算并展示超出数量，但浏览器必须预先将全量（数百上千个）DOM 节点渲染进文档树，无法解决真正的内存、图片网络并发与 DOM 渲染预算瓶颈。
- **红线与防误伤**：
  - **不要**在主详情页、章节目录或书架网格中无脑挂载长距离 `useIntersectionObserver` 自动追加哨兵；
  - **不要**将溢出提示遮罩层覆盖在已渲染的功能性卡片（链接/按钮）之上造成键盘与读屏幽灵焦点；
  - **不要**在面临上百张网络图片的列表上单纯依赖纯 CSS 隐藏（`display: none`）来做伪分页；
  - **放行/改用**：
    1. **虚拟切片预算管理（JS 控 DOM）**：Vue 层面实行受控的分批切片（书架 12 本 / 目录与画页 24 步长），严格将 DOM 节点数约束在预算内；
    2. **尾格独立承接**：溢出提示卡片（如 `.shelf-fold-card`、`.page-tile-overflow`）作为独立的网格卡片流式追加在列表末尾，不侵占已有卡片的交互层级；
    3. **双向受控与平滑滚顶**：不仅提供「再展开」与「展开全部」，必须随时提供「收起」出口，并借助 `scrollIntoView({ behavior: 'smooth', block: 'start' })` 平滑回滚至网格顶端，保证读者始终掌控滚动条长度。

### 49. View Transition 异步更新回调跳过引发的 Promise 永久悬空挂起陷阱（ViewTransition Update Callback Skip & Hanging Promise）

- **本质**：
  1. 根据 W3C View Transitions Level 1 规范与各浏览器内核实现，当文档处于后台非激活状态（如隐藏标签页）、处于离屏预渲染环境，或前一轮过渡未完成即被新过渡强行抢占（Preempted）时，引擎可能直接让 `updateCallbackDone` 与 `finished` 进入 Rejected（`AbortError`）状态，并**直接跳过调用传入的 `updateCallback`**；
  2. 若在 Composable 或路由钩子（如 `withViewTransition` 或 `router.beforeResolve`）中使用 `Promise.withResolvers()`，且仅依赖 `updateCallback` 内部的回调来触发 `resolve()`，一旦回调被浏览器跳过，外部 Promise 将永久保持在 Pending 状态，导致页面路由导航被永久卡死或调用端 await 无限挂起。
- **红线与防误伤**：
  - **不要**假设 `document.startViewTransition(cb)` 传入的 `cb` 在任何异常/抢占场景下都必然会被执行；
  - **不要**让对外暴露的控制流 Promise 单独死锁在 `updateCallback` 的执行分支上；
  - **放行/改用**：
    1. 声明 `let executed = false` 执行标记，在 `updateCallbackDone.catch` 与 `finished.catch` 阶段实施 `ensureExecuted` 拦截；
    2. 若捕获到过渡被内核抛弃且回调未被调度，立即由 catch 钩子执行同步/降级状态更新并触发 `resolve()`，确保业务调用链与路由生命周期百分之百平稳兑现。

### 50. 阅读器末页完结标记在同路由组件复用下的状态泄漏陷阱（Reader End-of-Book State Leak on Route Component Reuse）

- **本质**：
  1. Vue Router 在路径参数改变但目标组件相同时（如从 `/comic/jm/A/read/10` 跳转至 `/comic/jm/B/read/1`），默认采用组件实例原地复用策略，不会重新触发根组件及其子组件的 `setup()`；
  2. 在阅读器末页卡片（`ReaderEndCard.vue`）内部，为了防止读者视口反复微移触发多次网络写入，通常设有防抖布尔标记（`let hasTriggeredCompleted = false`）；
  3. 若父级容器（`ReaderViewport.vue`）挂载 `<ReaderEndCard>` 时未绑定与当前漫画关联的 `:key`，且漫画为单章节作品（`showEndCard` 始终为 `true`，无法通过 `v-if` 自然销毁），则切书后 `ReaderEndCard` 实例持续常驻，`hasTriggeredCompleted` 永久锁死在 `true`；
  4. 读者读完第二部作品并滑动至末页时，`IntersectionObserver` 虽然再次命中视口，但由于防抖标记已被前一本书污染，`emit('completed')` 绝不会再次触发，导致后续所有通过末页卡片连续阅读的作品均无法沉底归档或标记完结。
- **红线与防误伤**：
  - **不要**在依赖组件内局部闭包状态进行一次性生命周期判断的场景下忽略 `:key` 隔离；
  - **不要**假设同路由跨参数切页会自动清空内部 DOM 实例与 setup 变量；
  - **放行/改用**：
    1. 在阅读器滚动视口内为 `<ReaderEndCard>` 显式绑定 `:key="`${source}/${sourceId}`"`，强制 Vue 在切本时执行完整卸载与重新挂载生命周期；
    2. 配合父级顶层 `useReaderData` 针对 `[source, sourceId]` 变更的主动监听，确保跨本导航时阅读器全局状态、交互标记与末页感知彻底归零重置。

### 51. 阅览室沉浸式暗室背景与浅色全局控件的对比度碰撞陷阱（Reader Dark Room & Light Global Controls Contrast Collision）

- **本质**：
  1. 纸间默认主题采用典雅暖调纸质底色与墨色文字（如 `var(--ink-0)` 接近黑色 `#1b1917`）。而阅读器采用固定的沉浸式纯黑暗室背景（`--reader-bg: #0d0e0c`）；
  2. 当在阅读器末页卡片或暗室覆盖层中直接复用全局通用控件样式（如裸用 `.btn-ghost` 或浅色边框徽标）时，未作暗室隔离的样式会继续使用浅色墨色文本 `color: var(--ink-0)` 与透明底色；
  3. 这种“近黑文字叠加于纯黑背景”的对比度雪崩（对比度接近 1:1，严重击穿 WCAG AA 级 ≥ 4.5:1 无障碍底线）导致幽灵按钮如同隐形，读者无法看清「返回书架」等关键操作。
- **红线与防误伤**：
  - **不要**在固定暗室/暗调容器中直接裸用继承自浅色主题的前景文字或边框（如裸用 `.btn-ghost`、`color: var(--ink-0)`）；
  - **不要**在暗室组件中引入未在 Design Tokens 中声明的硬编码颜色（如裸写 `#333`、`#fff`）；
  - **放行/改用**：
    1. **暗室专有 Token 上下文隔离**：文字统一采用 `--reader-ink`（或 `--reader-text` 别名），底板采用 `--reader-surface-strong`，边框采用 `--reader-line-strong`，悬浮高亮切换为 `--reader-surface-hover` 并将文字升为纯白 `--paper-0`；
    2. **键盘焦点显式透传**：为暗室中的各类按钮与辅助图标按钮（如 `.rec-detail-btn`）显式声明 `:focus-visible` 焦点环（`outline: 2px solid var(--accent)`），杜绝在暗室中失去焦点指引；
    3. **遵循微标字阶底线**：徽章与次级状态文字使用 `--text-caption: 0.6875rem` 配合 `font-size-adjust: ch-width 0.48`，严禁在移动端使用 `< 11px` 的硬编码字号。

### 52. 多行文本截断在首屏批量挂载下的强制同步重排死锁（Forced Reflow & Layout Thrashing in Clamped Lists）

- **本质**：
  1. 在声明了 CSS `-webkit-line-clamp` 的文本元素上，浏览器引擎为了返回 `scrollHeight` 与 `clientHeight`，必须脱离异步合成管线，同步执行完整的多行字形折行与盒模型排版测量；
  2. 当在长列表或网格（如书架卡片 `ComicCard.vue`）中，组件在 `onMounted` / `nextTick` 或初始化 `useResizeObserver` 中批量读取该属性时，数十个实例在微任务队列中密集交错读写，引发极其严重的 **Forced Reflow / Layout Thrashing**；
  3. 主线程被排版计算长时间阻塞（单次重排耗时高达 20ms~50ms），导致首屏渲染直接掉帧（单帧长达 266ms），触发 DevTools 红色长任务警告。
- **红线与防误伤**：
  - **不要**在组件初始化生命周期（`onMounted` / `nextTick`）中无差别同步读取 DOM 几何排版属性以提前判断打点截断状态；
  - **不要**在无用户交互的卡片上挂载全局 `useResizeObserver` 去同步读取 `scrollHeight`；
  - **放行/改用**：
    1. **JIT 纯按需测量（Just-In-Time Detection）**：将几何排版测量严格推迟至读者意图触发时刻（光标悬停 `pointerenter`、触控按压 `touchstart`、键盘聚焦 `focusin`），单次测量耗时 < 0.05ms，首屏强制重排降至 0ms；
    2. **浮层延迟生效评估与触控适配（Deferred Disabled Evaluation & Touch Interaction）**：在 Tooltip 唤起延迟（`delay: 120ms~350ms`）计时器触发时二次核验 `props.disabled`，严禁将 `props.disabled && props.delay === 0` 耦合作为判定短路，确保在动态禁用与 `delay: 0` 时逻辑正交；同时支持移动端设备在 `touchstart` 时显式唤起气泡，弥补移动端缺失 hover 的交互盲区；
    3. **自动化重排防御门禁（`pnpm detect:perf`）**：借助静态 AST / 模式扫描拦截生命周期中的几何读取反模式。

### 53. 动态图片转码中的惊群效应与 HTTP 内容协商缓存污染陷阱（Thundering Herd & HTTP Content Negotiation Poisoning in Dynamic Image Transcoding）

- **本质**：
  1. **未受控的锁外快速转码引发并发惊群（Thundering Herd）**：在实现按需缩放或格式协商（如从 JPEG 生成 WebP）时，若在 API 路由层仅判断 `not target.exists()` 即在互斥锁之外直接启动图像库（如 Pillow）进行解码与压缩转码，当首屏数十张卡片并发加载或多个客户端同时涌入时，会导致数十个工作线程对同一张图片并发重复转码，触发 CPU 负载与磁盘 I/O 尖峰；
  2. **缺漏 `Vary: Accept` 导致的代理/CDN 共享缓存污染（Shared Cache Poisoning）**：在无扩展名 URL（如 `/covers/1/file`）上使用 `Accept: image/webp` 做透明内容协商时，若未在 HTTP 响应头附带 `Vary: Accept`，中间反向代理（如 Cloudflare、Nginx）或局域网共享缓存会将 WebP 二进制文件缓存为统一副本，导致不支持 WebP 的旧版客户端或爬虫随后拉取该 URL 时遭遇图片无法解码损坏；
  3. **扩展名未清洗导致的非预期文件拼接**：直接从 URL 动态路由参数 `{ext}` 取值并 `lstrip('.')` 作为文件后缀，若未在存储层做白名单截断归一，存在潜在的文件遍历或非法后缀探测风险；
  4. **资源缺失误抛 502 网关错误反模式（HTTP Status Semantic Inversion: 502 vs 404）**：在动态缩略图/封面转码端点中，若将底层源文件缺失（`FileNotFoundError`）或画卷尚未导入/页码越界（`KeyError`）一律捕获为通用异常并粗暴抛出 `502 Bad Gateway`，会导致反向代理与 CDN（如 Cloudflare）判定上游宕机触发错误屏接管、APM 监控报警与重试雪崩；此类由于客户端请求了不存在的实体引起的缺失必须精准映射为 `404 Not Found`，仅在真实的转码故障、内存崩溃等服务端异常时才抛出 500/502。
- **红线与防误伤**：
  - **不要**在端点层锁外直接执行耗 CPU 的图片格式转码与重采样；
  - **不要**在基于 HTTP 请求头进行内容协商的静态媒体响应中漏发 `Vary: Accept`；
  - **不要**允许未归一化的任意外部扩展名直接参与物理文件路径拼接；
  - **不要**将底层数据或实体未找到（`FileNotFoundError` / `KeyError`）粗暴映射为 `502 Bad Gateway`；
  - **放行/改用**：
    1. **Double-Checked Locking 互斥收敛**：端点层先做无锁热路径探测（若目标文件已存在直接零等待返回）；未命中时统一进入内部每页粒度互斥锁（`_lock_for_page`），在锁内执行二次存在性核验与快速转码，确保并发请求永远只有单线程执行转码，其余并发线程等锁后直接命中成品；
    2. **响应头标准隔离**：透明内容协商端点统一响应 `Vary: Accept` 与 `Cache-Control: public, max-age=31536000, immutable`；
    3. **扩展名白名单规整**：存储层显式执行 `clean_ext = "webp" if ext.lower().lstrip(".") == "webp" else "jpg"`，物理层彻底锁死合法后缀；
    4. **HTTP 状态码严格语义收敛**：在动态封面与转码端点中，显式捕获 `(FileNotFoundError, KeyError)` 并精准响应 `HTTPException(404, "Cover image not found")`，与转码过程中的服务端错误（500/502）严格边界隔离，避免 CDN 边缘误判。

### 54. 反向代理资产强缓存覆盖与 Cloudflare 边缘 Service Worker 换届死锁陷阱（Reverse Proxy Cache Assets & Edge SW Stale Deadlock）

- **本质**：
  1. 在 Nginx Proxy Manager (NPM) 或其他反向代理网关中，若在 Proxy Host 上勾选了 `Cache Assets`，网关会自动注入 `location ~* \.(jpg|jpeg|png|gif|ico|css|js)$ { expires 7d; }` 等规则；
  2. 此时，反代层粗暴覆盖了应用层（FastAPI `SPAStaticFiles`）针对 `/sw.js` 与 `/manifest.webmanifest` 精心下发的 `Cache-Control: no-cache, no-store, must-revalidate` 核心防死锁防线，向上一级 CDN（Cloudflare）下发了 `max-age=...` 的强缓存头；
  3. Cloudflare 边缘节点一旦缓存了带 TTL 的 `sw.js`，即使服务端容器已构建并发布了最新版本，公网客户端依然长期获取 20+ 小时前的旧版 `sw.js`；
  4. 旧版 `sw.js` 内嵌了已删除资源的预缓存清单（如 `/pwa-maskable-512x512.png`），导致浏览器并发拉取 404，且由于旧清单包含重复冗余资产（1.2 MB vs 336 KB），导致新旧版本换届死锁；同时若 Cloudflare 开启了 Bot 挑战且未豁免 Manifest，静默 fetch 还会触发 403 阻断。
- **红线与防误伤**：
  - **不要**在 NPM 或反向代理网关中无差别开启全局 `Cache Assets`；
  - **不要**依赖中间代理粗暴覆盖静态资源响应头，应将缓存语义的控制权归还给后端 SPA 静态中间件；
  - **放行/改用**：
    1. **NPM 保持取消勾选 `Cache Assets`**：让源站应用（FastAPI / `SPAStaticFiles`）全权掌控精确到文件级别的 Cache-Control（哈希 assets 强缓存 1 年，入口/SW/Manifest 强制 `no-cache`）；
    2. **Cloudflare 配置 PWA 绕过缓存规则（Bypass Cache）**：为 `/sw.js`、`/manifest.webmanifest` 等入口显式设置 Bypass Cache；
    3. **Cloudflare WAF 放行 PWA 关键入口**：配置精准限定域名（`http.host eq "comic.yourdomain.com"`）的 Custom Rule，对 `/manifest.webmanifest`、`/sw.js`、`/registerSW.js` 执行 Skip WAF/Bot 挑战，避免后台静默 fetch 被挑战页（403）阻断；

### 55. Cloudflare 免费版 Vary 忽略与边缘缓存越权穿透陷阱（Cloudflare Free Vary Ignored & Edge Cache Auth Bypass）

- **本质**：
  1. **Cloudflare 免费版忽略 `Vary: Accept` 导致格式死锁**：Cloudflare Free Anycast 边缘默认不支持基于 `Vary: Accept` 的多版本分片缓存。当后端在同一静态图片 URL 上做 WebP/JPEG 透明内容协商时，若历史或首次请求生成了 JPEG，Cloudflare Anycast 边缘会将其永久缓存在该 URL 下并向所有后续客户端下发，导致前端即使发了 `Accept: image/webp` 依然收到 JPEG；
  2. **边缘缓存越权穿透源站鉴权（Edge Cache Auth Bypass）**：当为私有媒体资源配置了 Cloudflare Cache Rule（如 Edge TTL 1 个月）后，一旦合法登录用户浏览过某本漫画，Anycast 边缘节点便建立了 200 缓存。此时外部未登录访客（如无痕模式）直接敲入该图片 URL 时，Cloudflare Anycast 边缘节点将直接命中缓存并返回 200 OK，**完全绕过了源站后端的 `auth_and_security_middleware` 与 Token 鉴权**，导致私有图片越权泄露。
- **红线与防误伤**：
  - **不要**依赖 `Vary: Accept` 期望公共 CDN 免费层实现透明图片格式协商；
  - **不要**在开启了边缘媒体缓存的 CDN 上仅依赖源站后端做鉴权校验；
  - **放行/改用**：
    1. **显式 WebP URL 收敛**：衍生缩略图与封面在前端 URL 层面显式使用 `.webp` 后缀（如 `/file.webp`、`/cover.webp`、`/thumbnail.webp`），正文页收敛为格式无关端点 `/file`，为 CDN 边缘提供唯一、确定的缓存键并打碎旧缓存；
    2. **Cloudflare WAF 边缘鉴权门禁（Auth Gate）**：在 CDN Anycast 边缘配置 Custom Rule，检测 `starts_with(http.request.uri.path, "/api/library/") and not (http.cookie contains "comic_shelf_token" or http.cookie contains "comic_shelf_device")`，无登录凭据的请求在 Anycast 边缘直接 `Block 403`，连边缘缓存都无法触碰；
    3. **正文原图 100% 格式保真**：正文漫画页不转码，保持解密源格式（JM 为 WebP，哔咔等源为 JPEG），仅衍生缩略图收敛为 WebP。

### 56. Cloudflare Under Attack 常态化质询与 WAF 鉴权门禁逻辑反转陷阱（Cloudflare IUAM Challenge & WAF Auth Gate Inversion）

- **本质**：
  1. **Under Attack 模式常态开启导致非交互式探测遭遇 403 挑战**：在 Cloudflare 仪表盘常态开启「Under Attack 模式（五秒盾）」后，Cloudflare 会对全站所有请求强制施加 JS/Turnstile 人机质询。虽然首次在浏览器地址栏打开网页时能顺利通过并获取临时 `cf_clearance` 凭证，但该凭证具有生存期（TTL）。一旦到期，浏览器在后台执行的 Service Worker 更新探测（`/sw.js`）、页面异步数据拉取（`/api/books`）以及画页二进制拉取（`/api/library/.../file`）属于**无 UI 界面的后台非交互式 fetch**，无法渲染并执行 Cloudflare 的 JS 人机验证挑战，Cloudflare Anycast 边缘直接返回包含质询页的 **HTTP 403 Forbidden**，导致应用静默瘫痪；
  2. **离线重置带来的“假性自愈”误导**：前端通过「重置全部离线环境」注销 SW、清空缓存并触发 `window.location.reload()` 顶层文档导航，重新为浏览器提供了完整的交互渲染视口，偷偷刷新了 `cf_clearance`，造成“离线存储损坏或缓存故障”的假象，但一旦凭证过期又会周期性重现；
  3. **WAF 自定义规则运算符反转误杀合法用户**：在配置 Cloudflare WAF 边缘鉴权规则（`paper-room-media-auth-gate`）时，若在图形化界面中误选了 `Cookie contains` 搭配 `Block`，规则将退化为“只要 Cookie 包含 `comic_shelf_token` 就予以 403 阻断”，导致已登录的合法读者反而被自身 Cookie 精准误杀。
- **红线与防误伤**：
  - **不要**在未配置凭据放行规则前无差别开启「Under Attack 模式」；
  - **不要**在配置 WAF 边缘门禁时依赖易反转的图形生成器，必须核对 raw expression 的逻辑非（`not`）；
  - **放行/改用**：
    1. **已登录读者绿色豁免通道（兼顾 Under Attack 与 0 误杀）**：若需开启 Under Attack 极高防探测模式，必须在 WAF 第 2 顺序部署 `paper-room-auth-bypass-attack` 规则，检测 `http.host eq "comic.yourdomain.com" and (http.cookie contains "comic_shelf_token" or http.cookie contains "comic_shelf_device")` 并在操作中选择 **`Skip` ➔ 勾选跳过「安全级别（Security Level）」**，使已认证读者彻底豁免五秒盾质询；
    2. **安全级别回归 `Medium`（备选基准方案）**：若不配置凭据 Skip 规则，Cloudflare 全局安全级别必须保持为 `Medium`（中）或 `High`，绝不常态开启「Under Attack 模式」；
    3. **精准表达式配置媒体 WAF 门禁**：必须点击 `Edit expression`，配置 `http.host eq "comic.yourdomain.com" and starts_with(http.request.uri.path, "/api/library/") and not (http.cookie contains "comic_shelf_token" or http.cookie contains "comic_shelf_device")`，只有**未持有凭证**的外部直接请求才在 Anycast 边缘被 403 阻断；
    4. **PWA / SW 专属绿色通道**：确保第 1 条规则 `paper-room-pwa-waf-skip` 严格置顶并勾选 Skip 安全级别与所有质询；
    5. **延长质询通过期**：在安全性设置中将「质询通过期限 (Challenge Passage)」提升为 `1 month`，消除短期过期闪断。

### 57. Nginx 反代网关源站 IP 白名单与 Real-IP 变量覆盖误杀陷阱（Nginx Real-IP Overwrite & Origin Access Control Trap）

- **本质**：
  1. **Nginx `$remote_addr` 被 `real_ip_header` 冲刷引发全员 403 误杀**：为了防御恶意扫描器探测家庭公网 IP 高位端口并绕过 Cloudflare WAF，许多架构师习惯在 Nginx / NPM 中配置 `allow <Cloudflare_IP>; deny all;`。但若 Nginx 已经或未来配置了 `real_ip_header CF-Connecting-IP;`，Nginx 的核心变量 `$remote_addr` 会被模块静默重写为**终端真实客户端的公网 IP**（如手机蜂窝网络 IP）。此时 Nginx 的 `allow` 指令拿着客户端的真实 IP 去比对 Cloudflare 节点网段，判定不匹配后**将 100% 的合法正常读者全量阻断为 403 Forbidden**；
  2. **动态 CDN IP 段维护成本与失效风险**：Cloudflare 虽有公布的 Anycast 节点网段，但在全球范围内会不定期扩容或临时启用新 IP。在反代层硬编码数十个 CIDR 不仅繁琐，一旦命中未及时收录的新节点就会导致突发性回源中断。
- **红线与防误伤**：
  - **不要**在配置了 Real-IP 穿透的网关层使用基于 `$remote_addr` 的 `allow/deny` 指令限制 CDN 回源；
  - **放行/改用**：
    1. **专属通信暗号（Transform Rules + Custom Header 校验）**：在 Cloudflare Dashboard 配置一条 `Transform Rules ➔ Modify Request Header`，为所有合法回源流量注入专属私有请求头（如 `X-Origin-Secret: <32位强随机密钥>`）；
    2. **NPM Advanced 选项卡免维护准入**：在 NPM Proxy Host 的 Advanced 文本框中写入校验逻辑，优先放行局域网网段（`192.168.0.0/16` 等，确保内外网分流千兆直连免检），仅对公网流量核验 `$http_x_origin_secret`。任何公网 IP 嗅探直连由于缺失该私有标头，在网关层 100% 击落返回 403，兼得极致安全性与永久免维护。

---

## 🚦 交付门禁（四步必跑）

1. **静态检查**：`vp check`（前端 0 error、0 warning、格式规范）；
2. **Vue 模板类型检查**：`pnpm type-check`（基于 `vue-tsc --build` 增量模式，排查 Vue template 内部 TS 属性绑定与类型错误，只验证改动文件加速）；
3. **后端测试**：`pnpm test:py`（后端 0 syntax/import error，中间件全链路测试通过）；
4. **定向单测**：仅运行改动对应的单测文件（严禁无差别全量阻塞）。
