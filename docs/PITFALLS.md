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

### 14. PWA 鉴权端点与离线缓存隔离（API Metadata Cache Ban & IndexedDB User Isolation）

- **本质**：将状态敏感型 API 纳入 Service Worker 离线缓存策略，导致客户端身份被陈旧响应持久劫持或多租户数据穿透；或 iOS PWA 缺失标准 180px PNG 根文件导致添加到主屏幕图标变截图。
- **复现场景**：Workbox 将 `/api/*`（如 `/api/library`、`/api/settings`）纳入 `NetworkFirst`，反向代理或弱网下命中未授权缓存导致馆长权限丢失且必须全量重置，或访客意外读取到馆长私密藏书；iOS Safari 找不到 180x180 图标回退抓取网页截图。
- **红线与防误伤**：**不要**在 Service Worker（Workbox）中缓存任何 `/api/` 数据端点（严禁配置 `api-metadata-cache`），**不要**在 `index.html` 仅书写 192px 尺寸图标；**放行/改用**Service Worker 仅缓存静态 App Shell 与二进制漫画画页（`manga-images-cache`），动态 API 的离线可用性必须收敛于受控的 Pinia + IndexedDB（`comic-shelf-meta`，按 `userId` 分区与签名隔离，`offline_actions` 仅在用户匹配时回写）；`public/` 与 `index.html` 必须提供标准 180×180 `apple-touch-icon.png` 与通配链接。

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

- **本质**：将具有明确树状包含关系的“向上返回父级视图”（如章节子视图返回漫画详情页）与浏览器的“时序后退（History Back）”混淆。早期曾简单建议子详情返回父详情使用 `router.push`，但这会导致历史栈追加新的父详情条目，其 `history.state.back` 恰好是子详情；当父详情页遵循条目 65 调用 `router.back()` 时，便会重新弹回子详情，形成致命的回弹死循环。
- **复现场景**：
  1. 从漫画详情页进入第 3 话子详情，点击左上角“返回本子详情”，若使用 `router.push`，历史栈累加新的父详情条目；
  2. 随后在父详情页点击“返回书库”，`router.back()` 回退至上一条目（第 3 话子详情），出现“从子页回父页，父页点返回又回子页”的死循环。
- **红线与防误伤**：
  - **不要**在明确语义为“向上返回父级”的按钮上盲目无脑 `router.push` 父级路径累加历史；
  - **不要**在子模块退出（如阅读器退出）时使用 `router.push` 累加游走历史；
  - **不要**在父详情页（Rank 2）点击返回时向更深层级的子路由（Rank 3 章节 / Rank 4 阅读器）倒退；
  - **放行/改用**（统一人格 `useHierarchicalNavigation`）：
    1. **子详情返回父详情（来源感知出栈 + 替换兜底）**：检查 `history.state.back` 是否精确匹配父详情页（`isParentAlbumRoute`）。若是，直接 `router.back()` 优雅出栈（无损还原父详情页离开时的滚动位置与章节展开折叠状态）；否则（如冷启动直达单话、外链接入）使用 `router.replace('/comic/:source/:id')` 替换兜底；
    2. **同级切话视口替换**：章节子路由内部切话（`switchChapter`）采用 `router.replace`，同层视口切换不入栈，消除历史栈爆炸，确保点击「返回本子详情」单次即可出栈回到父详情；
    3. **父级视图下级路由防卫（Downward Navigation Guard & Meta Rank）**：父详情页 `goBack()` 增加纵深防御拦截，优先依据路由元数据 `meta.rank` 进行声明式推导（拦截 `targetRank > 2`），并严格排除指向当前漫画自身的重复历史条目（避免阅读器 `replace` 退出后需双击返回的假死缺陷）与 `/create` 表单，拦截 `router.back()` 并以 `router.replace({ name: 'library' })` 兜底直达书架，彻底阻断向下回弹死循环与历史卡顿；
    4. **深层沉浸界面退出**：阅读器、全屏浮层退出统一使用 `router.replace` 就地替换历史栈。

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

### 58. 微件胶囊散落手写与无障碍按压态断层（Universal Chip & Polymorphic ARIA Trap）

- **本质**：在业务组件中各自手动拼接 `<button class="chip chip-button">` 或 `<span class="tag-chip">`，不仅引发内边距、圆角与字阶漂移，而且极易漏标 `:aria-pressed`、`type="button"` 与事件冒泡拦截（如点击删除标签误穿透触发表单提交或外层路由卡片跳转）。
- **复现场景**：在筛选栏手写带图标切换按钮未挂载 `aria-pressed`，读屏器无法感知开关状态；在标签管理弹窗内手写删除按钮未调用 `event.stopPropagation()` 触发卡片选中。
- **红线与防误伤**：
  - **不要**在业务组件内散落手写原生 `<button class="chip chip-button">`、`.tag-chip` 或带删除按钮的胶囊；
  - **放行/改用**：统一使用 `AppChip`。纯展示场景自适应输出语义化 `<span>`；筛选与动作场景自动升格为带有焦点环与 `:aria-pressed` 的 `<button type="button">`；可删除场景通过 `removable` 启用内置关闭微按钮并自动在底层阻断冒泡。

### 59. 代理穿透与出站下载下的 SSRF 预解析与 GFW 超时死锁陷阱（Proxy-Aware SSRF & GFW DNS Deadlock）

- **本质**：在防范出站下载 SSRF 攻击时，直觉做法是在 Python 层调用 `socket.getaddrinfo(host)` 将域名解析为 IP 并核验是否属于私有网段。然而在大陆网络环境下，境外 CDN 域名（如哔咔的分流节点）常被 DNS 污染或阻断，此时若配置了上游代理（`PICA_PROXY`），真正的 DNS 解析本应交由代理端远端执行；如果在本地宿主机执行同步 `getaddrinfo`，会导致每个页面下载阻塞长达 80+ 秒触发系统级 DNS 超时，使并发下载工作池彻底瘫痪死锁。
- **红线与防误伤**：
  - **不要**在依赖上游网络代理的场景下对外部 CDN 域名执行本地同步 `socket.getaddrinfo()` 预探测；
  - **放行/改用**：采用**语法级 IP 过滤 + 官方 CDN 域名白名单/后缀校验 + 重绑定黑名单**三位一体防护。字面量 IP 严格校验私有/回环并阻断直接 IP 访问；域名级拦截 `localhost`、`*.nip.io`、`*.sslip.io` 及 `.local` / `.internal` 等内网后缀；合法下载收敛于官方已验证的 CDN 根域（如 `.bwaa.co`、`.wikawika.xyz`、`.picacomic.com`）或用户通过 `PICA_EXTRA_CDN_HOSTS` 显式声明的内网镜像。

### 60. 上游拦截响应伪装合法图片与文件魔数防御陷阱（Upstream WAF Disguise & Magic Bytes Trap）

- **本质**：依赖 HTTP 状态码与响应体长度（如 `status == 200 and len(content) >= 100`）判断画页是否成功下载极度脆弱。上游 CDN 或反代（如 Cloudflare / 边缘 WAF）在触发人机验证或返回自定义 403 页面时，有时仍会给出 HTTP 200，但载荷是数百字节的 HTML（`<!DOCTYPE html>`）或 JSON 报文。若将其直接命名为 `.jpg` 写入磁盘，不仅在阅读器中产生破图，还会导致以图搜图 Sidecar 或 Pillow 在提取 ORB 特征时因未知格式抛出 `UnidentifiedImageError`，引发批处理崩溃。
- **红线与防误伤**：
  - **不要**仅凭 `len >= 100` 假定字节流为合法图像并直接落盘；
  - **放行/改用**：在写入磁盘或标记完成前，严格检查二进制数据前导魔数（Magic Bytes）：JPEG (`\xff\xd8\xff`)、PNG (`\x89PNG\r\n\x1a\n`)、WebP (`RIFF....WEBP`)、GIF (`GIF87a`/`GIF89a`) 及 AVIF (`....ftypavif`)。非图像数据立即触发多 CDN 候选节点故障转移降级，若全部分流均无效则抛出明确错误并安全回滚。

### 61. 短篇画卷封面越界与动态收敛陷阱（Dynamic Cover Count Convergence Trap）

- **本质**：系统全局配置 `COVER_COUNT=4`（默认抓取前 4 页作为画卷封面与悬浮缩略图）。若收录的漫画为单话短篇或插画集且总页数小于 4（如仅 1~2 页），元数据若盲目写入 `cover_count=COVER_COUNT`，前端和封面生成器在请求第 3、4 张封面时将索引超出实际画页列表范围，造成控制台持续爆出 404/500 噪音与破图。
- **红线与防误伤**：
  - **不要**在 Provider 的 `fetch()` 中为 `ComicMeta.cover_count` 赋予未经边界约束的全局常量；
  - **放行/改用**：统一执行动态收敛 `cover_count = min(COVER_COUNT, total_page_count) if total_page_count else COVER_COUNT`，确保封面请求永远不会超越实际收录页数边界。

### 62. 哔咔移动端 REST 接口 Query 参数签名遗漏与假成功静默截断陷阱（PicAcg HMAC Query Stripping & Silent Truncation Trap）

- **本质**：哔咔官方移动端 REST API 的 HMAC-SHA256 签名机制强制要求签名的相对 URI 路径中**必须完整保留 Query 字符串**（如 `comics/{id}/eps?page=1` 与 `comics/{id}/order/{order}/pages?page=1`）。若在计算签名时误将 Query 剥离（如 `.split("?")[0]`）或把 `params` 独立传给 requests，服务端在签名不匹配时**不会**返回 401 或 403 报错，而是静默返回无 `data` 字段的假成功响应（`{"code": 200, "message": "success"}`）。这导致分卷列表与画页列表在第一页就被错误判定为空并跳出循环，最终造成全书 `page_count: 0`、`chapters: []` 坏档且无法预缓存封面。
- **参考源单一事实源红线**：全仓确立 `wgh136/PicaComic`（[https://github.com/wgh136/PicaComic](https://github.com/wgh136/PicaComic)）为哔咔逆向协议与端点的**唯一事实源**。后续遇到任何端点变动或分页疑难，一律对照该项目实现，严禁在外部泛化搜索引擎搜索不相关或低质的“piacg”关键词。
- **红线与防误伤**：
  - **不要**在计算哔咔 HMAC 签名时剥离或丢弃 URL 中的 Query 字符串；
  - **不要**在 `album.json` 已有但 `page_count == 0` 时放行缓存命中；
  - **放行/改用**：
    1. **签名与请求路径完全同源**：在 `_request` 中先将 `params` 通过 `urlencode` 完整拼接到 `clean_endpoint`（如 `comics/{id}/eps?page=1`），再将同一字符串透传给 `calc_signature` 计算 Header 签名并作为请求 URL；
    2. **历史坏档读写自愈**：在 `/api/library/import` 处校验 `cached.meta.page_count > 0`，当检测到 `page_count == 0` 坏档时自动穿透缓存触发回源全量重拉；

### 63. 章节子路由缓存脱节与缩略图静默落盘感知失效（Chapter Subroute Cache Disconnect & Thumbnail-Implied Page Caching Trap）

- **本质**：在详情页与章节子路由中，`PageTile` 请求 `/thumbnail` 缩略图时，后端会按需抓取原图、解密并落盘，并在服务端 `album.json` 中将画页标记为 `cached = true`；但前端画页网格由于缺乏对这一“隐含落盘（Implied Caching）”动作的感知，加之客户端 `api.detail` 启用了 `useMemoize` 内存缓存，在子路由内即使调用 `load(true)` 也依然返回陈旧内存快照；此外，`ChapterView` 误用全书粒度的 `api.cacheProgress` 轮询而非单话粒度的 `api.chapterCacheProgress`，导致单话缓存进度与全书混合，造成“画页缩略图已渲染但徽标始终卡在‘待缓存’、且单话缓存结束后状态不自动收敛”的割裂。
- **红线与防误伤**：
  - **不要**在章节子路由中调用全书粒度的缓存进度轮询（`api.cacheProgress`）；
  - **不要**在后台任务完成或主动对账时直接调用未穿透内存缓存的 `api.detail`；
  - **不要**让画页网格被动等待下一次全量刷新才更新已下载状态；
  - **放行/改用**：
    1. **缩略图加载感知向上冒泡**：`PageTile.vue` 在 `@load="onThumbLoad"` 处检测，若当前页未标记为 `cached`，立即派发 `cached(index)`；`PageIndexGrid` 向上转发 `@page-cached`，父级（`ChapterView` / `ComicDetailView`）乐观更新内存中 `page.cached = true` 与 `cached_pages` 计数；
    2. **精准单话轮询与缓存穿透**：单话缓存精准轮询 `api.chapterCacheProgress`；在任务完成或显式重拉时调用 `load(true, true)`，通过 `bypassCache: true` 主动逐出 `memoizedDetail`；在 `api.cacheChapter` 触发时自动清理对应的 `memoizedDetail`；

### 64. 3D 变换下卡片视口投影尺寸缩放与 Scroll-Snap 吸附回弹陷阱 (3D Transform Bounding Box & Scroll-Snap Spring-back Trap)

- **本质**：在包含 3D 动画透视变换（如 `view-timeline` 驱动的 `scale(0.72) rotateY(-38deg) translateZ(-5rem)`）的封面轮播图中，若在步进计算中使用 `getBoundingClientRect().width` 读取首张卡片的渲染盒模型，读取到的仅是透视压缩后的视口投影宽度（约 136px，而非原本 256px 物理排版宽）；这导致计算出的步进偏移（`step = width + gap ≈ 152px`）远小于实际相邻卡片的中心物理间距；由于位移未能跨过 CSS `scroll-snap-type: x mandatory` 的中位吸附临界点，浏览器会将视口强行吸附回弹至原卡片，导致连续点击时出现“多点一次才切换”的假死假象。
- **红线与防误伤**：
  - **不要**在带有 CSS 3D 变换（transform/scale/rotate）的轮播项上使用 `getBoundingClientRect()` 计算滚动步长；
  - **放行/改用**：基于不受 3D 变换矩阵影响的 DOM 排版坐标（`slide.offsetLeft + slide.offsetWidth / 2`）动态计算物理中心卡片，并调用标准原生 `slide.scrollIntoView({ inline: 'center', behavior: 'smooth' })` 实行绝对几何对齐；同时支持卡片直接点击居中与键盘回车交互。

### 65. 详情页返回参数丢弃与折叠批次基线污染陷阱 (Router Query Stripping & Pagination Baseline Pollution Trap)

- **本质**：
  1. 详情页顶栏手写返回按钮若硬编码为 `router.replace({ name: 'library' })`，会导致路由查询参数（如来源分馆 `?source=jm` 或搜索关键词）被全量抹除，同时破坏浏览器历史栈，使 Vue Router 的 `scrollBehavior` 无法从 `popstate` 读取 `savedPosition`；
  2. 在实现跨路由列表展开状态恢复时，若将恢复的临时条数（如 24）直接赋给 `usePaginationFold` 的 `initialStep`，会导致 Composable 将 24 误认为是基础收整基线（Base Step），使得“收整”按钮失效或收整时无法回到初始的 12 条。
- **红线与防误伤**：
  - **不要**在详情页等子页面返回按钮中硬写无参 `router.replace({ name: 'library' })`；
  - **不要**将列表恢复数量与折叠收起基线混为一谈；
  - **放行/改用**：
    1. 返回按钮优先检测 `window.history.state?.back ? router.back() : router.replace({ name: 'library' })`，无损还原来源路由和筛选参数；
    2. `usePaginationFold` 引入 `initialVisibleCount`（仅控制挂载初态切片），与 `initialStep` / `step`（控制折叠收起基线）彻底解耦，兼顾高度占位防止滚动跳跃与随时收回初始首屏。

### 66. 常驻 SSE 长连接挂起与挂机任务被 `useIdle` 误切断陷阱 (Persistent SSE Idle Hanging & Premature Idle Teardown Trap)

- **本质**：
  1. 全站 24 小时无差别常驻挂起 `/api/events/stream` 长连接，导致网络面板持续显示 pending 请求，引发后端连接占用与长连接悬挂的心理负担；
  2. 在引入 `useIdle(10min)` 试图缓解常驻长连接消耗时，未将连接生命周期与异步任务深度解耦。当用户在后台发起耗时较长的批量离线缓存或大图集导入（>10 分钟）时，因缺乏鼠标键盘操作触发 `idle = true`，导致 SSE 长连接被意外掐断，丢失关键进度与完成事件；
  3. 服务端在 `lifespan` 启动阶段执行 `broadcast_event("system_version", ...)`，由于此时没有任何客户端建立连接，该广播为空跑无用功。
- **红线与防误伤**：
  - **不要**在前端启动时默认常开 `/api/events/stream` 长连接；
  - **不要**在承载后台长耗时任务的长连接状态机中使用盲目超时的 `useIdle`；
  - **不要**在没有任何握手客户端的后端启动生命周期广播业务事件；
  - **放行/改用**：
    1. **任务驱动型按需生命周期**：仅在发起导入、预缓存或检测到后台活跃任务时（`beginTask` / `endTask`）自适应拉起长连接；全部任务归零后经 5 秒平滑防抖冷却自动熔断注销，日常浏览网络面板保持 0 pending 请求；
    2. **淘汰 `useIdle`**：长连接生命周期严格由活跃任务集合、阅读器避让与视口前台状态裁决，彻底杜绝挂机批量下载被误判闲置切断；

### 67. 标签托盘高度重排冲击波与卡片常驻合成图层踩踏陷阱（Tag Tray Reflow Blast Radius & Resident VT Layer Trap）

- **本质（Trace-20260910 真实故障复盘）**：
  1. 在流式布局中，展开抽屉使用 `grid-template-rows: 0fr ⇄ 1fr` 动效导致主线程在 260ms 内每一帧执行几何重排（Forced Reflow）；
  2. 位于流式抽屉正下方的书架网格含有数十张漫画卡片（总文档高度达 4850px+），卡片内包含 3D 旋转叠牌封面、滤镜、圆角与阴影；
  3. **协同杀手叠加**：吸顶栏 `.site-header` 带有 `position: sticky; top: 0; backdrop-filter: blur(14px)`，且全局铺满了带有 `mix-blend-mode: multiply; filter: contrast/grayscale; mask-image: radial-gradient` 的固定背景 `<AmbientWatermark>`。当用户在已滚动（y ≈ 300px）的状态下点击展开标签抽屉时，下游移动的整屏卡片穿过吸顶栏，Blink 引擎在每一帧（在 144Hz 屏幕下单帧仅 6.94ms 预算）被迫执行 33 次 `UpdateLayer` 并重算双通高斯模糊与全屏正片叠底，`CrGpuMain` 单帧耗时直接飙升到 60ms ~ 160ms，导致瞬间丢弃 11~~23 帧，帧率暴跌至 6~~12 FPS 严重停顿假死。
- **红线与防误伤**：
  - **不要**在推挤海量复杂卡片的主干文档流中使用任何 CSS 高度过渡动画（无论是 `grid-template-rows` 还是 `interpolate-size: allow-keywords`，改变几何尺寸必然引起下游卡片在视口内连续移动，无法根除重排与 GPU 合成雪崩）；
  - **不要**为网格所有普通卡片常驻声明静态 `view-transition-name`；
  - **不要**让吸顶毛玻璃与全屏复合滤镜水印裸露在非隔离图层树中；
  - **放行/改用**：
    1. **交互范式升维**：次级筛选标签收纳全面收敛为基于 HTML Popover API + CSS Anchor Positioning 的**顶层气泡浮层（Overflow Tag Popover）**（`AppPopover`），页面高度 0 变动，下游卡片 0 位移，几何重排为 0，GPU 模糊重算为 0，144 FPS 满帧丝滑；
    2. 吸顶栏 `.site-header` 增加 `contain: layout style; isolation: isolate;` 图层隔离；
    3. 全屏水印 `.ambient-watermark.is-page` 增加 `contain: strict; transform: translateZ(0); will-change: opacity;`，隔绝合成器频繁无效重绘；
    4. 印章与徽标改用高不透明度半透明纯色背景（如 `color-mix(in oklab, var(--ink-0) 88%, transparent)`）加微投影，兼顾锐利质感与零 GPU 模糊着色器消耗；
    5. 局部微交互统一交由原生 CSS `transition` 或 Vue `<Transition>` 驱动，View Transition 严格收敛于跨页面大路由推进。

### 68. 条漫切片腰斩与阅读器行内装订页脚冲突（Inlined Page Footer vs Webtoon Slices）

- **本质**：
  1. 条漫（韩漫/国漫/Webtoon）在分发时被切成多张连续图片（如 3200px + 1912px）。若沿用普通分页漫画的设计，在每张图下方插入占位行内页脚（`<footer class="page-footer"><span>021</span></footer>`）并施加垂直外边距（`padding-top: var(--reader-gap)`）与单页阴影（`box-shadow`），会硬生生将对白气泡与人物画面腰斩切断；
  2. 切片高度往往不规则，若允许「适应高度（fit: height）」缩放，会导致相邻两页被缩放为不同横向宽度，产生横向左右错位撕裂；
  3. 在高 DPR 视网膜屏或浏览器缩放（125%/150%）下，两个紧邻的 `<img>` 会因浮点像素舍入在接缝处漏出 0.5px 的底色微缝。
- **红线与防误伤**：
  - **不要**在垂直连续的切片条漫中插入占文档流高度的行内页码、页面投影或外边距；
  - **不要**在无缝条漫模式下允许「适应高度」或多列分屏（`pagesPerView > 1`）；
  - **放行/改用**：
    1. 单页传统日漫保留标准间距与行内页脚；
    2. 无缝长卷模式下彻底拔除行内页脚，改用视口右下角悬浮胶囊（`ReaderFloatingPill`，滚动时感应淡入、静止 1.5s 淡出、呼出 HUD 时主动隐退，使用高不透明度半透明纯色避免滚动期间 GPU 模糊着色器雪崩）；
    3. 状态机硬约束锁定单列全宽（`pagesPerView = 1`，`fit = 'width'`），并在设置面板中以微标提示禁用；
    4. 对非首图施加 `margin-top: -1px` 亚像素微咬合，并重置图片底色与投影为透明，100% 杜绝缩放漏缝。

### 69. 单本作品偏好反向污染全局基线与无界字典膨胀陷阱（Per-Comic Preference Bleed & LocalStorage Bloat Trap）

- **本质**：
  1. 在引入单本独立阅读偏好（Overrides）时，若深度监听器无条件向全局默认配置（`comic-shelf:reader-settings:v1`）写回，会导致单本条漫自适应开启的 `seamless: true, fit: 'width'` 反向污染全局存储基线，使后续打开的所有普通日漫都被强制变异为条漫模式；
  2. 退出或切换至未自定义的作品时，若未以全局偏好重置共享响应式单例，会导致上一本漫画的排版状态（如 RTL 或横向翻页）跨漫画逃逸残留；
  3. `OVERRIDES_KEY` 在多作品打开后无上限累加，带来本地存储容量超限隐患；
  4. 使用 VueUse 时若脱离 `vueuse-functions` skill，容易盲目在终端用 Node 探测内部选项，忽略其事件派发与 flush 时序机制。
- **红线与防误伤**：
  - **不要**在存在活跃漫画上下文时修改全局默认存储；
  - **不要**在切换作品时遗留上一本作品的自定义排版脏状态；
  - **不要**在本地存储中无限追加作品偏好字典；
  - **不要**脱离 `vueuse-functions` skill 盲目用 Node 脚本探测 VueUse 函数与 API；
  - **放行/改用**：
    1. 严格区分全局持久化与单本偏好字典：`if (activeComicKey.value) { /* 仅写 overrides */ } else { /* 写 stored */ }`；
    2. 切换或退出作品时，以全局存储为真理源重置单例状态；
    3. 引入 `MAX_OVERRIDES = 100` 实施 FIFO / LRU 驱逐策略；
    4. 凡使用 VueUse 必须读取 `vueuse-functions` skill 获取权威选项与最佳实践；
    5. **警惕局部覆盖死锁**：不能在仅有阅读器入口时单向降级为局部覆盖，必须通过双轨制同时开放全局基线修改与自愈（详见 **坑 73**）。

### 70. 万级分页偏移跳跃、以图搜图历史断层与全量展开虚假触底陷阱 (Paginated Library Offset-Mismatch, Visual Search Amnesia & Pseudo-Unfold Trap)

- **本质**：
  1. **分页偏移断层**：在流式无限滚动或批量追加时，若服务端仅依靠 `(page - 1) * page_size` 计算 SQL 偏移量，当客户端因展开全部调整单次拉取批次（如从 24 调整为 120），SQL `OFFSET` 会因基数突变产生大幅跳跃，导致中间藏书被无故跳过；
  2. **识图检索历史断层**：在服务端分页后，前端内存仅持有首屏切片（如前 24 本）。若读者使用以图搜图，Milvus / OpenCV 向量特征库命中了数月前收录的深层历史藏书（如第 500 本），前端由于内存无该条目，过滤计算后直接显示“暂无匹配藏书”，造成识图可用却不可见的严重断层；
  3. **全量展开虚假触底与双卡冲突**：`usePaginationFold` 若将 `remainingCount` 按 `totalLength - visibleCount` 计算，并在用户点击「展开全部」时直接将 `visibleCount` 拔高至服务端 `totalCount`（如 500），会导致前端在仅下载了 48 本时 `remainingCount` 便提前归零，底部的「全架藏书已展开」完成条与尾格折叠卡（因 `hasMore === true`）同时发生矛盾并发渲染；
  4. **全库全量无节制展开导致显存崩溃**：若在万级藏书规模下真正把上万张卡片（4万张封面图片）挂载进单页 DOM，会导致移动端标签页直接 OOM 崩溃闪退。
- **红线与防误伤**：
  - **不要**在流式追加或批次变化场景仅依赖 `page * page_size` 计算分页偏移；
  - **不要**让客户端内存过滤接管服务端分页下的向量识图匹配；
  - **不要**基于未就绪的推测数量（`visibleCount`）断言剩余未呈现项（`remainingCount`），必须基于实际已挂载的 DOM 列表长度（`visibleItems.length`）与 `!hasMore` 守卫进行判定；
  - **不要**允许展开全部操作无上限追加，必须设置设备显存安全上限（如 240 本）；
  - **放行/改用**：
    1. 服务端接口支持显式 `offset` 参数，与 `page` 解耦，确保平滑流式追加与批次自适应伸缩；
    2. `/api/library` 支持 `ids`（`source:source_id` 列表）定向检索，以图搜图结果直通 SQLite 影子索引精准拉取全貌；
    3. `remainingCount = computed(() => Math.max(0, totalLength.value - visibleItems.value.length))`，且底部展开完成条强制附加 `!hasMore` 守卫；
    4. 60 本触发安全刹车暂停无感滚动，`store.loadAll(maxCap = 240)` 实施安全封顶并防范 OOM。

### 71. TransitionGroup 无 Key 侦测桩、同路由 Query 强制滚顶与流式分页失步假死陷阱 (Unkeyed Sentinel in TransitionGroup, Same-Path Scroll Reset & Frozen Stream Append Trap)

- **本质**：
  1. **TransitionGroup 子节点无 Key 警告**：在 `<TransitionGroup>` 网格容器内放置 IntersectionObserver 侦测桩元素（如 `<div ref="activeSentinelEl" class="stream-sentinel" />`）时，若未绑定显式 `key`，Vue 会在运行时抛出 `<TransitionGroup> children must be keyed.` 警告；
  2. **同页面 Query 变更粗暴滚顶**：Vue Router 的 `scrollBehavior` 默认对非历史后退的所有导航无条件返回 `{ top: 0 }`。当用户在书架内点击「全部 / 在读 / 已读」分段胶囊或切换筛选排序时，URL 触发 `router.replace({ query })`，导致页面视口瞬间被暴力拉至最顶部（Hero 横幅之上），打断用户的浏览心流；
  3. **流式增量追加与折叠切片失步假死**：当流式滚动或点击「再展开」触发 `loadMore` 从服务端拉取第 2 页（例如 items 从 24 扩充至 48）时，若 `ComicGrid` 内的 `watch(() => props.items)` 未识别增量追加（`isAppend`）并主动将 `visibleCount` 顺延展开一批（+12），已抵达上一页末尾的读者会发现第二页网络数据已拉取成功，但 DOM 展现切片被死死卡在第 24 本，触底侦测桩未发生位移也无法再次触发 IntersectionObserver，造成“明明拉了第二页却死活不显示”的假死 Bug。
- **红线与防误伤**：
  - **不要**在 `<TransitionGroup>` 内部包含任何缺少唯一 `:key` 的直接子节点（包括不可见的侦测桩与折叠卡）；
  - **不要**在同路由仅 query/hash 变更（`to.path === from.path`）时强制滚回顶部 `{ top: 0 }`；
  - **不要**在数据源增量扩展时（`newItems.length > oldItems.length` 且首项匹配）保持 `visibleCount` 不动导致新数据被压抑在折叠卡之后；
  - **放行/改用**：
    1. 为侦测桩绑定静态唯一键（如 `key="active-stream-sentinel"` 与 `key="unified-stream-sentinel"`）；
    2. 在 `scrollBehavior` 中显式拦截：`if (to.path === from.path) return false`，保留当前视口绝对坐标；
    3. `ComicGrid` 针对 `isAppend` 增量追加自动计算新展开切片：`activeVisibleCount.value = Math.min(activeComics.value.length, activeVisibleCount.value + props.batchStep)`，并在流式拉取结束时通过 `nextTick` 探测超高分辨率视口是否仍需补充触发，实现真正无缝丝滑的无限滚动。

### 72. DOM 属性子串匹配误伤与 iOS PWA 桌面图标漂移陷阱 (Attribute Substring Selector Collisions & Apple Touch Icon Mutation Trap)

- **本质**：使用 `link[rel*='icon']` 模糊子串匹配（`*=`）去更新浏览器标签页的 Favicon 时，由于 `'apple-touch-icon'` 包含 `'icon'` 子串，导致 iOS 专用的 `<link rel="apple-touch-icon">` 被动态覆写为 WebP 格式的随机看板头像。这不仅导致用户在刷新页面后唤起「添加到主屏幕」时捕获的图标随会话随机漂移，更因 iOS SpringBoard 桌面渲染器对 WebP 格式的兼容性缺陷，引发桌面图标变白块或退化为网页截图。
- **复现场景**：`useBrandIcon` 在客户端挂载后调用 `syncFavicon()` 执行 `document.querySelectorAll("link[rel*='icon']")`，用户在 iPhone Safari 中将网页添加到主屏幕时，图标每次刷新都随 `public/brand-icons/` 随机变化。
- **红线与防误伤**：
  - **不要**使用 `link[rel*='icon']` 通配子串选择器去操作 Favicon；
  - **不要**在运行时动态篡改系统级的 `<link rel="apple-touch-icon">` 或 PWA Manifest 主图标；
  - **放行/改用**：
    1. 动态 Favicon 严格限定精准选择器：`link[rel='icon']:not([sizes]), link[rel='shortcut icon']`，确保动态轮换仅作用于网页标签页与应用顶栏（`AppHeader` / `GateView`）；
    2. 坚守 `apple-touch-icon.png` 绝对静态、180×180 / 192×192 PNG 规范，与桌面入口的确定性身份永久绑定。

### 73. 局部状态隔离引起的全局基线死锁与不透明选择反模式（Isolated Override Deadlock & Opaque Scope Anti-Pattern）

- **本质**：
  1. 为治理单本条漫自适应反向污染全局基线（坑 69）而引入 `if (activeComicKey.value) { setOverride(...) } else { setGlobal(...) }` 后，由于全站仅能在阅读器内部唤起设置面板，导致 `activeComicKey.value` 在面板呈现时恒为非空；
  2. 读者在界面上做的任何调节，永远只能落入单本独立字典，全局基线 `stored.value` 彻底变成了既不可见、又无法通过 UI 修改的死锁黑盒；
  3. 存量设备（如 iPad）若因历史漏洞早已存有 `fit: 'width'`，每打开一本未自定义的新漫画便会退回使用全局基线的 `'width'`，迫使读者误以为配置丢失或“切换过的就不会、新的又变回宽度”，造成极大的心智负担与不透明感。
- **红线与防误伤**：
  - **不要**在没有向用户提供全局配置入口的情况下，把所有设置入口单方面降级为单本专属覆盖；
  - **不要**让全局基线成为不可查看、不可重置、无法修改的隐式黑盒；
  - **放行/改用**：
    1. **排版作用域双轨制（Dual-Scope UI）**：在面板顶部透明公开「📖 本作偏好」与「🌐 全局默认」双轨标签，读者可自主决定改动影响单本还是全站；
    2. **即改即分离 + 快捷回退**：本作处于继承态时修改立即生成单本覆盖，并提供显式「恢复跟随全局」按钮；
    3. **即时联动（Live Sync）**：修改全局默认时，若当前漫画处于继承状态，视口画卷立即所见即所得联动；
    4. **存量基线静默自愈**：通过 `HEALED_KEY` 探测并清洗历史遗留的脏基线数据，免除读者手动清空浏览器缓存的成本。

### 74. Chrome DevTools MCP 导航挂起死锁与执行上下文销毁竞争陷阱 (Chrome DevTools MCP Navigation Deadlock & Context Race Trap)

- **本质**：
  1. `chrome-devtools-mcp` 的 `navigate_page` 工具在底层将 Puppeteer 的 `page.goto(url)` 包裹在 `waitForEventsAfterAction` 拦截器中；
  2. 拦截器在执行前后启动了 `waitForNavigation`，并尝试通过 `evaluateHandle` 向当前文档挂载 `MutationObserver` 监听 DOM 变动（`waitForStableDom`）；
  3. 当目标页面为现代本地开发环境（如 Vite SPA + 自签名证书 `basicSsl` + PWA Service Worker + DevTools 虚拟覆层）时，页面导航伴随着执行上下文（Execution Context）的急剧销毁与重建。CDP 的 `evaluateHandle` 与 `waitForNavigation` 极易在此生命周期竞争中发生死锁，既无法捕获 `load` 事件也无法退出观察；
  4. 同时 `navigate_page` 默认未设置单次超时（`timeout: undefined`），导致工具调用直接挂起假死，直至触碰底层 180 秒的 CDP 协议超时（`protocolTimeout: 180000`），产生「任务每次使用都会卡死」的现象。
- **红线与防误伤**：
  - **不要**对本地开发服务器（尤其包含 PWA / HMR / 自签名证书的 SPA）直接调用裸 `navigate_page({ type: "url", url: "..." })`；
  - **放行/改用**：
    1. **原生 JS 敏捷导航（推荐）**：改用 `evaluate_script` 配合 `{ function: "() => { window.location.href = '...'; return 'navigating'; }", waitForStableDom: false }`，直接由浏览器运行时驱动 URL 跳转，完全绕过 `WaitForHelper` 脆弱的 DOM 观察器与上下文销毁死锁；
    2. **轻量就绪探测**：紧随其后使用 `evaluate_script` 配合 `waitForStableDom: false` 检查 `document.readyState === 'complete'` 及目标元素选择器；
    3. **性能录制安全触发**：页面就绪后，再调用 `performance_start_trace({ autoStop: true, reload: true, ... })`，此时底层走原生 Performance API 的生命周期采集与重载，不会触发 MCP 的 DOM 观察锁。

### 75. View Transitions 跨页前进推进时，Vue Router 的 scrollToPosition 诱发全量 DOM 强制同步重排（View Transitions Forward Nav & Vue Router scrollToPosition Forced Reflow）

- **本质**：
  1. 在 144Hz 高刷屏或弱 GPU 场景下，从书架点击漫画卡片进入详情页时，产生 130~210ms 严重顿挫与掉帧；
  2. Chromium Blink 渲染引擎在执行 `document.startViewTransition` 时，先离屏捕获旧视图快照。随后 Vue Router 在新页面组件挂载完成后的微任务队列中触发 `window.scrollToPosition`（来自 `scrollBehavior` 默认的 `{ top: 0 }` 或滚动恢复行为）；
  3. 此时 Blink 引擎正准备截取 `::view-transition-new(root)` 快照，突发的 DOM 滚动查询与设置迫使 Blink 引擎在中途对整棵已挂载的新 DOM 树执行同步强制排版（Forced Reflow），单次阻塞高达 209ms。
- **红线与防误伤**：
  - **不要**在路由导航回调或页面挂载生命周期中无节制调用滚动重置；
  - **放行/改用**：
    1. **In-Flight Pre-Capture Instant Scroll（飞行中捕获间隙瞬时重置）**：在 `router.beforeResolve` 中，将 `window.scrollTo({ top: 0, behavior: 'instant' })` 移入 `performUpdate` 内部、新组件挂载之前执行。此时旧页面被 GPU 离屏冻结快照遮挡，视口在暗中瞬时归零，读者视觉 0 跳动；
    2. **滚动行为标记短路**：在 `scrollBehavior` 中设置 `hasPreScrolled` 标记，当识别到前进推进已在飞行间隙中重置时，直接 `return false` 放行，彻底切断 Vue Router 后置微任务对 DOM 的二次几何查询，使跨页重排时间从 209ms 彻底归零（0ms）。

### 76. Vue <TransitionGroup> 的 FLIP 算法在多节点列表重排时引发连环 getBoundingClientRect 阻塞（Vue TransitionGroup FLIP Forced Reflow under High Refresh Rate）

- **本质**：
  1. 在书架点击分类标签、切换只看喜欢或按阅读进度排序时，30+ 张漫画卡片重新排布导致主线程发生 168ms 的 Forced Reflow 阻塞，在 144Hz（单帧预算 6.94ms）屏幕上出现严重连续丢帧；
  2. Vue `<TransitionGroup>` 的 `.xxx-move` 机制底层依赖 JS FLIP 算法：在 DOM 变动前后，主线程需要以 JS 循环方式对每个子节点调用 `getBoundingClientRect()` 与 `getComputedStyle()`（实测耗时达 180ms），计算初始与结束位置差值并注入 `transform`；
  3. 当每个子节点包含 3D 转换（`perspective`）、多层伪元素与阴影时，同步布局测量的开销呈几何级数爆炸，远超 144Hz 的渲染预算。
- **红线与防误伤**：
  - **不要**在 30+ 节点的高频筛选网格中滥用 Vue `<TransitionGroup>` 的 `.move` FLIP 机制；
  - **放行/改用**：
    1. **废除 JS FLIP，拥抱 CSS `@starting-style`（Baseline 2024）**：移除 `.shelf-card-move`，改由原生 CSS `@starting-style`（`opacity: 0; transform: translateY(0.75rem) scale(0.98);`）接管新卡片的淡入位移，将动画完全移交 GPU Compositor 合成器线程；
    2. **Lazy 3D Elevation**：仅在 `:hover` 与 `:focus-visible` 时按需激活 `perspective`，静态空闲状态保持纯 2D 平面，避免弱显卡常驻 3D 合成开销；
    3. **实测收益**：标签过滤重排导致的 Forced Reflow 从 168ms 骤降至 8ms（降幅 95.2%），平稳收敛进单帧时间预算。

### 77. 多态按钮覆盖 role="button" 引发的无障碍与 Space 键滚动冲突，及微型哨兵污染弹性布局间距陷阱 (Polymorphic Link ARIA Mismatch, Space Key Conflict & Flex Gap Contamination)

- **本质**：
  1. **多态组件语义污染**：在通用按钮（如 `AppButton`）实现多态跳转渲染（`<RouterLink>` 或 `<a>`）时，若强加 `role="button"`，破坏了原生链接（Link）的无障碍树语义；读屏器会将跳页链接误报为原地操作按钮，且由于原生 `<a>` 获得焦点时不响应 Space 键，用户按空格无法跳转反而会引发页面意外滚动；
  2. **微型哨兵污染弹性间距**：为消除重排而在 Flex 滚动容器内放置 1px 滚动检测哨兵（如 `sentinelStartEl`）时，Flex 引擎会自动在哨兵与首尾元素之间注入容器级的 `gap`（如 16px），无形中破坏了导航栏或工具条的边界对齐；
  3. **双轨偏好字段遗漏**：在实现「单本覆盖 vs 全局基准」双轨制时，局部覆盖持久化序列化时若遗漏 `autoTurn` 或 `autoTurnInterval` 等子字段，会导致设置面板界面声称已保存，但刷新或切话后静默丢失。
- **红线与防误伤**：
  - **不要**对底层用于跨页面导航的 `<RouterLink>` 或 `<a>` 强行赋予 `role="button"`；
  - **不要**让无界面的微型哨兵无抵消地直接参与 Flex 容器的 `gap` 间距计算；
  - **放行/改用**：
    1. **原生链接语义优先**：多态链接仅保留视觉样式 `.btn`，无障碍树保持隐式 `role="link"`，键盘 Enter 键直达且读屏器语义自解释；
    2. **哨兵布局负边距中和**：哨兵元素保留 1px 实体以满足 `IntersectionObserver` 的 `threshold`，同时通过 `margin-right/margin-left: calc(-1 * var(--space-4) - 1px)` 完全抵消 Flex gap；
    3. **双轨模型严格对称**：单本覆盖与全局基线在序列化字段与状态互斥锁（`isApplyingPreferences`）上保持 100% 结构对称。

### 78. HTML-in-Canvas 列表卡片反模式与 ResizeObserver 诱发 Grid 轨道无限自激震荡（HTML-in-Canvas Replaced Element Sizing & ResizeObserver Runaway Loop）

- **本质**：
  1. 试图使用 WICG 前瞻性草案 HTML-in-Canvas（Chromium 155+ 实验特性 `#canvas-draw-element` 的 `drawElementImage` 与 `<canvas layoutsubtree>`）接管书架长列表卡片的渲染；
  2. `<canvas>` 在浏览器排版体系中属于可替换元素（Replaced Element），具有内部固有比例与尺寸（Intrinsic Size & Aspect Ratio）。当组件通过 `ResizeObserver` 监听 DOM 容器尺寸并把像素回写至 `canvas.width / canvas.height` 时，改变了可替换元素的固有物理尺寸；
  3. 在 CSS Grid 动态网格容器（`grid-template-columns: repeat(auto-fill, ...)`）中，Grid 轨道（Track）高度默认根据单元格内容自动拉伸。写回 `canvas.height` 立即导致 Grid 重新排版并撑大轨道高度，而轨道高度扩大又再次触发子元素的 `ResizeObserver`，引发正反馈恶性死循环（Runaway Expansion Loop），导致卡片高度以每秒数千像素的速度无限膨胀，迅速引发页面假死并打崩 Blink 渲染进程；
  4. 此外，Retina 高清屏（2x~~3x DPR）下长列表若为每个卡片实例化独立 `<canvas>`，50+ 卡片需维持数十个独立 GPU Backing Store 离屏位图，额外吞噬 70MB~~120MB 未压缩显存，极易触发 GPU Context Loss 上下文崩溃；且 Canvas 位图完全丢失原生文本选择、键盘 Tab 焦点与无障碍树（Accessibility Tree），必须在其上层堆砌透明 DOM Hitbox 遮罩，架构臃肿畸形。
- **红线与防误伤**：
  - **不要**将 HTML-in-Canvas、`<canvas layoutsubtree>` 或任何基于 Canvas 的位图代理层引入文档流长列表、网格卡片等基础排版容器；
  - **不要**在 `ResizeObserver` 回调中将测量得到的元素尺寸反向写回该元素自身的固有尺寸属性（如 `canvas.width/height`、`svg.width/height`）；
  - **放行/改用**：
    1. **长列表坚守原生 DOM**：书架卡片一律坚守原生 DOM + CSS Grid 弹性网格，利用 `contain: layout style` + `container-type: inline-size` 配合 48 图增量预算，由 GPU 合成器线程直接调度滚动，维持 120 FPS 丝滑帧率且 0 额外显存开销；
    2. **精准场景定位**：HTML-in-Canvas 仅适合 3D WebGL 游戏 HUD 覆层、Canvas 复杂图表局部富文本图例或离屏海报位图导出等单体/离线场景，严禁作为通用 UI 列表基础设施。

### 79. SQLite FTS5 台词全文检索幽灵索引、访客隐藏漫画泄漏与多章节页码偏移陷阱 (FTS5 Ghost Index, Guest Data Leakage & Multi-Chapter Monotonic Page Mapping)

- **本质**：
  1. **幽灵索引残留**：漫画在删除、重新装订（Re-binding）或画页更新时，若未在事务级同步清理 `comic_dialogues_fts` 虚拟表，会导致读者搜得出台词但点击进入阅读器后画页已失效或内容错位；
  2. **访客权限条件漏洞**：在 FTS5 多表联合查询中若仅使用 `COALESCE(ci.hidden_from_guest, 0) = 0`，当某本漫画尚未在 `comics_index` 中正式入库索引（`ci.source IS NULL`）时，`COALESCE` 默认回退至 0，导致未公开的私密藏书对白被访客意外搜出并泄露；
  3. **多章节相对页码偏移**：多章节合集漫画的分卷画页伴生文件（如 `chap2/00003.ocr.json`）通常按该章内相对序号编码。若直接将局部序号存入 FTS5，读者点击跳转阅读器时会产生章内序号与全书拍平物理页码的严重错位。
- **红线与防误伤**：
  - **不要**在漫画画页发生重写或删除时漏掉 FTS5 虚拟表的原子清理；
  - **不要**在 FTS5 访客过滤中假定 `ci` 行一定存在；
  - **放行/改用**：
    1. **删除与重绑自愈闭环**：在 `delete_comic`、`replace_comic_pages` 中级联执行 `DELETE FROM comic_dialogues_fts WHERE source = ? AND source_id = ?`，重绑成功后自动触发重新扫描对齐；
    2. **访客安全双重断言**：访客过滤条件严格写为 `AND (:is_not_guest OR (ci.source IS NOT NULL AND COALESCE(ci.hidden_from_guest, 0) = 0))`，未索引与隐藏藏书 100% 阻断；
    3. **多章节全局映射**：`sync_comic_dialogues` 读取 `album.json` 自动将章内相对页码折算为全书全局单调递增页号（`1..page_count`）。

### 80. 漫画画页气泡高亮定位的 Letterbox 黑边漂移、Flex 高度传递失效与坐标自适应归一化陷阱 (Bubble Overlay Letterbox Drift, Flex Height Resolution & Adaptive Box Clamping)

- **本质**：
  1. **外层容器 Letterbox 黑边位移**：在阅读器横向翻页或适应高度模式下，外层 Flexbox 容器为了居中通常会在图片上下或左右产生大面积空白黑边（Letterbox / Pillarbox）。若高亮覆盖层直接绝对定位在外层 Flex 容器（`top: ymin*100%`），百分比基准是包含黑边的整个容器，导致高亮框相对图片物理内容严重偏移；
  2. **Flex 嵌套容器百分比高度传递失效（纵向翻页与横向翻页错位核心根因）**：在竖向翻页（`vertical-paged`）与横向翻页（`horizontal`）模式下，容器受限于视口高（`100dvh`）；若仅给中间层 `.comic-page-img-frame` 设置 `max-height: 100%` 而未指定明确高或纵横比，CSS 规范中子元素 `<img>` 的 `max-height: 100%` 因包含块高度不定而退化为 `none`，图片被原始分辨率彻底撑大（如 1071px）并在 Flex 居中下向上下各溢出 295px，而挂载在 frame 的覆盖层仅有 480px，导致高亮框相对画面向下暴跌 25%~30%，文字与高亮框严重错位；
  3. **底图加载期动效夭折**：若在底图网络加载期间直接触发 2 秒呼吸淡出动画，慢网下等图片真正解码呈现时动画早已播完淡出，读者完全看不见高亮；
  4. **坐标多标度与越界溢出**：若 OCR 伴生数据的包围盒坐标为 0..1000 标度（RapidOCR/Qwen2-VL 输出）或百分比 0..100，未缩放前直接被 clamp 钳制在 1.0；或顶部边缘分镜（`ymin < 0.12`）提示徽标向上展开被视口截断。
- **红线与防误伤**：
  - **不要**将画卷覆盖层直接挂载在外层包含 Letterbox 黑边的自适应容器上；
  - **不要**在翻页模式下允许 `.comic-page-img-frame` 与 `<img>` 脱节自生黑边或发生 Flex 溢出；
  - **不要**在底图加载未完成（`!imageReady`）时提前激活呼吸脉冲动效；
  - **放行/改用**：
    1. **动态注入图片宽高比锁定帧（Aspect-Ratio Lock）**：在 `ComicPageImage.vue` 解码就绪瞬间读取 `naturalWidth / naturalHeight` 并绑定 `:style="{ aspectRatio: naturalRatio }"`，frame 设为 `display: block; width: auto; height: auto; max-width: 100%; max-height: 100%`，在 `vertical-paged` / `horizontal` 下 `img` 设为 `width: 100%; height: 100%`，使容器与底图在任何屏幕尺寸和多页拼图下以 0 像素误差绝对咬合贴紧；
    2. **底图就绪门禁**：高亮计算严格绑定 `imageReady` 指示，底图就绪瞬间才点燃 2.2 秒呼吸脉冲；
    3. **坐标自适应归一化严格防溢出**：`parseBubbleBox` 智能探测 `maxVal > 2` 并按 1000 或 100 自适应降阶为 [0, 1]，通过 `Math.max(0, Math.min(1, v))` 严格钳位，顶部分镜提示徽标自适应翻转至下方（`is-placement-bottom`），右侧分镜自适应靠右对齐。

### 81. 前台搜索栏双重意图冲突、破坏性空状态劫持与 Combobox 视口盲航陷阱 (Dual Search Intent Conflict, Empty State Hijacking & Combobox Viewport Tracking)

- **本质**：
  1. **双重搜索意图冲突与破坏性空状态劫持**：书架搜索栏承担「本地藏书过滤」与「全书台词全文检索」双重意图。若台词检索未命中（0 条）时无差别将联想浮层置为展开态（`isOpen = true`），会导致用户在书架搜索书名或作者时，台词浮层突然大字弹出空状态警告（如「未在已索引分镜中找到台词」），严重遮挡书架已过滤出的漫画卡片，造成“书库无此书”的虚假心理恐慌；
  2. **Combobox 键盘导航视口盲航**：在具有固定高度与 `overflow-y: auto` 的联想列表中，若仅更新键盘焦点索引（`focusedIndex`）而未联动 DOM 的 `scrollIntoView`，当选项超出首屏可视区（如第 4~20 条）时，高亮项跌出折叠线，键盘用户失去视觉反馈（盲人摸象），敲击回车容易误跳不可见结果；
  3. **全文检索片段标签注入风险**：后端 FTS5 的 `snippet()` 通常带有 `<mark>` 高亮标签。若前端直接使用 `v-html` 渲染，极易引入 XSS 注入风险。
- **红线与防误伤**：
  - **不要**在后台台词自动检索返回 0 条时自动展开浮层；
  - **不要**在联想面板长列表中允许键盘焦点在视口之外盲目移动；
  - **不要**在渲染搜索结果与高亮片段时使用原始 `v-html`；
  - **放行/改用**：
    1. **静默伴生原则**：后台自动防抖检索仅当 `results.length > 0` 时才展开浮层；若为 0 条则保持静默隐藏，仅当用户主动按下 `ArrowDown` 显式探寻分镜时才展开空状态；
    2. **视口跟随对齐**：在组件中 `watch(focusedIndex)`，利用 `activeEl.scrollIntoView({ block: 'nearest', behavior: 'smooth' })` 确保键盘选区永远平滑居于可视区；
    3. **纯声明式 Token 解析**：手写 `parseSnippetTokens` 纯函数，将带 `<mark>` 的文本安全切分为 `{ text: string, isMark: boolean }[]`，在模板中用 `<mark>` 与 `<span>` 声明式渲染，杜绝任何 XSS。

### 82. SQLite FTS5 Trigram 短词全表扫描锁死、单库 WAL 写锁争抢与命令前缀输入流解耦陷阱 (FTS5 Trigram Short-Query LIKE Table-Scan Lockup, SQLite WAL Bulk-Write Starvation & Command Chip State Decoupling)

- **本质**：
  1. **SQLite FTS5 Trigram 2 字短词全表扫描锁死**：SQLite 原生 `tokenize='trigram'` 全文倒排索引要求查询项至少满足 3 字符（3-gram）。若用户键入 1~2 个字符且未做长度前置门禁，FTS5 引擎无法走倒排索引，被底层强制降级为无索引的全表逐行 `LIKE '%query%'` 扫描。在数万部漫画伴生、数百万至千万行台词的生产数据下，单次查询即可造成 SQLite 进程 CPU 100% 飙满、长达数秒挂起甚至死锁；
  2. **单库 WAL 写锁争抢与备份膨胀**：在万级与十万级规模下，离线 OCR 批量同步流水线会产生高频、耗时的批量插入（单个图集可产生数十至上千条台词包围盒记录）。SQLite 的 WAL 模式虽然支持并发多读，但全局始终**仅允许单个活跃写事务**。若将海量台词全文索引与承载用户关键业务（书架元数据、翻页进度打点、喜欢收藏、访客通行证名册）的 `comic_shelf.db` 合库存储，后台批量写入会长时间独占写锁，导致前台读者翻页进度打点与收藏频繁遭遇 `SQLITE_BUSY` 锁争抢异常，同时导致主数据库文件急剧膨胀至 GB 级，破坏轻量快速备份；
  3. **书架全局搜索框输入流污染与卡片网格清空**：书架主界面的搜索框原本承担全书标题、车号与作者的即时响应过滤。若直接在该输入框中打字搜索台词（例如输入“战斗”或“真相”），而未做意图分流，书架列表会立即被判定为“无此书名”而瞬间清空，引发读者的误操作挫败感（“一打台词书架就空了”）。
- **红线与防误伤**：
  - **不要**允许小于 2 个字符的模糊查询未经拦截穿透至 SQLite FTS5 引擎；
  - **不要**将海量离线 OCR 文本倒排索引与用户端核心状态共用同一个 SQLite 数据库文件；
  - **不要**在同一输入框内将台词长文本直接混杂透传给书架卡片列表过滤；
  - **放行/改用**：
    1. **前后端双重短词防爆守卫（Short-Query Guard）**：前端 Composable 与后端 FastAPI 路由在入口处设立硬性门禁，长度 `< 2` 字符时直接短路拦截（前端不发起网络请求，并渲染“请输入至少 2 个字以检索台词”提示文案；后端直接返回空列表）；2 字符短词查询走强制 bounded `LIMIT 30`；
    2. **台词专库垂直解耦（Zero Lock Contention）**：将台词全文倒排索引虚拟表 `comic_dialogues_fts` 及增量更新元数据 `comic_ocr_sync_meta` 从主库物理剥离为独立的 `backend/data/comic_dialogues.db`。读写完全独立连接池，后台海量 OCR 同步拥有专属写入通道，与前台读者翻页与收藏写入零写锁争抢；检索时在专库完成 FTS5 匹配后，仅通过主键批量回填主库封面与标题元数据；
    3. **斜杠快捷指令中枢与命令胶囊（Command Chip & Freeze Flow）**：在搜索栏引入 `/` 快捷指令唤醒菜单（`/台词`、`/车号`、`/作者`、`/随机`）。激活台词检索后，搜索框视觉前缀提取为朱砂印章样式的命令胶囊（`〔 💬 台词 × 〕`），同时将供给书架列表过滤的 `effectiveShelfSearch` 严格冻结为空，书架背景卡片安然不动，输入流专供台词检索 Popover 消费；按 Backspace 或点击移除胶囊时平滑恢复常规搜索。

### 83. 阅读器无条件挂载分镜覆盖层导致长篇画卷性能退化与气泡 URL 状态残留陷阱 (Unconditional Reader Bubble Overlay Mounting & Lingering Bubble URL Trap)

- **本质**：
  1. **长篇画卷全量无条件实例化**：在阅读器核心视口（`ReaderViewport.vue`）中，若在遍历 `group.pages` 循环中无条件渲染 `<ReaderBubbleOverlay>`，即使用户是从书架正常点入（`targetBubble === null`），整本漫画的每一页（动辄 100~200+ 页）也会全量实例化 Overlay 组件并计算内部属性，造成昂贵的 VNode 与响应式订阅开销，在长篇连续滚动或切页时诱发主线程卡顿；
  2. **URL 查询参数残留**：当用户通过台词搜索直达进入（携带 `bubble_box`、`bubble_text`）后，若在呼吸高亮结束或翻到后续页面时未擦除该查询参数，用户向后翻阅多页后若执行复制分享或刷新，旧页面的气泡高亮参数仍会挂在 URL 上产生脏状态。
- **红线与防误伤**：
  - **不要**在阅读器画页循环中无条件挂载覆盖层组件；
  - **不要**在气泡高亮使命完成后将临时的分镜坐标参数永久残留在 URL 中；
  - **放行/改用**：
    1. **模板级精确短路门禁**：在 `ReaderViewport.vue` 模板中强制使用 `v-if="targetBubble && targetBubble.page === page"`。非台词检索进入时整本漫画 0 个组件实例化；台词检索进入时全书仅命中单页挂载 1 个实例；
    2. **超时与翻页静默擦除**：气泡呼吸高亮淡出后（2.8 秒）或读者翻离当前画页时，自动调用 `dismissBubble()` 卸载组件，并通过 `router.replace` 原地静默擦除 `bubble_box`、`bubble_text` 等参数，保持 URL 纯净。

### 84. 进度条四舍五入虚假满额、浮点噪点污染与单页重试缺失陷阱 (Progress Bar Rounding Distortion, IEEE 754 Float Noise & Transient Prefetch Failure Trap)

- **本质**：
  1. **四舍五入语义失真（Rounding Distortion）**：直接使用 `Math.round((cached / total) * 100)` 计算百分比。当 208 页中完成 207 页时，`207 / 208 = 0.99519...` 被四舍五入强行进位为 `100%`，但底层 `cached < total` 且 `cache_complete = false`。导致界面显示“100%”却同时显示“207/208”，按钮仍为可操作的“缓存全部”而非“已全部本地化”，产生严重的认知割裂；
  2. **16 位浮点噪点污染 DOM**：未对计算比率做精度截断，直接将 `0.21153846153846154` 等原始 JS 除法结果注入 `--progress` 和 `scaleX()` 内联样式中；
  3. **单页网络抖动导致预缓存中断且失真**：后端在拉取数百页图片时，若遇到 1 页网络超时或远端限流，捕获异常后直接跳过退出，未做任何就地瞬态重试，前端误判为完全完成；
  4. **磁盘与元数据失步**：画页实际已在磁盘落盘（如阅读器直读），但 `album.json` 中 `page.cached` 滞后。
- **红线与防误伤**：
  - **不要**对任务进度使用无限制的 `Math.round` 进位至 100%；
  - **不要**将未截断的高位浮点数直接注入 DOM style 与 CSS 变量；
  - **不要**在后台长任务下载中对单页网络超时完全不做重试就直接标记结束；
  - **放行/改用**：
    1. **未达终态不进位法则（Non-terminal Floor Clamp）**：全站进度百分比统一走 `calculateProgressPercent`（`@/utils/progress`）。只要 `current < total`，一律封顶 99%（向下取整 `Math.min(99, Math.floor(...))`），当且仅当全部就绪时才返回 100%；
    2. **高精亚像素截断（4 位精度规约）**：`truncateProgressFloat` 统一截断保留 4 位小数（0.0001 / 0.01% 精度，4K 屏下误差仅 0.38px），杜绝 DOM 浮点噪点；
    3. **瞬态网络重试与漏页通知**：后端 `prefetch` 循环内注入单次 300ms 退避重试，平滑绝大部分网络抖动；若仍未完成则广播 `cache_partial`，前端 Toast 友好提示；
    4. **本地轻量自愈（Local Cache Reconciliation）**：在查询详情与进度时自动探查磁盘已存在的文件，自愈修正 `page.cached = true`。

### 85. 条漫连续模式终页高度不足致物理触底失效、流卷停靠态竞态循环与手势避让死锁陷阱 (Webtoon Short Last-Page Clamping Failure, Continuous Auto-Scroll Race Condition & Docking Lockup Trap)

- **本质**：
  1. **短终页几何对齐落空（Short Last-Page Distance Trap）**：在竖向连续（条漫）模式下，原分屏吸附算法通过计算 `Math.abs(spread.offsetTop - scrollTop)` 确定最临近画页。当整话最后一页物理高度小于浏览器视口高度时（例如终页高度 584px，视口高度 900px），滚动容器在完全触底（`scrollTop === scrollHeight - clientHeight`）时，最后一页顶边仍处于视口中下部，`scrollTop` 永远无法触达该页的 `offsetTop`。算法在距离判定上始终将倒数第二页判定为“最近页”，导致页码永远卡在 `N-1 / N`（例如 `160 / 161`），底层 `atChapterEnd` 永远无法激活，下一话跳转横幅彻底丢失；
  2. **流卷停靠态与滚动事件竞态循环（Auto-Scroll Docking Race Condition）**：在条漫基于 `requestAnimationFrame` 匀速自动流卷推进中，每帧物理更新 `el.scrollTop` 均会触发原生 `scroll` 事件。若在 `handleScroll` 中无差别调用翻页倒计时重置 `resetAutoTurnCountdown()`，当流卷触底触发 `isDockedAtEnd = true` 并停止 rAF 时，触底最后一帧派发的异步 `scroll` 事件会立即调用 `resetAutoTurnCountdown()` 将 `isDockedAtEnd` 冲刷置回 `false` 并重新唤醒 rAF，引发底端无意义空转与状态撕裂；
  3. **驻留锁死与回滚死锁（Docking Freeze Trap）**：读者抵达话末触发 `isDockedAtEnd` 驻留刹车后，若向上滑动回看前文，若底层仅在用户主动点击播放/暂停时才释放驻留锁，会导致软避让（Soft Yield）1.5 秒后由于 `isDockedAtEnd === true` 而永久无法恢复自动流卷，造成读者困惑；
  4. **末页读阅中 HUD 速度控制提前退场**：若仅根据 `atLastGroup`（`currentGroupIndex >= lastGroupIndex`）作为 HUD 自动翻页按钮的隐藏门禁，当读者阅读线刚接触最后一页顶部时，由于当前组索引变为末组，右下角流卷速度控制胶囊（如 `80px`）突兀消失，导致读者在阅读整张末页长图时彻底丧失随时暂停控制的能力。
- **红线与防误伤**：
  - **不要**在连续滚动模式下仅依赖页面顶边到视口顶端的绝对距离判定当前页；
  - **不要**在连续流卷模式下的物理滚动事件监听中无条件重置离散倒计时；
  - **不要**在读者已经回滚离开话末后依然强制锁死话末停靠状态；
  - **不要**在条漫模式下将离散末屏判断作为连续流卷 HUD 的收起依据；
  - **放行/改用**：
    1. **绝对触底夹紧与 40% 视口阅读线几何相交（Bottom Clamping & Read-Line Intersection）**：当滚动容器距离底端 `position >= max - 24` 时，确定性将当前组索引钳制为 `lastGroupIndex`，彻底根治短终页无法翻至最后一页与无下一话按钮问题；非极端边界采用视口高度上方 40% 有效阅读线与画页几何相交探测；
    2. **翻页排版模式分流守卫（Paging Mode Guard）**：`useReaderNavigation` 仅在离散翻页模式（`settings.mode !== 'vertical-continuous'`）下在滚动时触发 `resetAutoTurnCountdown()`，条漫模式完全交由 rAF 流卷状态机接管，杜绝竞态死循环；
    3. **回滚自愈解绑（Scroll-Away Un-docking）**：读者主动通过滚轮、触控或滚动条向上滑动离开底端（`el.scrollTop < max - 40`）时，即刻释放 `isDockedAtEnd` 驻留锁，静止 1.5 秒后平滑恢复自动流卷；
    4. **停靠态解耦与行内章末过渡卡片（In-flow Chapter Transition & Decoupled Docking）**：条漫模式下废除遮挡分镜画面的悬浮下一话横幅，改在画卷尾部自然内嵌流式章末卡片（`.reader-webtoon-chapter-end`）；HUD 控制按钮以 `isContinuous() ? !isDockedAtEnd : !atLastGroup` 进行解耦，末页整张画卷阅读过程中速度胶囊全程常驻可用，直至滚动完全抵达底端停靠卡片时才平滑收整。

### 86. 超长单本主滚动容器全量 offsetTop 重排风暴致 Chrome 崩溃与 iPad WebKit 惯性动量锁死 (High-Volume Full-DOM offsetTop Reflow Storm & WebKit Momentum Lockup)

- **本质**：
  1. **百页/千页单本全量 O(N) 重排风暴**：在单话高达 900+ 页的超长图集（如拆帧漫）中，若在 `handleScroll` 中使用 `querySelectorAll('[data-group-index]')` 并用 `for` 循环无差别遍历所有 900+ 个 DOM 节点逐一读取 `spread.offsetTop` 和 `spread.offsetHeight`，在 60/120 FPS 滚动下每秒产生数万次强制同步重排（Forced Synchronous Layout / Reflow Thrashing）。若缺少 `content-visibility: auto`，Chrome 渲染主线程 CPU 瞬间 100% 跑满当场假死崩溃；
  2. **iPad WebKit 触控惯性滚动与主线程重排冲突**：在 iPadOS Safari 中，手指滑屏惯性由独立的 Compositor（合成器）线程推进。主线程在滚动时高频密集读取 900+ 次 `offsetTop`，直接诱发 WebKit 主线程与合成器线程的图层几何失步（Desync），触发 WebKit 保护性终止动量并夹紧边界，导致滚动条瞬间撑满 100% 且手势卡死，直至手指离开、滚动静止后（Scroll Stabilized）主线程才完成计算恢复；
  3. **`content-visibility: auto` 护城河价值与稳健占位**：对于数百上千页长本，`content-visibility: auto` 配合 `auto 100dvh` 占位是阻断浏览器全量 DOM 布局的核心保障，绝对不能简单删除；真正的病根是 JS 端的全量 DOM 读取循环。
- **红线与防误伤**：
  - **不要**在阅读器高频滚动事件监听中对全部画页 DOM 执行全量 `querySelectorAll` 与 `offsetTop` 线性扫描；
  - **不要**在面对超长单本时盲目移除 `content-visibility: auto` 导致现代浏览器在数百页图集下崩溃；
  - **放行/改用**：
    1. **保留 `content-visibility: auto` + `contain-intrinsic-block-size: auto 100dvh`**：尊重移动端视口真实几何，依托浏览器内置跳过机制保障数百页大图集的常态流畅渲染；
    2. **局部邻域探测 + 二分查找收敛（O(1) ~ O(log N) 算法）**：`useReaderNavigation` 废除 `querySelectorAll` 全表扫描。平滑连续滚动时优先探测当前页及其前后各 2 页（99% 命中，仅 1~~2 次轻量查询）；大跨度跳转时先根据滚动百分比插值探测，最后以二分查找收敛（1000 页下最多探测 10 次）。每帧重排查询从 900 次暴降至 1~~2 次，CPU 降至 0.1%，彻底消灭 Chrome 崩溃与 iPad WebKit 动量掐死。

### 87. 海量藏书与长篇画卷前端高频计算反模式（O(N) 遍历、比较器内 new Date 与击键全量小写字符串风暴）

- **本质**：
  1. **分屏页码映射 O(N) 响应式遍历反模式**：在超长单本（如 1000 页）中，若通过 `pageGroups` 二维数组使用 `for (let i = 0; i < groups.length; i++)` 逐项执行 `groups[i].includes(page)` 进行页码与分组换算，在阅读器翻页、滚动同步或预加载定位时，强制遍历 1000 个数组，不仅计算浪费，还强行触发整个 `pageGroups` 响应式二维数组提前求值；
  2. **排序比较器内高频构造 `new Date()` 堆风暴**：在书架收录时间倒序与接卷推荐打分排序中，直接在 `sort((a, b) => new Date(b.time) - new Date(a.time))` 中解析时间。在 1000~5000 本书排序下，比较器执行 $O(N \log N) \approx 10,000 \sim 60,000$ 次，导致主线程创建成千上万个临时的 `Date` 堆对象与 ISO 字符串解析，诱发严重垃圾回收（GC）停顿；
  3. **书架检索击键字符串小写化风暴**：用户在书架搜索框每敲击一个字符，若在 `list.filter` 中对每本藏书的所有标签、作者、作品、角色、章节标题数组无脑调用 `.toLocaleLowerCase()` 与 `.some()`，单次按键产生数万个临时小写字符串，主线程严重丢帧掉帧；
  4. **日漫 RTL 模式横向滚动大跨度跳转插值反向**：在横向从右到左（RTL）排版下，DOM 元素物理倒序排列。若滚动条大跨度拖拽估算未将 `rtl` 纳入反转考虑，会导致拖拽时定位跳向相反章节。
- **红线与防误伤**：
  - **不要**在单调递增页码映射中使用 $O(N)$ 遍历和 `.includes()` 数组查找；
  - **不要**在 `sort()` 比较器内部反复调用 `new Date()` 或未缓存的 `localeCompare()`；
  - **不要**在搜索过滤的每帧击键中重复遍历数组并生成大量临时小写字符串；
  - **放行/改用**：
    1. **严格 $O(1)$ 数学封闭解（Closed-Form Math Clamping）**：`useReaderPaging` 直接基于 $\lfloor (\text{page} - \text{first}) / \text{ppv} \rfloor$ 计算分组索引，耗时从 0.5ms 降至 0.0001ms，彻底解耦 `pageGroups` 响应式依赖；
    2. **单遍时间戳规约与单例校对器（Single-Pass Timestamp Map & Intl.Collator）**：排序前通过单遍循环以 `Date.parse()` 预提取时间戳数值并完成未读/已读切分，比较器退化为纯数字减法；中文书名排序单例化复用 `const zhCollator = new Intl.Collator('zh-CN')`；
    3. **弱引用搜索索引（WeakMap Memoized Search Text）**：`useLibraryFilter` 采用 `itemSearchTextCache = new WeakMap<LibrarySummary, string>()` 首次组合多维度文本并小写化，后续击键仅执行单次 C++ 原生 `includes(needle)` 匹配，对象销毁时自动 GC；
    4. **RTL 双向滚动感知**：`resolveNearestGroupIndex` 显式感知 `rtl` 并在横向翻转时以 `1 - position / max` 执行精确线性插值。

### 88. 缓存对账与轮询接口高频同步 I/O 导致磁盘争抢陷阱 (Cache Polling Sync Disk I/O Storm & Atomic Scannable Cache Guard)

- **本质**：
  1. **高频轮询接口同步磁盘 I/O 风暴**：在漫画下载与缓存进度轮询场景中，前端客户端以 1 秒为间隔密集轮询 `/api/library/{source}/{id}/cache`。若在获取进度（`get_cache_progress`）或缓存完成时直接无条件触发全量磁盘对账（`reconcile_cached_pages`），且对账逻辑采用 $O(N)$ 遍历画页并在循环内部逐页调用 `os.path.exists()`，当一本漫画有数百或上千页时，单次轮询产生数百次磁盘系统调用（syscall），多个读者并发或多卷下载时导致宿主机磁盘 I/O 100% 跑满；
  2. **锁外覆写与竞态写入风险**：若对账检测到磁盘画页发生变化，直接就地写回 `album.json` 而未加写互斥锁，极易与后台下载工作线程或阅读器在线直读缓存的写入产生并发文件截断或数据竞争（Data Race）。
- **红线与防误伤**：
  - **不要**在轮询端点热路径中无条件执行阻塞式同步磁盘对账；
  - **不要**在循环内部使用 `os.path.exists()` 逐一探测海量画页文件；
  - **不要**在无锁状态下并发覆写 `album.json`；
  - **放行/改用**：
    1. **只读查询与写入彻底解耦**：`/cache` 进度查询端点严格作为纯内存只读快照读取，禁止在查询路径触发同步落盘写入；
    2. **单遍扫描集合匹配（Single-Pass `os.scandir` Set Intersection）**：`reconcile_cached_pages` 采用单次 `os.scandir` 扫描目标目录将磁盘已有文件名存入 `Set`，画页判定退化为内存 $O(1)$ 查找，系统调用从 1000 次暴跌为 1 次；
    3. **双重原子守卫（Double-Checked Locking & Atomic Guard）**：仅在发现磁盘与元数据存在差异时，才获取 `_cache_guard` 锁执行落盘，写入采用临时文件原子替换（Atomic Rename），彻底杜绝脏写。

### 89. 翻页模式大跨度跳转阈值与正反候选页探测陷阱 (Paged Reader Large Jump Threshold & Bidirectional Probe Candidates)

- **本质**：
  1. **翻页模式大跳转探测误判**：在阅读器横向与纵向分页模式（`settings.mode !== 'vertical-continuous'`）下，页面由吸附滚动（Scroll Snap）驱动。若大跨度跳转阈值定为绝对像素（如 600px），在 iPad、高分屏或双页拼卷（双页跨度可达 1600px~2400px）场景下，一次正常的单屏翻页就会超过 600px，被算法误判为“用户拖拽了滚动条发生了大跨度跳转”，强制触发全量插值与 DOM 二分查找，破坏平滑翻页性能；
  2. **快速连续翻页候选页探测越界（Probe Miss）**：快速划动翻页时，用户可以在一个动画帧内跨越 2 个分组。若候选邻域仅探测当前组的前后 1 组（`±1`），快速翻页瞬间直接落空，导致每帧回退到二分查找；
  3. **条漫回滚自愈驻留死锁**：条漫模式下到达章节末尾触发停靠锁（`isDockedAtEnd = true`）后，若用户向上滑动回看前文，若缺乏原生滚动事件的主动解绑机制，停靠锁无法解除，导致静止 1.5 秒后软避让失效、自动流卷永远无法恢复。
- **红线与防误伤**：
  - **不要**在分页模式下使用绝对固定像素作为大跨度跳转的判定门禁；
  - **不要**在快速滚动探测中仅保留单项邻域探测；
  - **放行/改用**：
    1. **动态视口相对阈值（Dynamic Viewport Ratio Clamp）**：大跨度跳转门禁采用 `pageSize * 0.5`（或横向/纵向容器尺寸的半屏跨度），自适应单页、双页及任意分辨率设备；
    2. **局部双向候选集拓宽（±2 Bidirectional Probe）**：邻域探测拓宽为 `[cur, cur + 1, cur - 1, cur + 2, cur - 2]`，99.9% 覆盖快速翻页场景，二分查找触发率降至 0.01%；
    3. **滚动事件解耦与自愈解绑**：监听主容器原生 `@scroll` 事件，在条漫向上回滚时（`scrollTop < max - 40`）自动释放 `isDockedAtEnd` 驻留锁，保证读者手势回滑后平滑恢复自动流卷。

### 90. 万级藏书客户端多维搜索与主线程 CPU 掉帧陷阱（Web Worker 卸载、极简 ID 传递与三层防御） (Large-Scale Library Client-Side Filtering & Web Worker Offloading)

- **本质**：
  1. **万级藏书主线程 CPU 击键雪崩**：当个人漫画收藏量达到上万本时，全量藏书在客户端内存中包含标题、作者、作品、车号、标签及章节标题。在搜索框打字时，即便有 WeakMap 缓存搜索文本，每敲击一个字符在主线程进行 $10,000 \times O(\text{filter}) + 10,000 \log(10,000) \times O(\text{sort})$ 计算仍需耗时 20ms~50ms，直接导致输入框掉帧、光标卡顿甚至产生输入法吞字；
  2. **Worker 线程结构化克隆风暴（Serialization Storm）**：若将过滤结果以完整对象数组（包含万级图书所有元数据）通过 `postMessage` 在 Worker 与主线程间频繁双向传递，浏览器的 `structuredClone` 序列化与反序列化耗时将高达 30ms~60ms，彻底抵消 Worker 卸载的收益；
  3. **误以为万本藏书展开会导致 DOM 卡死**：实际上，纸间首页在视图层拥有 `usePaginationFold`（受控折叠，默认初始仅挂载 12 张卡片，安全刹车 60 张，每次搜索自动重置折叠步长），因此万级图书检索时 DOM 树上的节点数始终被死死约束在预算内。真正的卡顿点在**主线程 JS 过滤排序计算**以及用户主动点击「全部展开」后的**海量卡片样式与图片排版渲染**。
- **红线与防误伤**：
  - **不要**在 Web Worker 通信中双向全量传输重量级业务对象数组；
  - **不要**在缺乏 Worker 运行环境（如 Node/SSR/Vitest）的场景下强制依赖 Web Worker；
  - **不要**在超大列表中允许万级 DOM 节点无约束全量挂载；
  - **放行/改用**：
    1. **三层立体防御护城河**：
       - **第 1 层（计算卸载）**：`useLibraryFilter` 采用双轨架构：<1000 本或 Node 环境主线程极速纯函数同步运算（0 延迟）；$\ge 1000$ 本无感卸载至 `libraryFilter.worker.ts`。通信协议仅传递微量查询参数（~50 字节）与轻量有序 ID 列表（`string[]`，仅几十 KB），主线程利用预构建的 `Map<string, LibrarySummary>` 以 $O(1)$ 映射还原，主线程全程保持 120 FPS 丝滑响应；
       - **第 2 层（DOM 节流）**：`usePaginationFold` 牢牢锁定渲染预算，每次用户打字检索时自动将可见步长重置为初始 12 项，绝不允许上万个 DOM 卡片同时进驻文档树；
       - **第 3 层（展开软封顶与局部隔离）**：在 `usePaginationFold` 的 `loadAll` 中施加 120 本软封顶（支持按需阶梯递进），卡片保留 `contain: layout style` + `container-type: inline-size` 严格隔离重排；彻底移除 `content-visibility: auto`，杜绝其隐式激发的 `contain: paint` 对卡片 `-0.35rem` 悬浮浮动与弥散阴影（`--shadow-2`）的死黑硬件裁切（严格遵守本指南第 7 条避坑铁律）。

### 91. Composable 传参膨胀与跨层对象聚合反模式（Composable Parameter Explosion & Sub-State Object Aggregation）

- **本质**：
  1. **参数爆炸与形参错位风险**：当大型复合视图（如 `ReaderView`、`ComicDetailView`）向下沉淀高阶编排 Composable 时，若简单将所有子状态机展开为扁平参数列表（例如展开传入 30+ 离散的 `Ref` 与普通回调函数），视图调用处将充斥数十行冗长参数样板代码，参数顺序极易错位导致静默类型漂移与难以排查的 Bug；
  2. **过度解构与领域生命周期撕裂**：将底层状态机彻底解构为孤立变量后，各变量丢失了所属的领域聚合边界，跨模块协同（如翻页状态机与自动阅读状态机的联动）演变为混乱的离散变量乱飞，严重破坏了代码的可维护性与自解释性。
- **红线与防误伤**：
  - **不要**在封装高阶编排 Composable 时设计接收 10 个以上平铺离散参数的巨型签名；
  - **不要**在视图层无脑将所有子状态机全量扁平解构后再拼装传出；
  - **放行/改用**：
    1. **子状态机对象整包聚合（Sub-State Aggregation Pattern）**：保持子状态机实例的领域完整性，高阶调度器直接接收子状态机命名对象（如 `{ settings, bubble, data, paging, chrome, navigation, autoTurn }`）；
    2. **内部精准就地解构**：在高阶 Composable 函数体头部根据业务调度需要就地解构，视图层仅需一行干净的调用传参，将组件脚本行数彻底压低至 150 行以内，杜绝类型漂移。

### 92. Vue 模板增量 TS 检查与 Composable 解构漏绑陷阱（Vue Template Incremental Type Checking & Destructuring Leakage）

- **本质**：
  1. **Vue 模板 TS 检查盲区（vue-tsc 绕过陷阱）**：标准 `vp check` 或 `tsc` 仅对 `.ts` 脚本和 `<script lang="ts">` 内部代码进行类型校验，默认无法深入检测 `.vue` 模板 `<template>` 内部的表达式与属性绑定错误；
  2. **Composable 抽取后顶层解构遗漏（Template Property Unbound）**：在执行「视图轻量化」将大量逻辑从 Vue 组件下沉到 Composable 期间，若开发者在 `<script setup>` 中将逻辑抽取后忘记显式解构模板实际引用的 Ref 或方法（如 `isOffline`、`showingRange`、`loadAll`、`goToChapter`），模板在运行时会访问未定义属性或因深层嵌套 Ref 未在顶层解包而导致逻辑静默失效（产生 TS2339 / TS2551 错误）。
- **红线与防误伤**：
  - **不要**在重构或新建 `.vue` 组件后仅依赖 `vp check` 就宣称类型检查通过；
  - **不要**在 Composable 内部隐藏模板强依赖的变量而不向外解构导出；
  - **放行/改用**：
    1. **改动组件必跑 `pnpm type-check`**：任何涉及 `.vue` 文件的变更，交付前必须运行 `pnpm type-check`（基于 `vue-tsc --build` 增量模式，只验证改动文件，毫秒级通过），彻底排查模板绑定的类型错误；
    2. **契约自解释与精准解构门禁**：Composable 必须清晰声明返回类型契约与 JSDoc，视图消费层在 setup 顶层精准解构模板实际绑定的 Ref 与函数，杜绝因深层对象传给模板而引发的响应式断裂与 TS 类型盲区。

---

## 🚦 交付门禁（四步必跑）

1. **静态检查**：`vp check`（前端 0 error、0 warning、格式规范）；
2. **Vue 模板类型检查**：`pnpm type-check`（基于 `vue-tsc --build` 增量模式，排查 Vue template 内部 TS 属性绑定与类型错误，只验证改动文件加速）；
3. **后端测试**：`pnpm test:py`（后端 0 syntax/import error，中间件全链路测试通过）；
4. **定向单测**：仅运行改动对应的单测文件（严禁无差别全量阻塞）。
