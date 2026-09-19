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
- **红线与防误伤**：**不要**在包含 Hover 浮动、叠牌倾斜或投影弥散的卡片上设置 `contain: paint` 或 `content-visibility: auto`；**严禁**试图通过“增加外层 DOM 壳将 Hover/阴影移至外层”的绕道方案（这不仅会因内层 `contain: paint` 导致 3D 叠牌副封面偏角切平与 Tooltip 锚定异常，还会因动态自适应网格的 `contain-intrinsic-size` 估算误差引发滚动条剧烈跳跃与 CLS 抖动）；**放行/改用**纯扁平无溢出的静态列表放行，带立体浮动的卡片改用 `contain: layout style` 并依托万级藏书三层防御架构（12 本切片 + 60 本刹车 + 120 本展开软封顶，见避坑 #90）实现零负担满帧渲染。

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

### 76. Vue <TransitionGroup> 的 FLIP 算法与内部 Render 测量在多节点列表重排时引发连环 Forced Reflow（Vue TransitionGroup FLIP & Render-Level Forced Reflow under Dynamic Grids）

- **本质**：
  1. 在书架滚动加载 48~~120 本漫画后，回到顶部切换分类标签或筛选条件，主线程出现 30~~168ms 的 Forced Reflow 阻塞，在 144Hz 屏幕上出现楼梯状连环丢帧；
  2. **致命深层机制（Vue 官方运行时源码层面）**：单纯从 CSS 中移除 `.shelf-card-move` 类并不能阻止重排！Vue `<TransitionGroupImpl>` 的 render 函数在每次更新时，**无条件遍历所有子节点**直接执行 `positionMap.set(child, getPosition(child.el))`（内部直接调用 `el.getBoundingClientRect()`）；同时在大量卡片离场（如 48 本过滤为 7 本，41 本离场）时，对每个离场卡片执行 `onLeave` 钩子读取 `window.getComputedStyle(el).transitionDuration`（`getTransitionInfo`）。DOM 变动与同步样式查询交错，必然导致密集 N 次的连环 Forced Reflow（Layout Thrashing）；
  3. 当每个子节点包含容器查询（`container-type`）、多层伪元素与阴影时，同步布局测量的开销呈几何级数爆炸。
- **红线与防误伤**：
  - **不要**在海量卡片网格或高频重排长列表（如 `comic-grid`、`page-grid`、`chapter-grid`）使用 Vue `<TransitionGroup>` 包装；单纯移除 `-move` CSS 类属于治标不治本；
  - **放行/改用**：
    1. **彻底废除 `<TransitionGroup>`，回归原生 `<div>`**：将 `ComicGrid.vue`（`comic-grid`）、`PageIndexGrid.vue`（`page-grid`）与 `ChapterIndex.vue`（`chapter-grid`）等长列表的 `<TransitionGroup>` 彻底替换为标准 `<div>`，切断 Vue 运行时对所有子节点的 `getBoundingClientRect` 与 `getComputedStyle` 密集轮询，主线程 JS 阻塞直接彻底归零（0ms）；
    2. **纯现代 CSS `@starting-style`（Baseline 2024）接管入场**：卡片与画页挂载补间分别由 `ComicCard.vue`、`PageTile.vue` 与 `ChapterCard.vue` 内部的原生 CSS `@starting-style` 接管，动画由浏览器 GPU 合成器线程处理；离场节点直接随 VDOM 卸载即时重排，利落无拖沓；
    3. **性能门禁全域守护**：在 `scripts/detect-perf.mjs` 中接入 `[transition-group-in-dynamic-lists]` 静态拦截规则，杜绝向书架网格、画页列表及章节目录重新引入 `<TransitionGroup>`；
    4. **实测收益（Chrome DevTools MCP 验证）**：切换筛选与展开长列表时的 `ForcedReflow` 耗时从 30~168ms 彻底降为 0ms，Performance Insights 面板中 Forced Reflow 警告彻底消除，全站列表达成满帧 120 FPS 原生丝滑。

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

### 85. 条漫连续模式终页高度不足致物理触底失效、流卷停靠态竞态循环与动晕症陷阱 (Webtoon Short Last-Page Clamping Failure, Continuous Stream Deprecation & Cybersickness Trap)

- **本质**：
  1. **短终页几何对齐落空（Short Last-Page Distance Trap）**：在竖向连续（条漫）模式下，原分屏吸附算法通过计算 `Math.abs(spread.offsetTop - scrollTop)` 确定最临近画页。当整话最后一页物理高度小于浏览器视口高度时（例如终页高度 584px，视口高度 900px），滚动容器在完全触底（`scrollTop === scrollHeight - clientHeight`）时，最后一页顶边仍处于视口中下部，`scrollTop` 永远无法触达该页的 `offsetTop`。算法在距离判定上始终将倒数第二页判定为“最近页”，导致页码永远卡在 `N-1 / N`（例如 `160 / 161`），底层 `atChapterEnd` 永远无法激活，下一话跳转横幅彻底丢失；
  2. **匀速流卷动晕症与机械自动化冲突（Continuous Stream Cybersickness Anti-pattern）**：在条漫长卷中曾尝试基于 `requestAnimationFrame` 驱动视口以设定速度匀速流卷推进。由于条漫分镜高度与信息密度极其非均质，匀速移动破坏了注视锚点，诱发视觉-前庭感官冲突与严重动晕症（头晕恶心）。条漫模式已彻底废弃流卷与机械自动化，将节奏 100% 交还给读者的手势/滚轮；
  3. **行内章末过渡卡片（In-flow Chapter Transition）**：条漫模式下废除遮挡分镜画面的悬浮下一话横幅，改在画卷尾部自然内嵌流式章末卡片（`.reader-webtoon-chapter-end`），末页整张画卷完整入目。
- **红线与防误伤**：
  - **不要**在连续滚动模式下仅依赖页面顶边到视口顶端的绝对距离判定当前页；
  - **不要**在条漫（竖向连续）模式下引入任何持续线性位移或机械定时，防止动晕症与失控感；
  - **放行/改用**：
    1. **绝对触底夹紧与 40% 视口阅读线几何相交（Bottom Clamping & Read-Line Intersection）**：当滚动容器距离底端 `position >= max - 24` 时，确定性将当前组索引钳制为 `lastGroupIndex`，彻底根治短终页无法翻至最后一页与无下一话按钮问题；非极端边界采用视口高度上方 40% 有效阅读线与画页几何相交探测；
    2. **自动翻页专精离散翻页**：自动翻页（Auto-turn）严格限定在横向/竖向离散翻页模式下运行，在静止阅读期 100% 绝对静止，条漫长卷彻底豁免自动化。

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
  3. **动态视口相对阈值（Dynamic Viewport Ratio Clamp）**：大跨度跳转门禁采用 `pageSize * 0.5`（或横向/纵向容器尺寸的半屏跨度），自适应单页、双页及任意分辨率设备；
  4. **局部双向候选集拓宽（±2 Bidirectional Probe）**：邻域探测拓宽为 `[cur, cur + 1, cur - 1, cur + 2, cur - 2]`，99.9% 覆盖快速翻页场景，二分查找触发率降至 0.01%。

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

### 93. 轮询状态提前覆写与任务终止反馈静默吞没陷阱（Polling State Premature Overwrite & Toast Swallowing Trap）

- **本质**：
  在基于定时器的长任务轮询器（如画页预缓存、后台下载）中，需要在任务自然终止瞬间（`job.running === false`）触发用户感知 Toast 或完成回调。若在轮询回调顶部过早执行 `caching.value = job.running` 覆盖自身响应式状态，随后在计算终止分支时去读取 `const wasCaching = caching.value`，此时读到的已是被提前覆写的 `false`；导致 `if (wasCaching)` 分支永远无法进入，使得原本精心设计的「单批次就绪/重试引导/错误告警」Toast 提示全线失效，造成静默中断与认知断层。
- **红线与防误伤**：
  - **不要**在判断任务终态前提前将服务端 `job.running` 赋值给本地记录上一次状态的 Ref；
  - **放行/改用**：
    在更新本地 `caching.value = job.running` 之前，先捕获上一刻的状态快照 `const wasCaching = caching.value`；或者由状态机明确记录状态迁移事件（`RUNNING -> IDLE`），确保完成反馈可靠投递。

### 94. 组合式函数双向依赖与临时 Ref 拆分身份陷阱（Circular Composable Dependency & Split Identity Trap）

- **本质**：
  在视图层编排多个业务 Composable（如 `useComicDetail` 与 `useChapterCache`）时，若 Composable A 需要 Composable B 产生的状态（如 `detail`），而 Composable B 初始化参数又需要 Composable A 的回调（如 `syncJobState`），容易诱使开发者在视图中先声明一个临时的 `const detailRef = ref(null)` 传入 A，随后调用 B，再通过 `watch(detail, val => { detailRef.value = val })` 反向同步。这造成单一实体分裂为两个 Ref 镜像（Split Identity），在组件内产生竞态双写开销，并可能在回调中触发 TDZ 引用错误（在 `const` 声明前引用变量），同时严重膨胀视图代码突破 ≤150 行门禁。
- **红线与防误伤**：
  - **不要**在 `<script setup>` 中为了避让组合式函数的初始化次序而创建桥接用的中间 Ref 和同步 watch；
  - **放行/改用**：
    优先按单向数据流拓扑序初始化数据源 Composable（如 `useComicDetail`），并将返回的原生 Ref 直接传参给消费方；对于相互依赖的回调方法，采用轻量局部委托函数（如 `let syncJobStateDelegate: ((job) => void) | undefined`）在下方延迟挂接，彻底消除冗余状态与响应式双写。

### 95. 复合画卷重新装订与缩略图粗暴失效陷阱（Composite Re-binding & Indiscriminate Thumbnail Invalidation Trap）

- **本质**：
  1. **单话靶向装订误删全本缩略图**：此前单话替换逻辑中直接执行 `shutil.rmtree(thumbs_dir)` 与 `covers_dir`，导致整本数十个章节的上百张缩略图瞬间全部失效，破坏了未改动章节的缓存连续性；
  2. **手工装订漫画被远端刷新冲垮**：用户为停更漫画手工补录画页后，若无 `custom_pages: true` 保护与远端刷新拦截门禁，后台或用户误点「刷新资料」会导致远端旧章节全量重刷覆盖本地手工编排；
  3. **单目录平铺图片丢失章节分界**：下载的复合文件名资源（如 `1-1.avif`, `2-1.avif`）若按单文件扁平处理，会抹去所有章节边界并退化为单话平铺。
- **红线与防误伤**：
  - **不要**在单话重新装订或局部更新时无差别清空整本缩略图/封面目录；
  - **不要**允许远端 Provider 刷新覆盖带有 `custom_pages: true` 的漫画；
  - **放行/改用**：
    1. **靶向失效（Scoped Invalidation）**：仅清理目标话目录下的 WebP 缩略图（`thumbs_dir / _safe(target_chapter)`），其他话缩略图保持缓存秒开；仅当目标章节起始页落在前 4 页时局部刷新封面；
    2. **纵深防御（Defense-in-Depth Protection）**：前端检测 `customPages: true` 时自动隐匿「刷新资料」按钮，API 路由层拦截阻断带 `refresh: true` 的请求（400 友好报错），底层存储合并兜底强制保留本地章节结构；
    3. **复合分话智能聚类（Pattern Auto-Grouping）**：使用复合命名正则自动聚类切分多章节并自然序单调重排，在全量替换时智能继承已有章节标题。

### 96. CSS 变量虚假防御与属性过渡反模式陷阱（CSS Token False Defense & Transition Shorthand Trap）

- **本质**：
  1. **组件层局部 Fallback 虚假防御（False Defensive Fallbacks）**：在单源设计系统（`tokens.css`）已全局静态载入的应用中，开发者在组件内部大量书写 `var(--accent, #b34a36)`、`var(--space-1, 0.25rem)` 等回退值。这不仅没有起到防御作用，反而会静默掩盖变量名拼写错误（Silent Failure），并导致设计系统 Token 演进时由于局部写死硬编码而引发严重的颜色与间距漂移；
  2. **渐变背景滥用 `transition: background` 简写（Broken Gradient Interpolation）**：CSS 规范中线性/径向渐变归属于 `<image>` 类型，标准 CSS 引擎无法在两个不同的渐变图片之间直接进行平滑补间插值。写 `transition: background 0.2s` 会在 hover 时产生生硬闪烁（snap/flicker），且纯色背景使用简写会强制浏览器每帧计算 8 个长写子属性，引发合成器无谓重排；
  3. **散落组件重复手写基础动画（Duplicate Keyframes Bloat）**：在多个组件中各自手写私有的 `@keyframes spin` 或 `@keyframes shimmer`，不仅增加 CSS 打包体积，还可能引发 SFC scoped 样式的同名 keyframes 命名空间污染。
- **红线与防误伤**：
  - **不要**在组件内部编写非动态注入变量的硬编码 Hex / 像素 Fallback（如 `var(--accent, #b34a36)`）；
  - **不要**对渐变背景使用传统的 `transition: background`，也不要在纯色背景过渡中使用简写；
  - **不要**在业务组件内重复声明 `@keyframes spin` 等通用基础动画；
  - **放行/改用**：
    1. **静态令牌 100% 裸用与单源收敛**：除动态内联注入样式（如 `var(--mask-left, 0px)`）外，所有静态令牌严禁编写局部 fallback；全站除 `tokens.css` 声明文件外，组件样式达到 **0 Hex 残留**；
    2. **纯色过渡长写与渐变动画 `@property` 插值**：纯色背景明确声明 `transition: background-color`；渐变背景动效通过 `@property` 注册类型化自定义属性（`<percentage>`、`<color>`），交由 GPU 合成器进行平滑数学插值；

### 97. Vue 3.6 Vapor Mode 虚树假设与私有原语反模式陷阱（Vapor Mode VNode Assumption & Private Primitives Trap）

- **本质**：
  1. **虚拟节点假定失真（VNode Access Trap）**：在组件内调用 `getCurrentInstance()?.vnode` 或读取 `vnode.props`、`vnode.el`。在 Vapor 模式下，组件编译直接生成原生 DOM 节点和微粒响应式 Effect，**根本不存在虚拟 DOM 树**，`instance.vnode` 恒为 `undefined`，任何直接读取其属性的操作均会抛出 `TypeError: Cannot read properties of undefined` 导致页面白屏崩溃；
  2. **样式绑定的机制差异（`<style> v-bind()` vs `:style`）**：在 Vapor SFC 中，若使用 `<style>` 内部的 `v-bind(expr)`，其依赖早期 VDOM 运行时的样式变量注入管线。在 Vapor 探针阶段，应优先使用显式 `:style="{ '--custom-var': expr }"` 动态注入 CSS 自定义属性，保障 100% 确定性；
  3. **复杂插槽与未适配组件混部陷阱（Complex Slot & Heavy Interop Trap）**：在 `<template vapor>` 叶子组件内若盲目嵌套依赖复杂作用域插槽（Scoped Slots）或 VDOM 专属特性的深层第三方组件，会触发跨模式桥接开销甚至插槽上下文丢失；
  4. **高密度 Vapor 叶子节点滥用 `<RouterLink>` 桥接陷阱（RouterLink VDOM-in-Vapor Thrashing）**：`<RouterLink>` 为纯正的 VDOM 组件，内部深度依赖 `h()` 与插槽分发。在高密度（50~200+ 节点）展示切片或卡片内部嵌套 `<RouterLink>`，会迫使运行时构建数百个微型 VDOM Bridge 桥接容器，不仅彻底抹平了 Vapor 的模板克隆（`cloneNode`）红利并增加内存 GC 负担，还在单测环境下极易触发 `shapeFlag` 未定义报错；
  5. **全站无脑全量开启（Premature Full-Site Vaporization）**：在没有独立跑分沙盒与精准单测验证的情况下，在 `vite.config.ts` 中开启全局 `features: { vapor: true }`，会导致全站上百个组件的边界问题同时爆发，违背渐进增强原则。
- **红线与防误伤**：
  - **不要**在 Vapor 组件内部编写任何读取 `getCurrentInstance()?.vnode` 的代码；
  - **不要**在 Vapor 组件中依赖 SFC `<style>` 内的 `v-bind()`；
  - **不要**在高密度 `<template vapor>` 叶子展示组件内滥用 `<RouterLink>` 引入双模桥接损耗；
  - **不要**在 `vite.config.ts` 开启强制全局 Vapor（`features.vapor: true`）；
  - **放行/改用**：
    1. **局部探针渐进落地**：维持全站默认稳定 VDOM，仅在原子叶子组件上通过 `<template vapor>` 显式开启；
    2. **纯粹原生与零 VNode 编译**：Vapor 叶子组件优先采用纯原生 DOM 与 SVG 矢量，避免跨模式桥接开销；
    3. **原生 `<a>` 渐进路由代理（Zero-VDOM Progressive Navigation）**：采用 `<a :href="url" @click="handleClick">`，在事件处理中智能放行多按键修饰符（`metaKey`/`ctrlKey` 等原生多标签页打开），普通左键点击调用 `e.preventDefault()` 并由 `router.push()` 无刷新接管，既达成 100% 零 VNode 微粒直驱，又完整保全无障碍 (a11y) 与浏览器原生交互；
    4. **同构响应式底座**：100% 复用既有 `composables` 和 Pinia Store，状态层零分裂；
    5. **显式 CSS 变量注入**：统一通过 `:style="{ '--foo': bar }"` 与 CSS 变量通信。

### 98. Vue 3.6 RC 与 Vitest 双包危害与实例割裂陷阱（Vue 3.6 Dual-Package Hazard & Test-Utils Instance Isolation Trap）

- **本质**：
  1. **构建格式非对称（Asymmetric ESM/CJS Builds）**：Vue 3.6 RC 中的 `@vue/runtime-vapor` 仅发布了 ESM Bundler 产物（没有 CommonJS 构建）。而 Vitest 在 Node.js (JSDOM) 环境执行测试时，Node 模块导出匹配策略默认命中 `"node"` 条件，使得 `@vue/test-utils` 与 `@vue/*` 底层依赖默认以 CJS 方式加载；
  2. **跨模块实例割裂（Instance Isolation & currentInstance: null）**：若仅将 `vue` 别名重定向至独立打包的单文件（如 `vue.runtime-with-vapor.esm-browser.js`），而 `@vue/test-utils` 仍通过 CJS 运行时执行 `mount()`，会导致组件内的 `useSlots()`、`useTemplateRef()` 访问 ESM 上下文中的 `currentInstance`，其实例恒为 `null`，报 `TypeError: Cannot read properties of null (reading 'vapor')`；
  3. **pnpm 隔离拓扑下的别名寻址失效（Strict Non-Flat node_modules Resolution）**：在 pnpm 严格模式下，`@vue/shared`、`@vue/server-renderer` 等非顶层直接依赖并未扁平提升至根目录 `node_modules/@vue/`，写死相对路径别名必然导致构建/单测解析中断。
- **红线与防误伤**：
  - **不要**在 `vitest.config.ts` 中单独将 `vue` 别名指向独立的 `esm-browser.js` 浏览器单文件；
  - **不要**在 `vitest.config.ts` 中直接硬编码 `./node_modules/@vue/shared` 等假设扁平的相对物理路径；
  - **不要**在子模块 `package.json` 中分散硬编码每个具体 RC 小版本号（如 `3.6.0-rc.7`）；
  - **放行/改用**：
    1. **全链路 ESM Bundler 单例收敛**：在 `vitest.config.ts` 中，通过 `createRequire` 从已解析的 `vue` 和 `@vue/test-utils` 根部动态解析 `@vue/test-utils/dist/vue-test-utils.esm-bundler.mjs` 以及各 `@vue/*` 的 `dist/*.esm-bundler.js`，确保测试用例、测试工具库与组件运行在完全一致的单一模块实例上下文内；
    2. **pnpm Catalog 统筹版本治理**：在 `pnpm-workspace.yaml` 中定义 `catalog.default.vue: rc` 并在 `overrides` 中将 `@vue/*` 衍生包全量锁定到统一的 `'rc'` 标签，主应用 `package.json` 统一使用 `"vue": "catalog:"`，升级时只需一条 `pnpm update` 或 `pnpm install` 自动从 npm 镜像对齐最新版。

### 99. 全局按键切话监听穿透、macOS 历史导航抢占与伪存活 Ref 声明陷阱（Global Keydown Interception, Modifier Hijacking & Dummy Void Trap）

- **本质**：
  1. **修饰键漏滤与 macOS 历史竞争（Modifier Hijacking & Dual Navigation Race）**：在页面级通过 `useEventListener('keydown')` 监听 `[` 与 `]` 切话时，若未严格过滤 `metaKey`/`ctrlKey`/`altKey`，由于 macOS 上 `Cmd + [` 为浏览器原生“后退”、`Cmd + ]` 为“前进”，Mac 用户尝试返回上一网页时会同时触发应用内切话，且因未调用 `e.preventDefault()` 造成底层原生 History 弹出与 Vue Router 推进的并发竞争，导致路由栈撕裂；
  2. **活动模态层与长按连发穿透（Modal Bleed & Keyrepeat Queue Flood）**：若未检测当前活动的对话框或菜单（`dialog[open], [role="dialog"], [role="menu"]`），读者在重命名、追加或重订画页弹窗中聚焦非输入区域敲击按键时，底层页面在用户无感知状态下跨话跳转；若未过滤 `e.repeat`，长按按键会高频狂发数十次切话请求造成导航队列拥堵；
  3. **Linter 模板 Ref 误报、伪存活代码与函数 Ref 滥用（Dummy Void & Inline Function Ref Anti-Pattern）**：早期在开启 `no-unused-vars` 校验时，由于通用 linter 无法直接穿透 Vue SFC 原生标签上的字符串属性 `ref="xxx"`，且旧版 Composable 尝试在自身内部直接创建 Ref 暴露给模板绑定，部分实现为了平息警告写出 `void dropZoneRef` 或内联赋值 `:ref="(el) => { dropZoneRef = el as HTMLElement }"` 等胶水代码。不仅污染了模板 AST，还破坏了 Composable 的声明式设计与单元测试沙箱解耦。
- **红线与防误伤**：
  - **不要**在任何页面级单键快捷键处理中遗漏 `e.metaKey || e.ctrlKey || e.altKey`；
  - **不要**在顶层存在活动的模态对话框或下拉浮层时放行背景路由导航快捷键；
  - **不要**在消费型组件中书写 `void <ref>` 等伪存活占位代码；
  - **不要**在单 DOM 节点或 Composable 驱动容器上使用 `:ref="(el) => ..."` 函数式内联赋值胶水；
  - **放行/改用**：
    1. **严格四重前置守卫**：先验 `if (e.repeat) return`，再验 `if (e.metaKey || e.ctrlKey || e.altKey) return`，三验 `if (document.querySelector('dialog[open], [role="dialog"], [role="menu"]')) return`，四验输入元素（`INPUT`/`TEXTAREA`/`SELECT`/`isContentEditable`），合法切话时显式 `e.preventDefault()`；
    2. **现代 Composable DOM 容器注入范式（Composable DOM Injection via useTemplateRef）**：宿主 DOM 元素统一在组件 `<script setup>` 顶层使用 Vue 3.5 `useTemplateRef<HTMLElement>('dropZoneEl')` 声明，模板直接使用原生静态 `ref="dropZoneEl"` 绑定，再将其作为可选入参注入下游 Composable（如 `useFileStaging({ dropZoneRef: dropZoneEl })`、`useLocalWorkshop({ dropAreaRef: dropAreaEl })`），彻底淘汰 `:ref="(el) => ..."` 胶水与 `void <ref>` 占位；
    3. **函数 Ref（:ref）全站单一合法场景**：全站仅保留在 `v-for` 循环中需要按业务动态 ID 进行字典寻址的场景（如 `ChapterSwitcher.vue` 中的 `:ref="(el) => (buttonEls[chapter.id] = el as HTMLElement | null)"`）。在此场景下，由于元素需要被 O(1) 按章节 ID 检索居中定位，使用字典型函数 Ref 是 Vue 官方推荐且唯一的规范范式（详见 Vue 官方文档 Template Refs on v-for）；其他所有确定节点必须 100% 收敛为 `useTemplateRef`；
    4. **双轨分工检查**：`vite.config.ts` 对 `*.vue` 单独关闭 `no-unused-vars`，由开启了 `noUnusedLocals` 的 `pnpm type-check`（`vue-tsc --build`）全权负责 Vue 模板的严格未引用检查。

### 100. 本地路径导入与长耗时 RPC 一刀切短超时引发的时序撕裂与 I/O 阻塞陷阱（Split-Horizon Timeout & Heavy File Copy Stall）

- **本质**：
  1. **一刀切 15s 前端超时与重型 I/O 的时序撕裂（Split-Horizon Abortion）**：在防范 Socket 泄漏时，若全站无差别设置 15s 超时，面对服务器/NAS 本地目录导入（数百上千张图片）、全书重新装订等操作，由于服务端仍在同步遍历磁盘复制或生成各章节封面，前端在第 15 秒精准触发 `TimeoutError` 弹红提示失败；而服务端 Python 线程在后台默默将整本收录入库，造成「界面提示失败但刷新后已存在」的严重用户体验认知割裂；
  2. **跨卷/同卷磁盘物理全量拷贝冗余（Physical Duplicate Copy vs Hardlink）**：在同一 NAS/主机文件系统下，使用 `shutil.copy2` 无谓地将几百兆至数千兆数据重新写入磁盘，不仅耗时长达数十秒，还浪费宝贵的磁盘存储空间；
  3. **多话封面同步转码阻塞主请求（Synchronous Pillow CPU Bottleneck）**：在本地导入主请求中，若同步对几十个章节的第一页逐一解码并生成 WebP 缩略图，CPU 密集型计算直接卡死 HTTP 响应。
- **红线与防误伤**：
  - **不要**简单粗暴地将全站所有 API 请求超时调长为几分钟（破坏普通短请求的快速失败能力）；
  - **不要**在本地路径导入中对所有文件无差别执行物理全量复制；
  - **不要**在同步导入请求中连续生成全量多章节的封面图片；
  - **放行/改用**：
    1. **分级超时契约（Per-Request Timeout Override）**：轻量 API 继续维持 15s 快速失败基线，重型操作（`importLocalPath`、`replaceComicPagesFromPath`、`uploadPages`）显式放宽至 60s~120s；
    2. **同卷零拷贝硬链接（Zero-Copy Hardlink with Fallback）**：优先通过 `os.link` 创建硬链接（微秒级瞬时完成且不占额外空间），若遇到跨设备/跨挂载点（`EXDEV`）自动回退至 `shutil.copy2`；
    3. **主封面同步 + 章节封面异步分阶就绪**：首图主封面同步秒级生成供书架展示，多话章节封面交由后台守护线程异步转码，彻底解放 HTTP 同步响应。

### 101. 单测全量 Mock 模块导出缺失与 Pinia 上下文隔离陷阱（Vitest Mock Destructuring & Isolated Store Context Trap）

- **本质**：
  1. **全量 Mock 覆盖破坏导出完整性（Module Export Obliteration）**：在单测中使用 `vi.mock('vue-router', () => ({ ... }))` 进行简单对象替换时，会覆写该模块的所有原生导出（如 `createRouter`, `createWebHistory` 等）。当下游 composable 或 store 间接引入 `@/router` 时，触发 `No "createRouter" export is defined on the "vue-router" mock` 导致整个测试套件执行中断；
  2. **Composable 隐式 Store 依赖缺少激活 Pinia（Missing Active Pinia in Composable Testing）**：在对依赖 Store 的 Composable 执行单测时，若未在 `beforeEach` 中调用 `setActivePinia(createPinia())`，会抛出 `[🍍]: "getActivePinia()" was called but there was no active Pinia`。
- **红线与防误伤**：
  - **不要**在 `vi.mock('vue-router')` 等第三方核心模块时使用简单的无透传工厂函数；
  - **不要**在涉及 Composable/Store 组合测试时遗漏 Pinia 实例激活；
  - **放行/改用**：
    1. **`importOriginal` 局部透传 Mock 范式**：所有对第三方库的 `vi.mock` 必须采用 `async (importOriginal) => { const actual = await importOriginal<...>(); return { ...actual, ... } }`，严格保全未经 mock 的底层方法与工厂函数；
    2. **标准 Pinia 单测沙箱隔离**：测试文件头部引入 `createPinia, setActivePinia`，并在 `beforeEach` 内执行 `setActivePinia(createPinia())` 为每个测试用例分配干净独立的状态沙箱。

### 102. 源代码内嵌巨型多字节字符字面量致 IDE/LSP 卡死与静态数据解耦陷阱 (Giant Raw String Literals in Code, IDE/LSP Freeze & Asset Decoupling Trap)

- **本质**：
  1. **巨型单行字面量冲垮编辑器语法高亮与 AST 词法分析（IDE / LSP Freeze）**：在 Python 或 JS 脚本中直接内嵌数千甚至上万字符的超长单行字符串字面量（如提取自 OpenCC 的 3,881 对 CJK 简繁映射表），且包含大量多字节 Unicode 与 SMP 扩展区汉字（如 `𠗣`, `𡞵`, `𡠹`）。当开发者在 VS Code、Cursor、PyCharm 或 Zed 等现代编辑器中打开该文件时，Tree-sitter 语法着色引擎、Language Server (Pyright/Pylance) 与软换行排版管线在解析巨型 Token 时遭遇极端性能瓶颈，导致编辑器主界面直接假死或无响应；
  2. **模块顶层即时构建拖慢无关模块启动（Eager Init Overhead）**：若在模块 import 顶层无条件执行 `str.maketrans` 解析数千映射对，使得仅仅 import `app.db` 或执行轻量单元测试时也要为未被调用的简繁模块付出额外的 CPU 与内存开销；
  3. **并发调用下的惰性初始化竞态（Lazy Init Data Race）**：若为了解耦改为惰性加载但未加互斥锁，多工作线程在服务冷启动并发调用时可能产生重复解压与字典赋值竞态。
- **红线与防误伤**：
  - **不要**在任何 Python/TS 代码源文件中直接内嵌数千字符以上的静态数据字典或超长字符字面量；
  - **不要**在模块导入期（Top-level）对未使用的重型映射表执行急切初始化；
  - **放行/改用**：
    1. **静态数据物理解耦（Binary Asset Decoupling）**：将静态映射数据按紧凑格式（如 UTF-8 变长序列 + zlib 压缩）持久化于独立的伴生资产文件（如 `backend/app/assets/zh_tables.dat`），使 Python 代码保持为纯净的轻量高内聚函数（≤60 行），IDE 打开秒开；
    2. **线程安全惰性单例（Thread-Safe Lazy Singleton）**：采用 `threading.Lock()` + 双重检查锁定（Double-Checked Locking）在首次调用时按需解压并构建 `str.maketrans` 转换表，兼顾 0ms 模块导入开销与高并发安全；
    3. **自解释轻量单测覆盖**：在 `backend/tests/test_zh_conv.py` 中对 SMP 四字节字、去重变体及多线程并发进行全面断言，保障 100% 健壮性。

### 103. 模块拆分动态反射、Mixin MRO 遮蔽与非原子性写入时序陷阱（Dynamic Reflection Anti-Pattern, Mixin MRO Shadowing & Premature Deletion Trap）

- **本质**：
  1. **动态反射逃逸与隐式调用断层（`sys.modules.get` Anti-Pattern）**：在拆分巨石文件（如 `main.py` / `storage.py`）后，为了规避直接依赖，在业务路由或预取逻辑中使用 `sys.modules.get("app.main")` 或 `getattr(store, ...)` 动态嗅探单例对象。此举彻底击穿了 Python 静态类型分析与 IDE 符号追踪，且在单独运行局部单元测试（未导入 `main.py`）时导致全局事件广播与单例方法静默失败；
  2. **多继承 MRO 与 Fallback 桩方法遮蔽（Mixin MRO Shadowing）**：在 `ComicStore(ComicStoreBase, Mixin1, Mixin2, ...)` 继承体系中，若在 `ComicStoreBase` 中定义了显式 fallback 桩方法（用于静态类型提示与接口契约声明），由于 `ComicStoreBase` 在 MRO 顺序中排在 Mixin 之前，Python 方法解析会优先命中 Base 桩方法（抛出 `NotImplementedError`），使具体 Mixin 中的实际实现被彻底遮蔽；
  3. **非原子写入与时序颠倒导致数据永久灭失（Premature Deletion before Disk Swap）**：在执行漫画画页全量替换等复杂操作时，若在写入磁盘前提前调用 `delete_comic_dialogues` 清理旧台词全文索引，一旦后续物理写盘或文件校验失败抛出异常，不仅新画页未能成功入库，旧台词索引也已被不可逆删除，破坏了事务的故障安全（Crash-Safe）不变量；
  4. **直连公网反代头伪造绕过防护（Header Spoofing & Forwarded Trust Gap）**：在解析客户端真实 IP 时，若无条件信任 `X-Forwarded-For` 请求头，在直接暴露端口（未经正向代理）环境下，攻击者可伪造标头绕过登录防爆破与双重限流熔断。
- **红线与防误伤**：
  - **不要**在生产路由与存储逻辑中使用 `sys.modules.get(...)` 动态反射主应用符号；
  - **不要**在多继承组合类中将提供 Fallback 桩方法的基类置于具体业务 Mixin 之前；
  - **不要**在文件系统写入成功且元数据原子落盘之前提前删除关联数据库记录；
  - **不要**在直连/未配置受信任代理时无条件信任外部 `X-Forwarded-For` 请求头；
  - **放行/改用**：
    1. **显式依赖注入与直接服务调用**：通过直接导入已解耦的 `app.routers.common.get_store` 与 `app.events.broadcast_system_event`，彻底消除动态反射；
    2. **标准 MRO 继承顺序**：声明为 `class ComicStore(*Mixins, ComicStoreBase)`，并在 Base 中显式声明所有方法签名与抽象契约，既保全 IDE/类型检查，又确保 Mixin 实现正确覆写；
    3. **写入成功后原子清理（Write-Then-Delete）**：将关联索引与派生资产的物理/数据库删除操作严格延后至 `store.replace_pages` 写入成功之后，确保任意环节失败时数据 100% 可回滚；
    4. **代理头受信任门禁（Trusted Forwarded Proxy Gate）**：引入 `TRUST_FORWARDED_HEADERS` 配置（默认 `True`），在直连或私有部署时支持置为 `False` 并严格回退读取 `request.client.host` 物理底层套接字。

### 104. CSS Token 标尺断层、Undefined 变量静默回退与层叠上下文遮挡反模式（Undefined Z-Index Token Decay, Stacking Context Occlusion & Dropdown Piercing Trap）

- **本质**：
  1. **CSS 变量未定义导致层级静默坍塌（Undefined CSS Variable Fallback to Auto）**：组件在绝对定位浮层声明 `z-index: var(--z-dropdown);`，若全局 `tokens.css` 缺失 `--z-dropdown` 声明，浏览器将该属性解析为 invalid/unset 并静默回退至 `z-index: auto`，不报任何编译错误或运行时异常；
  2. **后续 DOM 节点层叠上下文物理覆盖（Later Stacking Context Overlap）**：书架头部（`.shelf-head` / `.search-container`）在 DOM 树中位于 `TagFilterBar` 与 `ComicGrid` 之前。当下方的 `ComicCard` 包含 `contain: layout style`、`transform` 动画及内部角标印章（`z-index: 2`）时，根据 CSS 规范，DOM 顺序靠后的独立层叠上下文将直接绘制在 `z-index: auto` 的前方兄弟节点之上，导致搜索选单或自动补全浮层被下方的卡片封面硬生生切断遮挡。
- **红线与防误伤**：
  - **不要**在组件内部使用未在 `src/styles/tokens.css` 注册的伪 CSS Token；
  - **不要**将承载绝对定位下拉浮层的父级容器（如 `.shelf-head` / `.search-container`）置于未显式声明 `z-index` 的扁平层级中；
- **放行/改用**：
  1. **全局 Z-Index 标尺集中注册（Elevation Tokenization）**：在 `tokens.css` 固化 `--z-dropdown: 35`、`--z-header: 40`、`--z-popover: 60`、`--z-modal: 90` 等单一语义源；
  2. **搜索头部容器显式层级提升（Stacking Context Elevation）**：在 `.shelf-head` 与 `.search-container` 挂载 `position: relative; z-index: var(--z-dropdown);`，确保浮层整体平稳浮于下方标签栏与卡片网格之上，且位于全站顶栏（`--z-header: 40`）下方。

### 107. Starlette StaticFiles 与 FastAPI HTTPException 继承断层导致 SPA Fallback 穿透失灵（StaticFiles HTTPException Inheritance Mismatch & Mock Divergence Trap）

- **本质**：
  1. **FastAPI 与 Starlette 异常继承倒置导致无法捕获（Exception Subclass Catch Miss）**：FastAPI 的 `fastapi.exceptions.HTTPException` 是 Starlette 的 `starlette.exceptions.HTTPException` 的子类。Starlette 底层的 `StaticFiles.get_response` 在找不到文件时抛出的是父类 `starlette.exceptions.HTTPException`。若自定义 `SPAStaticFiles` 在 `get_response` 中使用 `except HTTPException:` 且顶部从 `fastapi` 导入，Python 异常匹配机制会直接跳过该捕获块，导致 404 异常穿透逃逸至全局异常处理器，将本应回退返回 `index.html` 的前端路由（如 `/comic/:source/:id`、`/discovery`）直接以 JSON 404 错误返回；
  2. **单测私造 Mock 掩盖真机故障（Unit Test Mock Divergence）**：单测文件在自身脚本内部重新定义了一份 `SPAStaticFiles` 且在单测内部使用了 `from starlette.exceptions import HTTPException`，仅测试了单测局部的 Mock 类，未直接引入应用真实挂载的 `main.py:app` 与类定义，造成单测全绿但真机 Docker / NAS 部署一刷新就 404 的假绿现象；
  3. **静态目录硬编码层级断裂（Static Dir Path Clamping）**：容器化（`/app/dist`）与本地开发（`<root>/dist`）环境下的相对路径层级不同，若仅依赖固定层级的 `parents[2]` 且环境变量未传时，可能引发静态文件根目录脱靶。
- **红线与防误伤**：
  - **不要**在继承或扩展 Starlette `StaticFiles` 时仅捕获 `fastapi.HTTPException`；
  - **不要**在单测中复制粘贴业务类重新定义 Mock 进行虚假验证；
  - **不要**对运行时静态文件路径采用单一硬编码 `parents` 解析；
- **放行/改用**：
  1. **联合捕获 Starlette 与 FastAPI 异常（Dual-Exception Catching）**：引入 `from starlette.exceptions import HTTPException as StarletteHTTPException`，使用 `except (HTTPException, StarletteHTTPException) as ex:` 彻底覆盖 404 拦截，确保非静态扩展名的请求稳定返回 `index.html`；
  2. **端到端真机真实 App 挂载单测**：单测直接引入 `from app.main import SPAStaticFiles, app as main_app`，直接对生产 ASGI 实例发送路由与静态文件请求并验证 HTTP 状态码与 Content-Type；
  3. **静态目录候选链自愈解析（Candidate Path Cascade）**：优先读取 `COMIC_SHELF_STATIC_DIR` 环境变量，自动在 monorepo 根目录 `../../dist`、容器目录 `../dist` 以及当前工作目录 `./dist` 之间智能探测就绪的 `index.html`。

### 108. 存储拆分重构中画页物理路径与全局页码合成脱靶致 502 穿透陷阱 (Storage Refactoring Page Path Synthesis vs. Physical Filename Desynchronization Trap)

- **本质**：
  1. **全局页码合成覆盖物理文件名（`page.file` Single Truth Decay）**：在拆分巨石存储层至模块化 Router 与 Storage Mixin 时，`store.page_path` 与 `store._chapter_page_path` 被错误重构为 `f"{index:05d}{ext}"` 动态合成。对于多章节漫画（如哔咔、JM 或本地多话），第 2 话以后的画页物理文件名保存在 `page.file` 中（如 `00001.webp`），而全局页码 `page.index` 为全局单调递增（如 15）。动态合成会寻址到不存在的 `00015.webp`，破坏了 `page.file` 的单一事实源；
  2. **替换漫画空远端协议触发下载异常并转为 502（Empty Remote URL Download Cascade）**：当 `page_path.exists()` 误判为 `False` 时，媒体流路由回退调用 `store.ensure_page`。对于全量重新装订的漫画（`custom_pages: true`），其 `remote_pages` 中的 `url` 为空字符串 `""`。Provider 解析空协议抛出 `ValueError`，媒体路由未捕获具体错误而是包装为 `502 Bad Gateway`，导致全本画页与缩略图大面积报错；
  3. **元数据自愈逆向标记本地缓存为未就绪（False Negative Cache Mark）**：`load_meta(verify_cache=True)` 与 `save_fetched` 在校验缓存时调用脱靶的 `_chapter_page_path`，将已完整落盘的图片误判为丢失，并将元数据中的 `page.cached` 反向刷为 `False`。
- **红线与防误伤**：
  - **不要**在 `page_path` 或 `_chapter_page_path` 中通过 `index` 猜测合成文件名，必须无条件读取 `page.file`；
  - **不要**在 `ensure_page` 中对 `not page.url` 的画页调用远端 Provider 下载；
  - **不要**在媒体路由中将本地文件缺失或空 URL 抛出为 502，必须返回 404；
- **放行/改用**：
  1. **物理文件名单源寻址**：`_chapter_page_path(meta, page)` 严格寻址 `pages_dir / safe(page.chapter) / page.file`（或平铺 `pages_dir / page.file`），仅在 `page` 缺失时降级；
  2. **本地自定义画页缺失防御门禁**：在 `ensure_page` 内部显式拦截 `if not page.url: raise FileNotFoundError(...)`，路由层捕获 `(FileNotFoundError, KeyError)` 并返回 `HTTP 404 Not Found`；
  3. **无损自愈对齐**：修复路径解析后，`load_meta(verify_cache=True)` 在下一次读取时即可自动将磁盘真实存在的图片纠偏为 `page.cached = True`，存量 `album.json` 与 `remote.json` 结构完整无损，无需重新装订或重新导入。

### 109. 超长画卷离屏毛玻璃与无限动画引发合成雪崩及翻页页码自激震荡陷阱 (High-Volume Offscreen Backdrop-Filter Reflow Storm & Reader Programmatic Scroll Feedback Loop)

- **本质**：
  1. **离屏重型装饰引发合成雪崩（Offscreen Backdrop-Filter & Animation Stampede）**：在单卷达到 1000~2000 页的超长画卷（如拆帧漫或长条漫）中，若画页加载骨架（`ReaderLoadingState`）无差别使用 `backdrop-filter: blur(14px)`、`loading="eager"` 伴生插画以及包含 `loading-breathe` / `shimmer` 无限循环 CSS 动画，即使配合 `content-visibility: auto`，浏览器主线程与 GPU 合成器管线也会被迫同时维护数千个高开销图形图层与动画时间轴，在高速滚动时发生严重的掉帧、显卡风扇狂转与移动端 OOM 崩溃；
  2. **粗暴卸载式虚拟滚动的深水区反噬（Naive Virtualizer Feedback Traps）**：为了降低 DOM 内存曾尝试激进卸载离屏画页，引发三重严重退化：① 快速划动直接白屏（DOM 插入与图片重解码排队滞后）；② 条漫未知高度异步测绘引起 `scrollHeight` 突变，滚动微移触发 `@scroll` 监听器反向误判页码，形成自激震荡死锁（点击翻页页码来回跳动抽搐）；③ 彻底破坏外部「继续阅读」直达、按页码跳卷以及台词全文检索气泡（`BreathingBubbleOverlay`）的 DOM 挂载锚点；
  3. **主动跳转与被动滚动监听缺少互斥隔离（Missing Programmatic Scroll Silence Lock）**：在调用 `scrollToGroup` 平滑滚动时，沿途路过的中间画页不断触发容器 `@scroll`，被动监听算法将中间经过的画页误判为读者目标并反向覆盖 `currentGroupIndex` 与 `currentPage`，导致滑行途中页码不断闪烁并可能反弹回退。
- **红线与防误伤**：
  - **不要**在阅读器高频重复的画页占位与离屏状态中堆砌 `backdrop-filter` 复合滤镜与无限循环 CSS 动画；
  - **不要**在插画占位图上使用 `loading="eager"`；
  - **不要**在未解决动态高度锁死与锚点保留前对阅读器长卷引入侵入式组件卸载虚拟列表；
  - **不要**在程序化平滑滚动（`goToPage`/`goToGroup`）推进期间允许滚动监听器被动重写页码；
- **放行/改用**：
  1. **静默装订骨架（Quiescent Loading Placeholder）**：阅读器画页骨架采用极简静态暗色纸质混合背景（`color-mix`），全面剔除 `backdrop-filter` 与无限呼吸扫光动画，插画强制收敛为懒加载（`loading="lazy"`），挂载 `contain: layout style` 与 `contain: strict` 阻断局部重排；
  2. **程序化跳转静音锁与长跨度降级（Programmatic Scroll Silence Lock & Long-Distance Downgrade）**：在 `scrollToGroup` 触发主动位移时挂载 60ms~320ms 静音互斥锁，滚动期间放行进度条更新但严格阻断页码反向覆盖；超过 5 屏的长距离跳转自动降级为即时定位，并挂载原生 `scrollend` 事件与定时器双重释放保底；在读者触屏（`onUserInteract`）或滚轮（`onWheel`）干预时 0 毫秒即时解锁释放控制权；
  3. **宽高比固化防抖（Aspect-Ratio Latch）**：画页在首次解码测得真实物理尺寸后，将 `naturalRatio` 永久固化于外层包裹容器，消除后续视口进出或网络重试引起的几何形变与滚动条跳跃；
  4. **全量 DOM 容器常驻与迟滞注水视窗（Permanent DOM Shell with Hysteresis Hydration Window - `useReaderHydration.ts`）**：保持所有 900+ 最外层 `<section>` 与 `<article>` 在文档流中，永不物理删除以维持 `scrollHeight`、继续阅读定位与 DOM 锚点确定性；业务逻辑独立下沉至 `useReaderHydration.ts`，借助 VueUse 动态自适应设备与网络环境（弱网 5/10 屏、高 DPR 移动端 8/15 屏、桌面 15/30 屏）；离屏画页渲染纯 CSS `quiescent-paper` 静默纸框并由底层 `content-visibility: auto` 跳过排版绘制，形成**框架组件层（削减 97% 图片显存）+ 浏览器内核层（跳过离屏骨架绘制）的双层立体防御体系**，彻底根除自激震荡狂滚与控制台卡死。

### 110. 阅读器胶片预览轨局部切片全局索引脱靶与浏览器修饰键穿透陷阱 (Reader Filmstrip Scoped Hydration Desynchronization & Keyboard Modifier Shortcut Hijack)

- **本质**：
  1. **局部切片与全局分组索引脱靶致缩略图假死（Scoped Slice vs. Global Group Index Mismatch）**：在多章节漫画中，`scopedGroups` 过滤出当前章节的分组（保留全局 `group.index`，例如第 2 话为 `30..59`），而 `scopedCurrentGroupIndex` 计算的是局部数组索引（`0..29`）。传入 `useReaderHydration` 的滑动窗口基于局部索引运行（`minIdx: 0, maxIdx: 12`）。若在模板中误将全局 `group.index` 传入 `isGroupHydrated(group.index)`，当章节总组数超过全量注水阈值（24 组）时，所有全局序号 `30..59` 都会被误判为超出窗口（`30 > 12`），导致第 2 话及以后的缩略图全量脱靶瘫痪，永久停留在空白纸质骨架；
  2. **全局快捷键修饰键穿透劫持浏览器系统指令（Global Keydown Modifier Leakage）**：在顶层注册单键快捷操作（如 `s` 呼出胶片轨、`t` 缩略图、`f` 全屏、`n` 切话）时，若仅排除了表单 input 焦点而未严格校验 `event.ctrlKey || event.metaKey || event.altKey`，读者触发浏览器原生快捷键 `Ctrl+S`（保存网页）、`Ctrl+T`（新标签页）、`Ctrl+F`（页内查找）或 `Ctrl+N`（新建窗口）时，会被阅读器错误截获并触发界面跳变与全屏切换；
  3. **横向日漫 RTL 模式带符号负坐标轴居中死锁（Signed scrollLeft in dir="rtl"）**：现代浏览器（Chromium/WebKit/Gecko）在 `dir="rtl"` 滚动容器中遵循标准负坐标系规范，`scrollLeft` 取值范围为 `0` 至 `-(scrollWidth - clientWidth)`。使用常规 LTR 的 `Math.max(0, offsetLeft - ...)` 计算目标绝对坐标会强行传入正数，在 RTL 容器中被底层无情归零截断，导致横向日漫模式下任何居中滚动指令全线失效；
  4. **画中画异步跨页测绘尺寸竞态（Stale Decoded Geometry Race Condition）**：鼠标高速划过微缩单元格时，`props.page` 与图片 `src` 频繁切换。若在 `nextTick` 中仅校验 `img.complete && img.naturalWidth` 而未校验 `img.currentSrc === thumbUrl`，可能在浏览器网络层未完成新图重置前误读上一页的尺寸并错误上报当前页的宽高比。
- **红线与防误伤**：
  - **不要**将经过局部过滤切片的列表数组的全局属性直接传入依赖局部视窗滑动窗口的 `isGroupHydrated`，必须传入 `v-for="(group, gIdx)"` 的局部循环索引 `gIdx`；
  - **不要**在全局键盘监听器中遗漏修饰键拦截，严禁在 `ctrlKey / metaKey / altKey` 为 true 时分发单键业务动作；
  - **不要**在带有 `dir="rtl"` 属性的横向滚动容器上通过绝对正值 `Math.max(0, ...)` 进行定位；
  - **不要**在动态复用单体 `<img>` 的画中画浮层中读取未经 URL 校验的 `img.naturalWidth/Height`；
- **放行/改用**：
  1. **局部循环索引用作注水校验单源（Localized Loop Index Injection）**：模板统一书写 `<img v-if="isGroupHydrated(gIdx)" ...>`，使 `useReaderHydration` 内部的 `currentGroupIndex`、`orderedGroups` 与外部渲染完全保持局部坐标系统一；
  2. **修饰键前置阻断防线（Modifier Guard）**：在 `useReaderKeyboard` 的 `onKeydown` 顶层统一增加 `if (event.ctrlKey || event.metaKey || event.altKey) return` 守卫，与全站 `useChapterPageInfo` 规范统一；
  3. **物理中点物理差值相对滚动（Relative Midpoint Delta via scrollBy）**：通过 `targetRect.left + targetRect.width / 2 - (railRect.left + railRect.width / 2)` 测算物理视口中心偏差值 `delta`，调用 `rail.scrollBy({ left: delta })`，天然穿透 LTR 与 RTL 坐标轴正负极性差异；
  4. **画中画真实解码响应式撑高与 URL 防穿透（Self-healing Popover Aspect-Ratio）**：在 `ReaderHoverPreview` 声明局部 `loadedRatio` 驱动 `--hover-ratio`，并在 `checkImageComplete` 中增加 `(img.currentSrc === thumbUrl.value || img.src === thumbUrl.value)` 校验，确保几何定盘与尺寸上报 100% 幂等可靠。

### 111. 矮切片阅读线穿透反噬、离屏伪 100dvh 崩塌与异步撑高重排自激翻页风暴 (Short-Spread Reading Line Penetration, Phantom 100dvh Collapse & Async Reflow Stampede)

- **本质**：
  1. **矮切片/宽幅拆帧漫 40% 阅读线几何穿透反噬（Short-Spread Read-Line Overshoot）**：在 16:9 视频拆帧漫、四格漫或移动端矮画幅长卷（单页高度 $H \approx 205\text{px}$）中，若在竖向连续滚动探测中硬编码 `readLine = position + el.clientHeight * 0.4`（移动端 $844 \times 0.4 = 338\text{px}$）。当视口精确对齐第 K 页顶端（`position = top`）时，由于 $H < 338\text{px}$，阅读线瞬间越界穿透至第 K+1 页甚至第 K+2 页，导致被动滚动算法把位于视口顶部正中央、完全可视的第 K 页误判为已被读完，直接将 `currentGroupIndex` 强行推进至下一组；
  2. **连续长卷误用 `content-visibility: auto` 与伪 `100dvh` 内在尺寸造成 600px+ 巨幅雪崩塌陷（Phantom 100dvh Collapse）**：若在 `.reader-spread` 全局声明 `content-visibility: auto; contain-intrinsic-block-size: auto 100dvh;`，在翻页模式下单屏确实是 100dvh，但在竖向连续模式下，画页真实高度是由开本宽高比决定的（如移动端 16:9 画页仅 239px）。浏览器会将尚未入目的离屏画页全部伪造为 849px，产生高达数十万像素的"幽灵滚动条"。一旦读者向上翻卷接近上方画页，画页进入渲染视界并真实布局，单页瞬间从 849px 塌陷至 239px（-610px/页），引发全卷 `scrollHeight` 和 `offsetTop` 剧烈断层缩水，导致读者在第 13 页向上点到第 10 页时，上方画页塌陷使物理 `scrollTop` 相对位置暴涨，被误判为跌回第 13 页；
  3. **HUD/工具栏点击与画卷脱节导致初始锚点残留弹回（HUD Click Detachment & Target Anchor Leakage）**：为补偿冷启动直达深层页码时上方图片异步加载撑高而引入了 `targetAnchorGroupIndex`。若仅在画卷视口（`ReaderViewport`）内部监听 touch/pointer 事件，读者点击处于视口外部的底部 HUD（`ReaderHud`）中的"上一屏"按钮时，`userInteracted` 无法被置为 `true`，导致初始锚点（如第 13 页）持续常驻。一旦读者向上翻到第 10 页且第 10 页图片就绪，`onPageReady` 判定 $10 < 13$ 且用户未交互，立即触发 `recalibrateTargetOffset(12)` 强行把视口弹回第 13 页；
  4. **未注水纸印占位骨架 `min-height` 倒挂诱发 250px+ 巨额 CLS 震荡（Skeleton Min-Height Inversion）**：在 `.quiescent-paper` 中硬编码 `min-height: clamp(...)` 会在矮切片下覆盖 `aspect-ratio`，导致脱水骨架与真实画页尺寸倒挂；
  5. **平滑滚动途中微调任务抢占打断（Smooth Scroll Preemption）**：在 `goToGroup` / `goToPage` 平滑过渡中无条件即时快跳打断读者视觉；
  6. **详情缓存未利用与二次挂载虚拟 DOM 抖动（Uncached Deep Mount & Forced Reflow Thrashing）**：进入阅读器时若无条件重置 `loading = true`，即便已持有详情也会闪烁 100ms 骨架屏再挂载 900+ 节点画卷；且 `currentPage` 初始赋 1 导致异步 watch 触发二次虚拟 DOM 重渲染；多图并发就绪同步读取 `target.offsetTop` 产生 180ms+ Forced Reflow 阻塞。
- **红线与防误伤**：
  - **不要**在连续长卷滚动探测中采用超越画页本身几何高度的固定视口偏置阅读线；
  - **不要**在连续长卷模式（`vertical-continuous`）的画页容器上滥用 `content-visibility: auto` 与 `contain-intrinsic-block-size: 100dvh`；
  - **不要**将交互监听局限于单个子组件内部，必须确保任何控制台/HUD 导航行为均能清空初始微调锚点；
  - **不要**允许微调逻辑对非当前分屏（`groupIndex !== currentGroupIndex`）执行跳转；
  - **不要**在已有缓存数据正常渲染时，因后台 SWR 接口失败将读者粗暴踢出阅读器或重置阅读进度；
  - **不要**在多图并发加载回调中同步读取 DOM 几何属性诱发 Forced Reflow。
- **放行/改用**：
  1. **开本自适应有效阅读线（Adaptive Reading Line）**：`resolveNearestGroupIndex` 采用 `threshold = Math.min(el.clientHeight * 0.4, height * 0.5)`，高画卷保持 40% 重心线，矮画幅回退至 50% 中线；
  2. **连续长卷豁免 `content-visibility: auto`（Continuous Mode Layout Exemption）**：将 `content-visibility: auto; contain-intrinsic-block-size: auto 100dvh;` 严格收敛至单屏定高的 `vertical-paged` 与 `horizontal` 模式。在 `vertical-continuous` 模式下完全由已具备真实宽高比的轻量 `.quiescent-paper` 直接进行原生布局，全卷 900+ 节点尺寸首帧 100% 确定，0px CLS，0 幽灵高度；
  3. **交互驱动锚点终结与 4 秒自毁（User Interaction Anchor Teardown & 4s TTL）**：在 `useReaderInteraction` 对 `prevGroup`、`nextGroup`、`goToPage`、`goNextChapter` 等交互统一注入 `onUserInteract()`，彻底注销 `targetAnchorGroupIndex`；冷启动设置 4000ms 兜底自毁定时器；并在 `recalibrateTargetOffset` 中增加 `groupIndex === currentGroupIndex.value` 刚性守卫；
  4. **开本比例定盘零 CLS（Zero-CLS Ratio-Governed Placeholder）**：`.quiescent-paper` 释放 `min-height: 0`，由 `aspect-ratio` 百分之百主导高度；
  5. **内存缓存直出与后台 SWR 保活（Instant Memory Cache & SWR Resilience）**：`useReaderData` 挂载时优先同步命中 `store.getDetail`，`loading` 初值赋 `false` 零骨架闪烁直出；后台更新失败静默保活；
  6. **初值提级与 RAF 合批（Route Param Initialization & RAF Batching）**：`currentPage` 挂载前直接由路由提取初值，规避二次重渲染；`recalibrateTargetOffset` 通过 RAF 合批消抖并清理历史调度。

### 112. 领域断言契约错位、跨层反向类型依赖与工具投机性泛化陷阱 (Domain Contract Divergence, Inverted Worker Type Dependency & Speculative Generality Trap)

- **本质**：
  1. **领域多态契约假设与真实结构脱节（Domain Field Divergence）**：在为领域对象（如漫画）实现通用状态守卫（如 `isMultiChapterComic`）时，直觉假设输入形如 `{ chapters: [...] }`。但书架摘要 `LibrarySummary` 真实字段是 `chapter_titles?: string[]`，而漫画详情 `ComicDetail` 章节列表位于嵌套的 `meta.chapters?: Chapter[]`。若入参未做多态解包与字段嗅探，传入标准的领域对象时会静默永远返回 `false`，埋下高危隐蔽缺陷；
  2. **Worker 共享底层纯函数反向依赖上层 Composable（Inverted Dependency across Layers）**：`src/utils/libraryFilterCore.ts` 既是主线程也是后台 Web Worker（`libraryFilter.worker.ts`）的过滤/排序算法核心。若直接从上层 `@/composables/useLibraryFilter` 反向导入 `SortKey` 类型，导致底层纯算法与上层 Vue 响应式状态机逻辑产生倒置耦合，破坏依赖倒置（DIP）原则；
  3. **单源工具库与组件孤岛判定断层（Fragmented Predicates & Speculative Generality）**：建立基础断言库与高精代数工具（`src/utils/is.ts` 与 `src/utils/math.ts`）后，若未能将组件层（如 `ReaderView`、`AppProgressBar`、`ImportPanel`、`ComicGrid`）中散落的手写判定与冗余中转重导出（`export { formatBytes }`）彻底收敛，既产生工具死代码，又破坏了单一事实来源（Single Source of Truth）。
- **红线与防误伤**：
  - **不要**在通用工具函数中凭空假设领域对象结构，必须严格核对 `src/types/index.ts` 核心契约；
  - **不要**允许 `src/utils/` 中的底层纯函数模块反向引用 `src/composables/` 或 `src/views/` 的任何符号或类型；
  - **不要**在多个模块之间级联中转重导出领域断言或格式化工具，必须收敛至单一出口；
  - **不要**新建了高精/守卫工具库却在组件层继续保留手写 `typeof === 'number'` 或 `Math.round(val * factor) / factor`。
- **放行/改用**：
  1. **多态领域对象安全解包（Polymorphic Contract Unwrapping）**：在断言函数中通过 `'chapter_titles' in item` 与 `'meta' in item` 兼容 `LibrarySummary`、`ComicDetail` 及带通用章节数组的对象；
  2. **核心契约类型下沉（Type Contract Sinking）**：将跨层共享类型（如 `SortKey`）下沉至 `src/types/index.ts`，由工具层与组合式函数单向消费；
  3. **单一真理源收敛与彻底落地**：全站数值/源判定全面收敛至 `@/utils/is`、保留小数统一委托至 `round(val, decimals)`，并彻底拔除 Composable 层的冗余中转导出。

### 113. 网盘层级倒置、PDF 多卷归并断层与画卷删除全链路自愈陷阱 (Netdisk Folder Inversion, Multi-Volume PDF Ingest Gap & Cascading Deletion Self-Healing)

- **本质**：
  1. **网盘/多层级下载目录结构字符排序倒置反噬（Netdisk Folder Inversion）**：网盘下载资源常见三级松散目录（如根目录 `Y | 作品名/` 下包含 `番外/`、`后续更新/`、`台东立版1-7卷/`）。若直接按根目录粗暴递归扫描，字符自然排序导致 `番外`（拼音 F）与 `后续更新`（拼音 H）被排在 `台东立版1-7卷`（拼音 T）之前，导致阅读器首话直接呈现番外或剧透后续；最佳实践是收敛到单目录扁平化多卷命名（`01_第1卷.pdf` ~ `07_第7卷.pdf`）或先按正篇目录导入再通过详情页「追加页面」补充番外与更新；
  2. **多卷 PDF 目录探测中空子目录阻断陷阱（Empty Subdir Ingest Blocking）**：在扫描包含多卷 PDF 的目录时，若检测条件硬编码 `if pdf_files and not subdirs:`，一旦目录内存在空文件夹或非图片目录（如 `.cache/`、`temp/`、`notes/`），会导致合订 PDF 无法被命中并回退至未找到图片报错；
  3. **章节删除后全局页码与起始页未压实引发的断层悬挂（Dangling Chapter Page Indices）**：删除中间章节（如第 3 话）时，若仅物理删除其目录而未联动重排剩余章节的 `start` 与全书全局单调页码表（1..N），会导致全书页码断层、阅读器跨话翻页报错与封面缩略图映射错位。必须严格执行自愈单调重排与封面级联重算；
  4. **PDF 暂存解包目录孤儿泄漏与内存耗尽（Staging Isolation Leak & OOM Bomb）**：导入、追加或替换 PDF 时解压的临时目录必须在 `try...finally` 块中确保清理；大文件上传必须流式分块（1MB）落盘以防 OOM，且单本强制限制 `MAX_PDF_PAGES = 5000` 防止解压炸弹；
  5. **上传 PDF 追加/替换场景下分话探测传入目录而非文件路径陷阱（Directory Passed as PDF Path in Append/Replace）**：在 `append_pages` / `replace_pages` 接收前端上传的 `UploadFile` PDF 时，解包后若误将解压产物临时目录路径传给 `detect_pdf_chapters`（该函数期望输入的是 PDF 文件路径或 bytes，由 `pymupdf.open()` 打开），会因 `fitz.open(dir_path)` 抛异常并静默回退至单章节导入，破坏多话探测；必须在临时 PDF 文件（`tmp_pdf`）解压后但在 `os.unlink()` 删除前，将真实文件路径传入分话探测器；
  6. **无界 OCR 扫描引发 Cloudflare 524 超时与 DoS 拒绝服务陷阱（Unbounded OCR 524 Timeout）**：对于大体积（如 500-1000 页）且无内置目录书签（TOC）的合订本 PDF，若开启 RapidOCR 逐页探测章节，每页 OCR 耗时 200-500ms，整书将阻塞 2-5 分钟，瞬间击穿 Cloudflare 100s（HTTP 524 Gateway Timeout）或 Nginx 网关超时。必须设置扫描步长采样与探测硬上限（`MAX_OCR_SCAN_PAGES = 40`），并在 TOC 提取到 $\ge 2$ 章节时立即短路退出（Early Return），杜绝无意义的全本 OCR 慢速扫描；
  7. **客户端分话起始页偏移信任与全局单调页号脱节断层（Client Chapter Start Divergence）**：在暂存分步建卷（`create_from_staged_pdf`）与单本 PDF 自动切分（`_import_single_pdf`）中，若盲目信任前端提交或探测器返回的相对 `c_start`，在跨卷拼接或多次追加时会导致章节 `start` 与底层全局单调索引（`PageRecord.index = 1..N`）产生偏移，打破核心不变量 #3。后端必须以全局累计写盘指针 `chap_start_page = global_idx` 为唯一真理源强行绑定 `Chapter.start`；
  8. **暂存生成画卷非原子组装导致半拉子孤儿卷与并发竞态（Non-Atomic Staging Ingest & Concurrency Collision）**：在 `create_from_staged_pdf` 中，若直接向最终漫画目录逐页生成或未加锁，一旦中途失败（磁盘满、进程崩溃），会留下残缺的损坏漫画，且可能引发目录并发冲突。必须：(1) 对 `(source, comic_slug)` 加全局锁；(2) 先向 `.tmp_create_pages_<token>` 组装完整散图再通过 `_atomic_swap_dir` 原子重命名切换；(3) 校验 slug 碰撞并返回 409 Conflict；(4) FastAPI 服务冷启动时立即触发 `_cleanup_staged_pdfs(max_age_seconds=0)` 彻底清除宿主机断电遗留的残余暂存文件。
- **红线与防误伤**：
  - **不要**在存在多卷 PDF 的目录导入判定中仅因存在非图片子目录就直接抛弃 PDF 聚类；
  - **不要**在删除章节后保留跳跃断开的全局页号，全书 `PageRecord.index` 必须从 1 开始严格单调连续；
  - **不要**在未校验 `staging_token` 正则格式前进行路径拼接；
  - **不要**在文件解压过程中漏掉 `finally` 目录物理清除兜底；
  - **不要**将散图解压目录路径当作 PDF 文件传入 `detect_pdf_chapters`；
  - **不要**在无电子书签时全量逐页无界运行 OCR，必须限制步长与最大候选扫描页数（$\le 40$P）；
  - **不要**信任前端传入的 `c.start`，必须由后端全局写入索引 `global_idx` 强制兜底；
  - **不要**直接在宿主漫画目录中非原子性地逐张组装页面，必须隔离在临时目录并执行原子目录替换。
- **放行/改用**：
  1. **单目录扁平化多卷推荐最佳实践**：推荐将系列卷册整理在同一漫画目录下命名为 `01_第1卷.pdf`、`02_第2卷.pdf` ...，利用自然排序直接一次性批量映射为各章节；
  2. **非排他性 PDF 多卷探测**：当目录内存在 `pdf_files` 且无顶级散图及多图子目录时，放行并执行 `_import_multi_pdfs`；
  3. **单调页码连续自愈压实（Monotonic Page Re-indexing）**：`delete_chapter` 物理删除目录后，立即重构全书 `rebuilt_pages`（`1..page_count`）并同步调整各章 `start`；
  4. **五层纵深防御与 1 小时自动 TTL**：结合 32 位 hex 令牌、流式 1MB 上传、5000 页上限与 1 小时后台 TTL，彻底根除磁盘膨胀与解压炸弹；
  5. **先探测后清理暂存 PDF 路径**：在解包后、`unlink` 前将真实 `tmp_pdf` 传给分话探测器；
  6. **TOC 短路早退与 40P 步长采样**：若提取到 $\ge 2$ 个有效目录章节直接返回，否则只扫描前 40 页或隔页抽样；
  7. **后端权威指针锁定 `Chapter.start`**：无论前端传入何种 `c.start`，后端只认 `chap_start_page = global_idx`；
  8. **互斥锁 + 原子目录交换 + 冷启动清理保底**：`_lock_for("local", source_id)` 互斥保护，`.tmp_create_pages_*` 组装完毕后原子重命名切换，FastAPI lifespan 钩入 `_cleanup_staged_pdfs(max_age_seconds=0)`。

### 115. Vue 3 模板引用隐式解绑、双轨双向状态脱节与大体量对象深度代理风暴 (Template Ref Decoupling, DefineModel State Desync & ShallowRef Proxy Flooding)

- **本质**：
  1. **模板引用与变量命名隐式耦合（Template Ref String Coupling）**：旧式在 `<script setup>` 中写 `const el = ref<HTMLElement | null>(null)`，严格依赖变量名与模板中 `ref="el"` 的字符串匹配。在代码重构、重命名或在 Composable 间复用时极易断联，且类型无法向模板编译器强保障。解决之道：统一使用 Vue 3.5+ 原生 `useTemplateRef<T>('el')`，实现编译期强类型绑定与标识符解耦；
  2. **父子受控状态手写 `emit('update:xxx')` 与内部 `internalX` 镜像状态引发的双轨脱节（Dual-Track State Divergence）**：在封装具有开闭或受控状态的组件（如弹窗 `Modal`、浮层 `AppPopover`、抽屉 `ComicGrid`、标签栏 `TagFilterBar`）时，手工声明 `props.open` + `emit('update:open')` 并在组件内部维护 `internalOpen` 本地 ref 与双轨计算属性。当外部未传或异步赋值时，本地镜像与外部受控状态极易脱节，且消费层散落大量 `@update:active-count`、`@update:archive-open` 等胶水代码。解决之道：一律使用 Vue 3.4+ 原生 `defineModel`，一行宏声明兼顾受控（`v-model:name`）与非受控默认行为，全站彻底拔除 `@update:xxx` 胶水；
  3. **单测中 `wrapper.setProps` 遇到内部触发 `defineModel` 的组件浅比较失效（DefineModel Test Reactivity Trap）**：在 Vitest / Vue Test Utils 单元测试中，若子组件通过 `defineModel` 改变了自身内部状态（如点击关闭按钮将 `open.value` 赋为 `false`），而测试挂载时传入的初始 `props.open` 仍为 `true`。若测试接下来直接调用 `await wrapper.setProps({ open: true })`，Vue 的 Props 浅比较机制发现上游传入的值前后均为 `true`，判定无需触发响应式通知，导致组件无法被重新展开，引发 `.find(...)` 为空的断言假失败。解决之道：测试中针对不同的关闭与阻断链路，**推荐为不同交互分别挂载干净的独立实例**，或先 `await wrapper.setProps({ open: false })` 强制变更上游再置 `true`；
  4. **大体量集合滥用深度 `ref` 导致的代理风暴与掉帧（Large Dataset Deep Proxy Storm）**：将书架全量藏书（`items: LibrarySummary[]`，含数百上千本漫画及各自的 tags、authors、covers 嵌套数组）、阅读器全本漫画（`detail: ComicDetail`，含 50~200 个分镜页对象）、以及发现页排行流存入深层 `ref()` 中。Vue 3 会对每个条目及其所有子属性递归注入 `reactive()` 代理，产生成千上万个 Proxy 实例，引发昂贵的初始化 CPU 占用、内存膨胀和垃圾回收（GC）卡顿。解决之道：对不需要深度细粒度监听属性原地修改的大体量数据集，**强行采用 `shallowRef()`**，数据变更统一通过不可变替换（`items.value = [...items.value]`）触发；
  5. **未关联作用域的裸露定时器与视口常驻监听器（Unscoped Timers & Idle Listener Leak）**：组件内部书写原生 `setTimeout` / `clearTimeout`，并在 `onBeforeUnmount` 中手写清理样板；或为了计算弹出层视口碰撞而在组件初始化时为 `window` 全局挂载 `scroll` 与 `resize` 监听，导致组件在休眠收拢时仍持续唤醒 CPU。解决之道：使用 VueUse `useTimeoutFn` 依托响应式作用域自动回收定时器；使用 Vue 3.5 原生 `onWatcherCleanup` 在 `watch(open)` 展开时动态注册 `window` 监听器、收拢时即刻解绑，达成休眠期 0 监听器、0 CPU 唤醒开销；
  6. **向后兼容双轨桥接与遗留初值 Props 的死代码沉淀（Legacy Dual-Track Bridges & Redundant Initial Props）**：在架构演进升级为多选（如 `activeTag` -> `activeTags`）或使用 `defineModel`（如 `initialActiveCount` -> `v-model:active-count`）后，继续在 Composable 或子组件中保留旧单数属性的 `@deprecated` computed 读写桥、4 组冗余的 `props.initialX` 以及对应的 4 组手写 `watch(() => props.initialX)`。这不仅造成代码膨胀，还会引起状态重复同步的静默回环。解决之道：演进完成后必须彻底拔除 `@deprecated` 桥接与 `initialX` 冗余 props，全面收敛至现代单一真理源。
- **红线与防误伤**：
  - **不要**在 `<script setup>` 中声明 `ref<HTMLElement | null>(null)` 作为模板 DOM 引用；
  - **不要**在模板中手写 `@update:xxx` 胶水绑定，父子双向状态一律使用 `v-model` / `v-model:name`；
  - **不要**在组件内部维护 `internalOpen` 和 `props.open` 的冗余双轨镜像逻辑；
  - **不要**对大体量集合（书架全量 items、阅读器全本 pages、搜索结果）使用深层 `ref()`；
  - **不要**在组件内部保留裸露的 `setTimeout` 并在 `onBeforeUnmount` 中手工清理；
  - **不要**在架构迁移完成后遗留 `@deprecated` 胶水桥接或保留重叠的 `initialX` 初始值 props 与监听器；
- **放行/改用**：
  1. **模板引用强类型化**：全站统一使用 `useTemplateRef<T>('refName')`；
  2. **双向绑定一等公民**：统一使用 `defineModel<T>('name')`，模板消费层直接 `v-model:name`；
  3. **单元测试独立挂载**：对于 `defineModel` 组件的不同交互路径，分别挂载独立 wrapper 避免浅比较跳过；
  4. **大规模数据浅层化**：书架 Store `items`、阅读器 `detail`、发现页 `feed`、Worker 过滤结果一律采用 `shallowRef`；
  5. **动态休眠与作用域定时器**：使用 `useTimeoutFn` 与 `onWatcherCleanup`，实现真正的休眠期零开销；
  6. **坚决淘汰胶水与冗余 Props**：彻底清退遗留的兼容桥与旧式 `initialX` 样板，单一状态唯一收敛。

### 116. 单子元素下 space-between 空间坍塌与本地车号 LOC_loc_ 叠字口吃 (Single-Child Space-Between Clumping & Local Display ID Prefix Stutter)

- **本质**：
  1. **Flexbox 单子项空间坍塌（Space-Between Single-Child Clumping）**：在卡片脚部（`.card-foot`）声明 `display: flex; justify-content: space-between;`。当漫画有浏览量（`comic.views` 存在）时，左侧为观看次数，右侧为 `<CacheProgress>` 缓存进度条，呈现标准两极排布；但本地自建或无浏览量的漫画由于 `v-if="comic.views"` 导致左侧元素不挂载。在 CSS Flexbox 规范中，仅含 1 个子项的 `space-between` 容器行为退化为 `flex-start`（靠左对齐），导致进度条突兀地弹回左侧，与右侧有浏览量的卡片在书架上形成参差不齐的严重视觉撕裂。解决之道：为进度条赋予 `.card-progress { margin-left: auto; }`，无论左侧是否存在元数据，进度条始终刚性锚定在右下角；并在 `@container (max-width: 220px)` 纵向排列时将 `margin-left` 复位为 0；
  2. **本地自建车号 LOC_loc\_ 双重前缀口吃（Local Display ID Prefix Stutter）**：本地上传未指定 ID 时，后端曾默认生成 `source_id = f"loc_{YYYYMMDD_HHMMSS}"`，随后在拼接 `display_id` 时再次拼装 `f"LOC_{source_id}"`，导致车号变成难看的 `LOC_loc_...` 叠字口吃，破坏封面图书馆借阅印章的简洁性。解决之道：规范化 ID 生成，`source_id` 剥离内置 `loc_` 统一为时间戳格式；`LocalProvider.normalize_id()` 与 `display_id()` 剥离冗余 `loc_` 前缀，确立单源格式标准。
- **红线与防误伤**：
  - **不要**在子元素数量动态变化的 `justify-content: space-between` 容器中依赖默认排列来锚定右侧操作/状态项；
  - **不要**在本地自建漫画生成逻辑中硬编码 `loc_` 前缀造成与车号 `LOC_` 的重复嵌套；
- **放行/改用**：
  1. **状态项右对齐刚性锁**：使用 `.card-progress { margin-left: auto; }` 确保右侧项恒定靠右对齐；
  2. **时序清晰自解释车号**：未提供自定义 ID 时生成 `YYYYMMDD_HHMMSS`，格式化为 `LOC_YYYYMMDD_HHMMSS`。

### 117. 外部创作平台 API 契约与本地分卷暂存流水线解耦、URL 响应式污染与深层直达失衡 (Machine API Contract Preservation, Bookshelf Deep-Link URL SSOT & Staging Pipeline Isolation)

- **本质**：
  1. **外部创作者平台（Paper Studio）Machine API 契约与内部暂存管道混淆（Machine Contract Preservation vs Internal Staging）**：
     在重构或清理接口时，将 `POST /api/library/local/create` 误当作可废弃的代码，却忽视了它是外部创作者平台（Paper Studio）携带 Machine API Token 自动化收录成品与手稿资产（`.layers.json`）的标准契约。内部暂存 PDF 管道（`POST /api/library/local/create-from-staged-pdf`）为纸间内部的原子隔离渲染服务，二者职责正交，不可相互取代；
  2. **书架筛选高频 `router.replace` 污染与单向深层直达（Deep-Link Hydration vs Reactive Replace Thrashing）**：
     在实现书架筛选状态与 URL 同步时，若在每次用户输入或点击标签时高频调用 `router.replace`，不仅会在快速切页/跳入详情时引发 Vue Router 的 `NavigationCancelled` 异常中断导航，还会造成历史栈抖动与输入卡顿。解决之道：内存状态作为单一真理源（SSOT），URL 参数仅在组件首次挂载时单向恢复（`hydrateFromQuery`）；需要分享当前筛选视口时，通过用户显式触发的「复制筛选链接」基于 `@vueuse/core` 的 `useClipboard` 导出直达链接，达成 0 导航抢占、0 性能抖动与 100% 可深层直达分享的完美平衡；
  3. **原生 Popover / Tooltip 进场离散过渡缺失 `@starting-style`（Discrete Entry Animation Glitch）**：
     原生 Popover / Tooltip 从 `display: none` 切换至 Top Layer `:popover-open` 时，若只声明了 `transition: ... allow-discrete` 而未配置 `@starting-style`，浏览器无法推断入场初始帧，导致进场动画丢失或瞬间跳变。必须显式声明 `@starting-style` 匹配对应进场关键帧。
- **红线与防误伤**：
  - **不要**在清理自建接口时废弃 `POST /api/library/local/create`；
  - **不要**在书架筛选过滤响应式循环中高频调用 `router.replace`；
  - **不要**在依赖 `allow-discrete` 的原生 Top Layer 浮层组件中遗漏 `@starting-style` 初始帧声明；
- **放行/改用**：
  1. **双平台架构 API 边界**：`POST /api/library/local/create` 作为外部平台入库契约保留，前端统一通过 `buildCommonMetadata` 内部解耦；
  2. **单向水合与按需复制直达**：初次挂载通过 `hydrateFromQuery` 恢复 URL 参数，通过 `buildShareUrl` + `useClipboard` 提供显式深层链接分享；
  3. **标准离散过渡范式**：结合 `transition: ... allow-discrete` 与 `@starting-style` 实现 0 闪烁原生进出场动效。

### 118. 多图源鉴权凭据落盘 TOCTOU 权限真空、SSRF 端口/畸形 IP 绕过、并发重登惊群与 CDN 候选池兜底反向放行 (Multi-Provider Secure Session TOCTOU, SSRF Port/Obfuscated-IP Bypass, Thundering Herd Auth & Failover Fallback Vulnerability)

- **本质**：
  1. **多图源凭据落盘 TOCTOU 权限真空与重复胶水代码（Credential Persistence TOCTOU & Base Class Convergence）**：
     第三方漫画图源（PicAcg、JMComic、以及未来接入的其他需登录站点）需要持久化 Token 或 Cookies 会话。若采用常规的 `open()` 写入后再调用 `chmod(0o600)`，在文件刚创建到 `chmod` 执行之间存在微秒级的时间窗口（TOCTOU），文件在共享 NAS 或多用户 Linux 宿主机上会以系统默认 umask（如 0644/0664）暴露给同宿主机其他账号。此外，若由各个 Provider 自行维护临时文件、并发锁与清理逻辑，极易导致新接入图源遗漏安全防护或写出损坏的半截 JSON。解决之道：将安全持久化下沉至 `ComicProvider` 基类（`save_secure_session` / `load_secure_session` / `clear_secure_session`），在 `os.open(..., 0o600)` 诞生瞬间即赋予私有权限，配合独立进程与纳秒时间戳临时文件及 `os.replace` 原子替换，彻底实现全平台接入契约的单源收敛；并在读取时间戳时做好 `(TypeError, ValueError)` 异常防护防爆 500；
  2. **SSRF 域名安全沙箱的端口伪造、切分顺序与畸形 IP 绕过（SSRF Port Stripping Order & Obfuscated IP Bypass）**：
     在校验远端重定向或 CDN 域名是否安全时，若在判定非法 URI 字符前先行剥离冒号端口（如 `host_part = d.split(":")[0]`），输入形如 `trusted.com:80@127.0.0.1` 或 `trusted.com:80/evil` 会因冒号先行截断导致后半段凭据注入被剥离，误判为安全公网域名放行。同时，若直接将携带端口号的字符串（如 `127.0.0.1:8080`、`[::1]:8080`）传入 `ipaddress.ip_address` 会抛出 `ValueError` 导致绕过。解决之道：必须将 `any(c in d for c in "/?#@%")` 字符黑名单置于最前置，随后剥离 IPv6 方括号与 `:port` 端口，强制校验 RFC 1123 / RFC 1035 标准合法主机名格式，并对最后一段为纯数字的疑似 IP 严格执行点分十进制解析阻断；
  3. **并发自愈重登惊群效应与短频被封（Thundering Herd on Expired Session Re-Auth）**：
     详情页预拉取或全本预缓存并发执行时，多个工作线程遭遇会话过期或受限画卷会同时触发 `force_refresh=True`。若仅在外层加锁而锁内未判定凭据最新时间戳，会导致排队线程依次串行连续向官方发起登录，短时间内连续登录极易触发官方验证码、IP 临时封禁或会话互踢。解决之道：锁内二次检查缓存并在发现 15 秒内刚刚由其他线程刷新成功时直接复用凭据；
  4. **CDN 容灾候选池的兜底反向放行陷阱与明文降级（Failover Fallback Bypass & Cleartext HTTP Downgrade）**：
     在为多 CDN 集群构建容灾降级池时，若存在形如 `if not cdn_candidates and orig_domain: cdn_candidates = [orig_domain]` 的“兜底容错”，一旦所有 CDN 均被安全规则拦截，该分支将无条件将最初被拦截的原始不安全域名重新加入请求队列，使前置防御形同虚设。解决之道：无安全候选可用时坚决阻断并直接抛出异常，且换源重试时强制 `scheme="https"` 杜绝明文降级；
  5. **上游报错与代理凭据泄漏（Sensitive Credential Scrubbing in Logs）**：
     第三方网络库（如 `jmcomic`、`curl_cffi`）抛出的异常文本可能包含包含密码的原始 HTTP 请求或代理连接串，直接输出到 logger 会造成凭据明文落盘。解决之道：统一接入 `_mask_sensitive` 正则清洗，将长密码与代理认证信息替换为 `***`，对 `< 4` 位短密码增加协议边界匹配防止误伤正常单词。
- **红线与防误伤**：
  - **不要**在敏感凭据持久化中写文件后再异步补调 `chmod`；
  - **不要**在各个 Provider 中自行重复编写 session 文件读写与权限控制逻辑；
  - **不要**在判定 URI 非法字符前优先执行冒号截断，防止 `@` 凭据注入穿透；
  - **不要**在 `force_refresh` 场景下排队无脑重复执行网络登录；
  - **不要**在多候选容灾池中编写放行未通过安全检验的兜底逻辑；
- **放行/改用**：
  1. **基类标准原子安全落盘**：所有图源会话读写统一调用 `self.save_secure_session` 与 `self.load_secure_session` 并做好时间戳转换容错；
  2. **严格的主机名沙箱防御**：前置阻断 `/?#@%` 后剥离端口，判定私有 IP、回环地址、链路本地、云厂商元数据（169.254.169.254）与 RFC 标准主机名格式；
  3. **并发防惊群 15 秒冷却**：入锁后二次检查凭据新鲜度，复用瞬时刷新成果；
  4. **候选池全量安全阻断与强制 HTTPS**：无安全节点可用时严格抛出 `RuntimeError`，杜绝任何反向放行与明文 HTTP 传输；
  5. **敏感日志脱敏保护**：日志记录前统一清洗 `JM_PASSWORD` 与 `proxy` 凭据。

### 119. 禁漫 AVS 会话与网页客户端分流错配导致假下架，以及操作级 RPC 污染全局状态引发 Toast 双重弹窗 (JM AVS-Session vs Web-Client Mismatch & Operation-Level RPC Store Error Pollution)

- **本质**：
  1. **禁漫移动端 AVS 凭据与网页客户端分流错配（JM AVS Token & Web Client Mismatch）**：
     禁漫平台（JMComic）在官方 App（移动端 REST API）与网页端（Web HTML）具有截然不同的鉴权协议。上游 `jmcomic` 库在 `client.login()` 成功后，置换出的是 App 端专属的 `AVS` Token。但是若后端在 `fetch()` 中写死调用 HTML 网页客户端（`_make_html_client()`），禁漫 Web 服务器对受限作品（如车号 `1208546`）会执行 302 重定向至 `/error/album_missing`（页面渲染“請先登入”），且 Web 网页登录必须附带图形验证码（`<img src="/captcha">`），根本不识别移动端的 `AVS` Cookie。这导致即使后端已配置合法账号密码且自愈重登成功，使用 HTML 客户端拉取仍会被禁漫当作未登录访客强行重定向至 404，误导为“受权限保护或登录失效”的死锁假下架。
     **解决之道**：架构上确立 **API 客户端优先拉取 + HTML 网页兜底降级**。创建 `_make_api_client()` 并将移动端 `AVS` 会话注入，通过 `_fetch_via_api()` 直接调用移动端 REST API。移动端接口原生识别 `AVS` 凭据，无图形验证码拦截，可毫秒级直达返回受限画卷的完整页数与多章节。通过通用的 `_assemble_fetched_comic()` 完成画卷模型收敛；仅当 API 客户端因网络故障时平滑降级至既有 HTML 抓取。
  2. **操作级 RPC 错误污染全局 Store 状态与 Toast 缺乏防抖去重引发双重弹窗（Store Error Pollution & Undebounced Toast Duplication）**：
     在前端状态管理中，若单次瞬态操作（如 `store.importComic`）在 `catch` 块中将错误赋值给全局状态 `store.error`，会导致挂载在根视图（如 `LibraryView.vue`）的全局监听器 `watch([() => store.error])` 自动弹窗提示 #1；而该操作由于继续向上抛出 `throw e`，发起操作的具体交互组件（如 `ImportPanel.vue`）在局部 `catch` 块中又显式调用 `toast(err.message)` 弹窗提示 #2。同时，若底层 `useToast.ts` 仅做无脑数组 `push` 且缺少短时防抖去重，两条完全相同的错误提示会同时并排堆叠在视口右下角，产生严重的“双重报错”劣质体验。
     **解决之道**：
     - **状态与异常边界清晰化**：操作级 RPC 失败严禁污染表示全库健康状态的全局 `store.error`，仅向外抛出异常，由发起操作的组件（`ImportPanel.vue`）负责直接捕获并展示；全局 `store.error` 仅留给全量书架列表拉取失败等系统级生命周期状态；
     - **Toast 底层同文同音调幂等去重与延期**：`useToast.ts` 内部记录活跃消息。在短时间（如 1.5s）内遭遇相同 `text` 与 `tone` 时，直接忽略新入队动作，并重新刷新既有 Toast 的自动销毁定时器（TTL），彻底消灭任何偶发重入或多链路冒泡导致的重复弹窗。
- **红线与防误伤**：
  - **不要**在已获取移动端 API Token（`AVS`）的环境下仅通过 HTML 网页客户端抓取需鉴权的第三方图源；
  - **不要**在操作级（瞬态 RPC，如导入、重命名、编辑、重新装订）方法中向全局数据流状态 `store.error` 写入局部错误；
  - **不要**在全局监听器和局部交互组件中针对同一操作错误并存两道相同的 `toast()` 弹窗逻辑；
  - **不要**在没有短时去重防抖机制的情况下直接将多路并发/异步捕获的文本推入 Toast 消息队列；
- **放行/改用**：
  1. **API 优先 + 兜底降级双轨契约**：涉及第三方平台解析时，优先使用抗 WAF/免验证码的官方 App REST API，通过统一装配器转换为纸间领域实体，保留 HTML 解析作为网络或协议容灾兜底；
  2. **局部操作异常仅抛不存**：操作级 RPC 的 catch 块仅记录日志并向上 re-throw，不污染全局响应式 Store，由触发交互的具体 UI 局部响应；
  3. **Toast 全局同文同音调短时防抖**：在 `useToast` 中以 1.5s 为窗口对同一 `(text, tone)` 实施幂等合并并刷新定时器，保障 UI 干净利落。

### 120. 图像分析中未统一色彩空间导致调色板与非标准格式极值误判 (Color Mode Normalization Mismatch in Image Extrema Analysis)

- **本质**：在 PDF 页面提取、空白/单色衬页识别及缩略图过滤算法中，直接对 PIL `Image` 对象调用 `getextrema()` 提取通道极值时，未统一色彩空间模式（Color Mode）。在调色板模式（`mode="P"`，如 8-bit Indexed PNG/GIF）或 CMYK / 1-bit 二值图中，`getextrema()` 返回的是调色板索引极值（例如 `(0, 255)`）或通道不匹配的极值，而非真实的 RGB 像素明度与发光强度，导致部分调色板格式的单色纯黑/纯白衬页被误判为非单色内容，或将不同颜色的调色板索引误判为单色。
  **解决之道**：在提取图像极值前，统一步骤进行色彩空间标准化：`thumb = im.convert("RGB").resize((32, 32))`，将所有输入图像格式（P, L, 1, CMYK, RGBA）在内存中转换为标准 24 位 RGB。此时 `thumb.getextrema()` 恒定返回 3 通道 `((min_r, max_r), (min_g, max_g), (min_b, max_b))`，直接判断通道差值与高低阈值即可，彻底消除多分支判断与色彩空间歧义。
- **红线与防误伤**：
  - **不要**在未执行 `convert("RGB")` 的情况下直接对未知来源图像的 `getextrema()` 结果进行明暗或均一性判定；
  - **不要**对调色板模式（`mode="P"`）图像的颜色索引做数值大小推断；
- **放行/改用**：
  - 在任何基于像素极值的空白/单色过滤算法中，前置执行 `im.convert("RGB")` 规范化色彩空间后再做极值分析。

### 121. 单测黑盒契约与测试生命周期隔离 (Test Suite Governance: Blackbox Contracts & Timer Lifecycle Isolation)

- **本质**：
  1. **测试实现细节（White-box Testing Fragility）**：在 Vue 组件测试中，通过 `wrapper.vm.*` 直接读取或修改组件内部响应式状态、直接调用内部私有函数，导致组件进行内部重构（如提取 Composable、改名局部状态）时测试发生假阳性崩溃。解决之道：坚持黑盒测试理念（遵循 Vue Testing Best Practices 与 Kent C. Dodds 哲学），以用户可见的 DOM 内容、ARIA 角色与属性、公开 Props 与 Emits 事件流为断言基准；
  2. **异步与时钟宏任务污染（Real Timer Flakiness & Macro-task Delays）**：使用 `new Promise(r => setTimeout(r, ms))` 带来真实耗时与测试不稳定（Flakiness），或 `await wrapper.vm.$nextTick()` 深度耦合 VM 实例。解决之道：使用 Vitest 假时钟 `vi.useFakeTimers()` + `vi.advanceTimersByTime()` 实现 0 毫秒确定性步进，响应式刷新统一使用 Vue 原生 `import { nextTick } from 'vue'` 与 `@vue/test-utils` 的 `flushPromises()`；
  3. **时钟与全局 Stub 泄漏（Timer & Global Stub Leakage）**：在单用例内部裸调 `vi.useFakeTimers()` 或 `vi.stubGlobal()`，一旦前面断言失败导致后续 `useRealTimers()` 未执行，污染后续测试套件。解决之道：严格在 `beforeEach` / `afterEach` 生命周期钩子中对称管理（`afterEach` 必调 `vi.useRealTimers()`、`vi.unstubAllGlobals()`、`vi.restoreAllMocks()`）；
  4. **复杂的 Composable 宿主上下文（Host Context for Composables）**：依赖 Vue 生命周期钩子（`onMounted`/`onUnmounted`）或依赖注入（`provide`/`inject`）的 Composable，统一使用 `src/__tests__/testUtils.ts` 提供的 `withSetup` 包装器，并在 `afterEach` 执行宿主 App 的 `app.unmount()`。
- **红线与防误伤**：
  - **不要**在组件单测中直接访问私有 `wrapper.vm.*` 内部数据（除非测试 `defineExpose` 声明的显式公共 API）；
  - **不要**在测试中书写 `setTimeout` / `setInterval` 真实延时宏任务；
  - **不要**在测试用例内部裸调假时钟却未在 `afterEach` 中保底恢复；
  - **不要**在修改全局 DOM Prototype 时缺少 `try...finally` 清理；
- **放行/改用**：
  1. **黑盒断言**：通过 `wrapper.find()`、`trigger()`、`setProps()` 及 `emitted()` 测试公开行为；
  2. **Vitest 假时钟与微任务**：使用 `vi.advanceTimersByTime()` 与 `await nextTick()` / `await flushPromises()`；
  3. **严格对称的生命周期清理**：在 `beforeEach` / `afterEach` 保证全局与 Mock 100% 隔离；
  4. **统一测试底座**：复杂的 Composable 使用 `src/__tests__/testUtils.ts` 的 `withSetup()` 工具。

### 122. 局域网纯 HTTP 访问缺少安全上下文导致 WebMCP / document.modelContext 无法注册与失效 (LAN Insecure Context Disabling WebMCP / document.modelContext)

- **本质**：
  1. **Chromium 安全上下文（Secure Context）硬性限制**：
     浏览器端模型上下文协议（WebMCP，即 `document.modelContext.registerTool()`）属于 Chromium 规范中的高权限高级能力（Powerful Feature）。W3C 与 Chromium 强制要求其宿主页面必须满足安全上下文（`window.isSecureContext === true`）。
  2. **本地回环 vs 局域网 IP 的判定差异**：
     `http://localhost:*` 与 `http://127.0.0.1:*` 被 Chromium 视为本地回环（Loopback），天然被信任为 `isSecureContext = true`，因此在开发机本地访问时 WebMCP 正常生效与注册；但当通过局域网其他设备访问纯 HTTP 地址（如 `http://192.168.x.x:5173` 或 `http://192.168.x.x:8000`）时，Chromium 将其判定为不安全上下文（`isSecureContext = false`），直接将 `document.modelContext` 隐藏或置为 `undefined`，导致前端 WebMCP 工具完全无法注册；
  3. **双轨解决方案**：
     - **临时调试方案（Chrome Flag 局部放行）**：在访问端 Chrome 地址栏打开 `chrome://flags/#unsafely-treat-insecure-origin-as-secure`，填入局域网源地址（如 `http://192.168.1.100:5173`），设为 `Enabled` 并重启 Chrome 即可强制开启 Secure Context；
     - **生产终极方案（泛域名 HTTPS）**：通过反向代理网关（Nginx Proxy Manager / Cloudflare Origin Rules）挂载 SSL 证书，全站使用 `https://comic.yourdomain.com` 访问，局域网与公网统一满足 `isSecureContext === true`。
- **红线与防误伤**：
  - **不要**在局域网纯 HTTP 访问发现 `document.modelContext` 为 `undefined` 时误判为代码丢失或前端打包 Bug；
  - **不要**在前端移除针对 `document.modelContext` 是否存在的防御性可选链（`?.`）判定；
- **放行/改用**：
  1. 局域网调试优先使用 `chrome://flags/#unsafely-treat-insecure-origin-as-secure` 声明来源为安全上下文；
  2. 局域网生产部署全面推进 HTTPS 终结。

### 123. 路由过渡前置滚顶污染 HTML5 历史快照导致书架返回归零 (Pre-Navigation Scroll Mutation Corrupting HTML5 History Popstate)

- **本质**：
  1. **HTML5 History 的快照时机陷阱**：在基于 View Transitions 或单页路由进行页面跳转时，如果在前置钩子（如 `router.beforeResolve`、导航守卫或点击事件触发时）过早调用 `window.scrollTo(0, 0)`，此时浏览器尚未完成当前路由的退出与快照保存。这一突变直接将当前页面（如书架首页 `/`）在 `window.history.state` 中的纵向滚动偏移量强行改写为 `{ scroll: { x: 0, y: 0 } }`；
  2. **Vue Router `scrollBehavior` 的假阳性**：当读者在漫画详情页点击“返回书架”或按下浏览器后退键时，Vue Router 接收到的 `savedPosition` 是已被污染的 `{ top: 0 }`。若 `router.options.scrollBehavior` 单纯信任 `savedPosition` 或默认兜底 `{ top: 0 }`，读者先前的滚动位置将被彻底丢弃，每次返回书架都重置回最顶部；
  3. **单例状态物理兜底架构**：书架会话单例状态机（`useShelfState`）在滚动时通过防抖监听真实写入 `shelfScrollY`。在 `router.scrollBehavior` 中，针对返回书架路由（`to.name === 'library'`）施加最高优先级防御：只要 `useShelfState().shelfScrollY.value > 0`，强行返回 `{ top: shelfScrollY.value, behavior: 'instant' }`，对齐 View Transitions 并在首屏瞬间锚定，彻底免疫浏览器历史快照污染。
- **红线与防误伤**：
  - **不要**在路由跳转尚未完成离开（beforeResolve / beforeRouteLeave）之前裸调 `window.scrollTo(0, 0)`；
  - **不要**在 `scrollBehavior` 中直接将 `savedPosition` 视为绝对可信源而忽略书架持久化的 `shelfScrollY`；
- **放行/改用**：
  1. 路由滚顶操作必须交由 `router.options.scrollBehavior` 在目标路由渲染阶段统一调度；
  2. 核心列表/书架视图必须具备状态单例锚点（如 `useShelfState().shelfScrollY`），在返回时优先使用单例记忆实现精确复原。

### 124. SegmentedTabs 双向绑定与 `@change` 守卫冲突导致 Tab 切换被吞 (Two-way v-model Mutating modelValue Ahead of Change Event Causing Early Return)

- **本质**：
  1. **事件触发时序差异**：在支持双向绑定的自定义组件（如 `SegmentedTabs`）中，点击非当前项时，组件内部的 `onSelect(key)` 会先执行 `modelValue.value = key`（直接通过 `defineModel` 更新父组件绑定的 ref），紧接着才触发 `emit('change', key)`；
  2. **父组件假性守卫反噬**：若父组件在 `@change="onTabChange"` 处理函数中习惯性编写 `if (source.value === key) return` 作为“防重复点击”守卫，由于第 1 步已先行修改了 `source.value`，当函数执行时 `source.value === key` 恒等于 `true`，导致父组件的数据加载方法（如 `loadRanking`）被静默拦截并直接 `return`，使得点击 Tab 界面有高亮切换动画却完全无法触发数据拉取；
  3. **防御机制收敛**：`SegmentedTabs` 内部本身已包含 `if (modelValue.value === key) return` 的前置判断（点击当前激活项本就不会触发 `emit('change')`）。父组件的 `@change` 监听器严禁使用 `modelValue === key` 作为判定条件，只需防重判定进行中的网络请求（如 `if (loading.value || refreshing.value) return`）。
- **红线与防误伤**：
  - **不要**在接收 `defineModel` 组件 `@change` 事件的处理函数中编写 `if (state.value === val) return` 防重复守卫；
- **放行/改用**：
  1. 信任子组件的变动分发，仅校验请求并发状态（`loading` / `refreshing`）；
  2. 切换图源时主动重置过期 `feed`（`if (feed.value?.source !== src) feed.value = null`），确保骨架屏在换源时平滑衔接。

### 125. 外部 Provider 榜单接口隐式必填参数遗漏 (PicAcg Leaderboard Missing Required Query Parameter `ct=VC`)

- **本质**：
  1. **上游移动端 API 契约严苛性**：哔咔漫画（PicAcg）官方排行榜接口（`/comics/leaderboard`）除时间跨度参数 `tt`（`H24` / `D7` / `D30`）外，必须同时携带类别/分类过滤参数 `ct`（通常为 `VC` 代表 View Count 浏览榜），且签名计算必须包含该 query string；
  2. **隐式校验报错阻断**：若仅传 `params={"tt": tt_val}`，上游服务器会直接抛出 HTTP 400 `{"code": 400, "error": "1002", "message": "validation error", "detail": "ct is required"}`。该异常被后端捕获并转换为 502 抛向前端，导致榜单无法拉取；
  3. **画页与缩略图前缀兼容**：PicAcg 的 `thumb.path` 既可能为 `tobeimg/...`，也可能为已带 `static/...` 的路径，必须执行智能前缀规范化（`thumb_path.startswith("static/")`），避免拼接出 `static/static/` 导致 404 挂图。
- **红线与防误伤**：
  - **不要**在调用外部非公开移动端反向工程 API 时仅凭直觉传参，必须核对抓包协议与第三方开源客户端契约；
- **放行/改用**：
  1. PicAcg 排行榜固定附带 `ct="VC"`，单元测试中通过 Mock 请求全面校验参数装配；
  2. 统一使用 `src/utils/source.ts` 标准元数据字典管理多源标签、路由与原站直达链接。

---

## 🚦 交付门禁（四步必跑）

1. **静态检查**：`vp check`（前端 0 error、0 warning、格式规范）；
2. **Vue 模板类型检查**：`pnpm type-check`（基于 `vue-tsc --build` 增量模式，排查 Vue template 内部 TS 属性绑定与类型错误，只验证改动文件加速）；
3. **后端测试**：`pnpm test:py`（后端 0 syntax/import error，中间件全链路测试通过）；
4. **定向单测**：仅运行改动对应的单测文件（严禁无差别全量阻塞）。
