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

### 14. PWA 鉴权端点与离线缓存隔离

- **本质**：将状态敏感型鉴权 API 纳入离线缓存策略，导致客户端身份被陈旧响应持久劫持。
- **复现场景**：Service Worker 将 `/api/auth/*` 纳入 `NetworkFirst`，网络抖动或弱网下命中 guest 历史缓存。
- **红线与防误伤**：**不要**在 Service Worker（Workbox）中将动态鉴权或探活端点（`/api/auth/*`、`/api/search/*`）通配进 `NetworkFirst` 离线缓存，且必须在 Manifest 中配置 `useCredentials: true`；**放行/改用**只读元数据与图片正常离线缓存，鉴权接口一律绕过 SW 直连后端（防止馆长身份被永久降级锁死为 403）。

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

---

## 🚦 交付门禁（三步必跑）

1. **静态检查**：`vp check`（前端 0 error、0 warning、格式规范）；
2. **后端测试**：`pnpm test:py`（后端 0 syntax/import error，中间件全链路测试通过）；
3. **定向单测**：仅运行改动对应的单测文件（严禁无差别全量阻塞）。
