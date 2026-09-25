# 错题本与避坑红线（Pitfalls Ledger）

> 纸间核心避坑速查表。按编号或关键词查，不必通读；重构或引入技术时定位对应条目，严禁踩踏红线。

---

### 1. 后端依赖清理与全局权限断层

- **墓碑**：已由 test:py 全链路测试守卫取代，不再单独维护。

### 2. JM 漫画下架 404 容错拦截

- **症状**：输入已下架的 JM 车号时，页面抛出正则匹配异常报 500。
- **根因**：原站重定向至错误页（如 `/error/album_missing`），后端未作下架重定向特征前置嗅探即直接正则提取 HTML。
- **红线**：严禁未经验证对远端 HTML 直接正则提取；必须前置嗅探下架错误页特征并转换为 HTTP 404 友好提示。

### 3. 多章节全局页码单调递增

- **症状**：自建漫画追加画页后翻页跳页、阅读乱序。
- **根因**：局部追加数据仅在章节内局部自增，破坏了全书平铺页码的全局单调递增（Monotonicity）不变量。
- **红线**：多章节漫画追加或重排画页时，必须全量触发全书 `rebuilt_pages` 重排，保持 `ch.start` 与 `page.index` 严格从 1 单调递增，见 AGENTS 不变量 3。

### 4. 服务端路径导入沙箱隔离

- **症状**：服务端路径导入可探测或扫描敏感系统目录（如 `/etc/`、`/root/`）。
- **根因**：直接透传用户物理路径给文件遍历/读取，未做沙箱白名单约束。
- **红线**：严禁未受限的用户输入物理路径直接参与文件 I/O；必须经 `_is_path_allowed()` 白名单校验，严格受限于 `DATA_DIR`、项目根目录与 `ALLOWED_DIRS` 沙箱。

### 5. Vue 3 响应式解包与顶层解构

- **症状**：模板渲染 Composable 变量时显示 `[object Object]` 或失去响应性。
- **根因**：Vue 3 模板自动 unwrap 仅对 `<script setup>` 顶层变量生效，嵌套对象内部 Ref 不自动解包。
- **红线**：严禁向模板传递未在顶层解构的 Composable 包装对象；Composable 返回的 Ref 必须在 `<script setup>` 顶层解构，只解构实际用到的项，见 AGENTS 不变量 4。

### 6. View Transitions 边界与阅读器防抢占

- **症状**：读者在阅读器内快速连续翻页或切话时白屏崩溃（AbortError）。
- **根因**：浏览器全局快照排他，旧 View Transition 尚未决时触发新快照会被底层主动 abort 击穿。
- **红线**：严禁在阅读器内部翻页或切话时调用 `document.startViewTransition`；View Transitions 仅用于跨页面跳转且必须 catch 兜底，页面内过渡用 `<Transition>`，见 AGENTS 不变量 7。

### 7. 硬件图层裁剪（contain: paint 陷阱）

- **症状**：书架卡片 Hover 向上浮动、叠牌倾斜或投影弥散时被容器边界强行裁切，Tooltip 锚定异常或滚动条抖动。
- **根因**：`contain: paint` 或 `content-visibility: auto` 会强行裁切所有超出容器 padding-box 的像素。
- **红线**：严禁在包含 Hover 浮动、叠牌倾斜或弥散投影的卡片上设置 `contain: paint` 或 `content-visibility: auto`；改用 `contain: layout style` 并依托三层防御架构，见 ADR 0018。

### 8. useMemoize 失败缓存残留与参数签名

- **症状**：切页取消请求后再次点击条目，重试永远命中历史异常（如永久报 AbortError）。
- **根因**：VueUse `useMemoize` 默认将 rejected promise 保存在内存池中，导致下游重试持续命中异常结果。
- **红线**：严禁在异步 memoize 函数发生 Promise reject 时残留缓存，必须在 catch 中调用 `.delete(key)` 逐出失败记录，且包装函数必须显式声明完整参数签名。

### 9. 书架切页回源骨架屏闪烁（SWR 保持）

- **症状**：从详情页或阅读器返回书架时，卡片瞬间消失并闪现骨架屏。
- **根因**：切页时无条件重置 `loading = true` 触发 DOM 销毁重绘，破坏了已有数据的视觉连续性。
- **红线**：内存已有书架数据时严禁将 `loading` 置为 true 触发骨架屏；必须采用 SWR 保持旧视图并在后台静默回源更新。

### 10. UI 变体与 Composable 类型契约一致性

- **症状**：调用组件变体（如 `variant="solid"`）导致样式失效或编译报错。
- **根因**：组件 Props 与底层状态机 TS 联合类型脱节，使用了未声明的别名或弃用字段。
- **红线**：严禁在组件调用处书写未在 Props 与 Composable 类型中定义的别名；新增变体必须在组件 Prop 与 Composable TypeScript 联合类型中保持 1:1 严格声明。

### 11. 零伪图标字符与单源字典收敛

- **症状**：图标在不同操作系统字重/基线错位，读屏器将 `'×'` 误读为“乘号”导致无障碍体验崩溃。
- **根因**：在模板中直接使用 Unicode 字符（`'✕'`、`'⋯'`）或散写内联 `<svg>` 代替受控图标。
- **红线**：模板严禁使用文本伪字符或散写内联 `<svg>`；所有图标必须收敛至 `src/components/icons/`（`IconXxx` / `<AppIcon>`），见 AGENTS 不变量 6。

### 12. 零宿主机本地绝对路径（Zero Local Path Leakage）

- **症状**：文档、配置或代码中遗留 `file:///home/...` 等开发者私有绝对路径，他人 clone 或部署时失效泄露。
- **根因**：将宿主机私有文件路径未经相对化直接落盘到受控资产中。
- **红线**：仓库内受控代码与文档严禁写入宿主机绝对路径（含 `file://`）；跨文件引用统一使用相对路径，见 AGENTS 不变量 8。

### 13. 详情页骨架屏与共享封面形变预热

- **症状**：从书架点击卡片进入详情页时闪现全屏灰块骨架屏，共享封面过渡形变（`comic-cover-active`）断裂。
- **根因**：在跨页动画关键帧尚未就绪时全屏切换占位，切断了 View Transition 的图层追踪连续性。
- **红线**：详情接口返回前严禁全屏呈现纯灰骨架屏；必须利用书架已有的 `LibrarySummary` 优先渲染 Hero 头部承接共享封面形变，并搭配 `@pointerenter.once` 意图预热。

### 14. PWA 鉴权端点与离线缓存隔离（API Metadata Cache Ban & IndexedDB User Isolation）

- **症状**：弱网或反代下命中未授权缓存导致馆长权限丢失，或访客意外读取到馆长私密藏书；iOS 添加到主屏幕图标变截图。
- **根因**：Service Worker 错误缓存了状态敏感型 `/api/*` 端点；iOS PWA 缺失标准 180px PNG 根文件。
- **红线**：Service Worker 严禁缓存任何 `/api/` 端点，动态数据离线化必须收敛于受控 IndexedDB 并按 `userId` 分区隔离；必须提供标准 180×180 `apple-touch-icon.png`，见 ADR 0005。

### 15. 后台轮询容错与熔断隔离

- **症状**：后端停机、重启或 401 时，前端定时器高频死循环重试，引发客户端自挂式请求风暴甚至被 WAF 封锁。
- **根因**：未对网络或鉴权报错设置熔断保护，多处轮询实例并发失控。
- **红线**：后台轮询遇到网络异常或 401 报错时严禁盲目静默重试，catch 中必须立即调用 `poll.pause()` 熔断；跨路由轮询必须使用 `createGlobalState` 单例化管理。

### 16. CDN 静态路由别名与穿透防线

- **症状**：公网访问静态媒体跨洋加载缓慢卡顿数十秒，边缘 CDN 强缓存不命中。
- **根因**：静态图片请求采用无扩展名的裸 API 路径（如 `/file`、`/thumbnail`），被 CDN 默认视为动态不可缓存内容。
- **红线**：静态图片与缩略图严禁仅提供裸 API 路由；必须提供带 `.webp` / `.jpg` 扩展名的路由别名并在 CDN 配置静态缓存规则。

### 17. 容器探针日志静音（Noise Suppression）

- **症状**：Kubernetes / TrueNAS 容器控制台每隔几秒狂刷 `/api/health` 200 OK，淹没真实业务异常与审计日志。
- **根因**：高频探活请求走默认 access log 管道输出，缺乏噪声过滤中间件。
- **红线**：严禁心跳探活的 200 流水打满 Uvicorn 控制台；必须通过 `QuietAccessLogFilter` 静音探活日志，并支持 `COMIC_SHELF_ACCESS_LOG=false` 配置彻底消除刷屏。

### 18. SQLite 静态请求写放大与 WAL 单写者锁竞争（Write Amplification in Read Hotpaths）

- **症状**：访客并发阅读预加载图片时，多线程排队争抢 SQLite 写锁触发 `busy_timeout` 与图片加载顿挫。
- **根因**：只读静态资源请求中同步执行数据库写事务（如高频更新 `last_active_at`），击穿 WAL 单写者吞吐上限。
- **红线**：严禁在静态资源读取或高频只读请求路径中无条件同步写数据库；活跃时间等审计字段必须在内存中基于时间与 IP 漂移实施阈值防抖（如 >60s 才落盘一次）。

### 19. 批量并发静态资源误触发令牌桶限流（Rate Limiting False Positives on Bulk Views）

- **症状**：访客进入书架时封面大面积裂图（报 429），管理端名册被误打上“〔 ⚠️ 速率受限 〕”标记。
- **根因**：将针对单连续翻页流的令牌桶限流直接套用于聚合首屏并发请求（50+ 张封面瞬间耗尽 45 突发配额）。
- **红线**：严禁将首屏聚合资源（如书架封面）与单流正文阅读翻页限流绑定在同一突发桶中；正文大图严格限流，聚合视图必须独立解耦或单设预算。

### 20. Check-Then-Act (TOCTOU) 并发穿透配额上限（Deferred Transaction Race Condition）

- **症状**：同一通行证并发多设备登入时，绑定设备总数突破 `max_devices` 配额上限，逃逸淘汰策略与熔断。
- **根因**：SQLite 默认延迟事务（DEFERRED）先查后插未互斥排他，并发线程同时读到未满额状态后双双插入。
- **红线**：并发配额守卫严禁依赖无锁 `SELECT` 做前置断言；进入临界区必须开启 `BEGIN IMMEDIATE` 排他事务或进程互斥锁，确保“查-汰-插”严格原子化。

### 21. 移动端折叠动效与隐藏表单的键盘焦点穿透（A11y Focus Leakage in Collapsible Components）

- **症状**：移动端折叠面板收起后，按 Tab 键光标仍能跳入折叠不可见的输入框中，引发视口异常滚动与失焦。
- **根因**：纯 CSS 高度动画（如 `grid-template-rows: 0fr`）仅在渲染层收缩，内部交互元素仍留在可访问性与 Tab 导航树中。
- **红线**：严禁仅依赖 `height: 0`、`overflow: clip` 或 `opacity: 0` 实现组件折叠；折叠态必须搭配 `visibility: hidden` 与延时过渡，确保收起后彻底剥离 Tab 焦点流。

### 22. 多数据源表单上下文隔离与非相关设置污染（Contextual Settings Leaks Across Import Sources）

- **症状**：切换到「本地自建 / 拆帧」导入时，界面仍暴露「同时缓存全部页面」与「下载并发数」等远端专属选项。
- **根因**：未按数据源 Provider 隔离表单上下文，将远端特定网络选项平铺在通用导入面板中。
- **红线**：跨数据源导入面板严禁暴露非当前 Provider 的配置项；网络并发与预拉取选项必须严格限定在远端 Provider（如 `activeTab === 'jm'`）作用域内。

### 23. 组件拆分真空与 Composable 无脑全量解构（Doc Vacuum & Indiscriminate Destructuring）

- **症状**：组件与 Hook 缺失文档契约致维护黑盒化；解构大量未使用的 Ref 引发 TS6133 警告与模板漏绑。
- **根因**：拆分代码时只做物理搬移而缺失 TSDoc 契约，并在消费层无脑全量解构 Composable 返回值。
- **红线**：严禁裸写无注释的新建/重构 Composable 与组件；消费层必须按需精准解构实际使用的 Ref 与函数，见 AGENTS 不变量 4。

### 24. ARIA 角色属性与无障碍名称规范（ARIA Roles & Accessible Names Mismatch）

- **症状**：读屏器导航识别混乱，Lighthouse / Axe-core 审计抛出 ARIA 角色不匹配或缺少可访问名称错误。
- **根因**：在非交互 `<div>` 挂载 `aria-expanded` / `aria-controls`；进度条角色（`role="progressbar"`）缺失 `aria-label`。
- **红线**：严禁在 generic `<div>` / `<span>` 上挂载控件状态属性，严禁进度条缺失可访问名称；控件状态必须收敛至真实 `<button>`，进度条必须配置 `:aria-label="label"`。

### 25. 静态传输未压缩与初始关键请求链预热污染（Render-Blocking CSS & Eager Prefetch Contamination）

- **症状**：首屏 LCP 与 FCP 严重降速，静态 CSS 未压缩传输且加载瀑布流混入未来视图样式。
- **根因**：FastAPI 未挂载 GZip 压缩中间件；在当前组件 `onMounted` 中同步 `import()` 目标路由 chunk 污染关键请求链。
- **红线**：服务端必须开启 `GZipMiddleware(minimum_size=1000)`；严禁在 `onMounted` 同步预取未来路由，路由预热必须走 `requestIdleCallback` 闲时或意图悬停触发。

### 26. 移动端阅读器高度塌陷与替换元素内生尺寸坍塌（CSS Flex/Grid Basis Collapse & Replaced Element Intrinsic Sizing）

- **症状**：移动端条漫或画页高度塌陷为 28px × 40px 的微缩邮票，悬浮折叠控件遮挡画面。
- **根因**：移动端在 `height: auto` 弹性父级下给 `<img>` 设百分比高度导致 flex-basis 解析为 0；条漫流与分页模式样式混杂。
- **红线**：移动端弹性父级下严禁给替换元素设百分比高度，严禁在阅读器放置遮挡正文的悬浮控件；连续滚动流使用自然流（`width: 100%; height: auto`），工具栏由轻触驱动。

### 27. CSS ScrollTimeline 坐标镜像反转与主线程重排抖动（RTL Scroll Coordinates Inversion & Layout Thrashing in Dual-Track Scroll Architecture）

- **症状**：日漫 RTL 模式下 CSS 进度条从 100% 倒退至 0%；快速滑动时高频读取 DOM 导致严重掉帧卡顿。
- **根因**：RTL 模式下 `scrollLeft` 物理坐标反转却复用了 LTR 关键帧；JS 滚动监听密集读取 `offsetLeft` 触发 Layout Thrashing。
- **红线**：RTL 模式严禁直接复用 LTR 进度条关键帧（必须做镜像反转与 `transform-origin: 100% 50%`）；JS 滚动轨必须通过 `requestAnimationFrame` 调度节流并由 `onScopeDispose` 清理。

### 28. 视口挂载与初次定位时序脱节导致阅读进度重置（DOM Mount Timing & Initial Positioning Failure Under v-if="loading"）

- **症状**：读者点击特定页码进入阅读器时，页面瞬间被重置到第 1 页并冲刷覆盖已有历史记录。
- **根因**：Composable 在 `loading=false` 之前触发 `onLoaded`，受 `v-if="!loading"` 影响此时 DOM 容器尚未挂载，瞬时定位静默失败并以 0 偏移触发滚动保存。
- **红线**：严禁在数据加载 Composable 中将 `loading = false` 延迟到依赖 DOM 的 `onLoaded` 之后；必须恪守“数据就绪 → 解除 loading → 触发 onLoaded/nextTick 瞬时定位”单向流水线。

### 29. PWA Prompt 模式装订更新死锁与 Service Worker controlling 事件缺失兜底（PWA Prompt Mode Update Deadlock & Missing Fallback Reload）

- **症状**：点击 PWA 更新横幅的「立即装订」后，按钮陷入无限旋转动画死锁，页面不刷新。
- **根因**：底层依赖未设超时的 SW `controlling` 事件，在边缘生命周期或缓存状态下事件未触发且业务层缺失超时熔断。
- **红线**：严禁将更新刷新完全押宝于无超时的第三方 SW 事件；必须绑定 `controllerchange` 监听派发 `SKIP_WAITING`，并设立 1.2s 兜底定时器（Fallback Reload）强制重载。

### 30. 后台缓存长任务与前台进度时序竞态（High-Water Mark & Live Cache Lock Race Condition）

- **症状**：预缓存任务完成时，卡片进度条从 100% 突跳回 4% 或归零，几百毫秒后才恢复。
- **根因**：后台任务结束时先解封了实时状态锁，而全量快照尚未回源更新落地，视图瞬间回退到旧快照。
- **红线**：后台任务从运行列表消失时严禁立即释放前端实时缓存锁；必须先执行 `loadItems(true)` 同步权威快照再解封，轮询中引入 `Math.max(cached, prevMax)` 高水位单调递增防护。

### 31. Uvicorn StatReload 全仓扫描假死与轮询无锁导致浏览器 Socket 连接池耗尽（Uvicorn StatReload Scan Deadlock & Browser 6-Socket Starvation）

- **症状**：开发服务频繁卡死不热更；网络面板接口全部挂起为 `(待处理)`，后续全站请求彻底瘫痪。
- **根因**：Uvicorn 裸跑 `StatReload` 扫描 30,000+ 文件致 CPU 跑满；前端轮询定时器无重入锁，请求堆积耗尽浏览器单域名 6 个 Socket 连接池且原生 `fetch` 无超时。
- **红线**：Uvicorn 严禁裸跑全仓 StatReload（必须配置 `watchfiles` 与排除目录）；前端异步轮询必须挂载 `isPolling` 互斥锁与 `AbortController`，全局请求统一封装 15s 超时控制。

### 32. 盒模型伪元素导致浮层误触滚动条与尖角装饰裁切（Pseudo-Element Scrollbar Leakage & Arrow Clipping）

- **症状**：气泡浮层仅 1~2 行短文本却常驻垂直滚动条，外部指示小三角箭头被截断消失。
- **根因**：指示三角与安全桥等绝对定位伪元素产生盒外溢出，根容器声明 `overflow-y: auto` 导致误判溢出并裁切几何装饰。
- **红线**：严禁在包含外置伪元素（小三角/安全桥）的浮层根容器直接设置 `overflow: auto`；根容器必须保持 `overflow: visible; padding: 0`，滚动与内边距下沉至内层 `.tooltip__content`。

### 33. CSS Anchor 碰撞翻转与静态类名脱节导致指示箭头指错方向（Anchor Inline-Flip & Desynced Arrow Alignment）

- **症状**：在屏幕边缘悬停时，浮层因空间不足翻转至对侧，但指示小三角仍停在原侧导致指错目标。
- **根因**：CSS Anchor Positioning 触发 `flip-inline` 翻转时，Vue 模板静态绑定 `props.align`，使得小三角样式与底层实际物理对齐脱节。
- **红线**：严禁为支持 CSS Anchor 自动翻转的浮层小三角绑定静态对齐类名；必须通过动态状态监听或纯 CSS 锚定属性感知翻转，保持箭头对齐几何自洽。

### 34. 路由历史栈污染与子视图层级回退混淆（Up Navigation vs History Back Loop）

- **症状**：在漫画子视图（章节/阅读器）点击返回父详情后，再点返回书库又弹回子视图，陷入回退死循环。
- **根因**：向上层级返回误用 `router.push` 累加历史栈条目，导致浏览器历史栈与逻辑层级树倒置。
- **红线**：层级向上返回严禁盲目 `router.push` 累加历史；子详情返回父详情依据 `history.state.back` 感知出栈或 replace 兜底，沉浸阅读退出统一 replace，父级返回需带下级路由防卫。

### 35. 长篇未缓存作品的无休止轮询空转（Job-driven Polling Guard）

- **症状**：打开数千页未缓存漫画详情页，无任何下载任务时浏览器仍每秒轮询 `/cache` 跑满 CPU。
- **根因**：将 `cached < total` 单纯作为轮询触发条件，缺乏后台活跃任务检测。
- **红线**：严禁仅凭页码未满开启无休止自动轮询；轮询必须严格由活跃任务（`job.running === true`）驱动，无任务时立即暂停，见 ADR 0010。

### 36. 盲从 IDE 警告双写未熟 CSS 属性与前缀级联倒置（Vendor-Prefix False Alarms & Cascade Inversion）

- **症状**：标准属性被遗留前缀语法反向覆盖，移动端产生滚动兼容怪异问题。
- **根因**：盲从 IDE 提示双写未 Baseline 的标准属性（如 `line-clamp`），或在 CSS 规则块中将标准属性写在 `-webkit-` 前缀之前。
- **红线**：严禁盲从 IDE 提示提前双写未成熟标准属性；多浏览器前缀必须严格恪守“前缀在前、标准在后”级联顺序，文本截断收敛至 `<AppTextClamp>`。

### 37. 单话离线画页缓存误标与非连续页码污染（Chapter-Scoped Cache Page Index Pollution）

- **症状**：缓存第 3 话时，第 1 话画页角标虚假亮起，第 3 话进度纹丝不动。
- **根因**：单话缓存误复用全书从第 1 页开始的全局阈值 `p.index <= progress.cached` 计算就地状态。
- **红线**：单话按需缓存严禁使用全局页码阈值更新状态；必须识别 `job.chapter_id` 并限定在该话物理页码区间（`p.chapter === ch.id`）精确标记，任务完成触发静默对账。

### 38. 误将跨路由持久状态置于 `<script setup>` 实例闭包内（`<script setup>` State Persistence Trap）

- **症状**：离开页面（如进入单话或阅读器）再返回时，详情页折叠计数和滚动位置被重置归零。
- **根因**：将跨路由需要记忆的状态声明在 `<script setup>` 顶层变量中，路由切换销毁组件实例导致状态丢失。
- **红线**：严禁在 `<script setup>` 实例闭包内声明需要跨路由存活的持久状态；跨路由/跨实例状态必须提升至独立的 Composable / Store 模块顶层单例。

### 39. 原生 `<dialog>` 顶层浮层陷阱与 CSS 覆盖（Top Layer & User-Agent Stylesheet Collision）

- **症状**：弹窗默认关闭状态下被全屏透明遮罩拦截全部鼠标点击，交互瘫痪；弹窗关闭时生硬黑屏闪烁。
- **根因**：移除了 `v-if="open"` 导致未打开的 dialog 被 CSS 类赋予 `display: grid`；`dialog::backdrop` 作为独立 Top Layer 盒脱离 Vue 过渡动画。
- **红线**：原生 `<dialog>` 模态窗必须配合 `<dialog v-if="open">` 保持物理隔离与 `<Teleport to="body">`；`::backdrop` 保持透明，视觉遮罩交由内部元素配合 `<Transition>` 过渡。

### 40. HTML Invoker Commands API 与 Click 冒泡的双重触发冲突（Invoker Commands & Bubble Race）

- **症状**：点击带有 `commandfor` 的按钮时弹窗闪退或无反应；点击关闭按钮直接掐断离场过渡。
- **根因**：浏览器原生派发 `CommandEvent` 的同时 `click` 事件向上冒泡，外层 `@click` 重复执行 `toggle()` 造成状态二次翻转；原生关闭直接抹去 `open` 破坏 Vue Transition。
- **红线**：带有 `commandfor` 的触发器严禁外层 click 重复执行手写 toggle；`<dialog>` 的 `@command` 事件必须调用 `preventDefault()` 接管关闭，由响应式变量驱动过渡离场。

### 41. PWA 预缓存动态多媒体资产泄漏与虚拟模块隔离（Precache Media Bloat & Virtual Module Isolation）

- **症状**：PWA App Shell 静态预缓存从 ~900KB 暴涨至近 10MB，首屏网络严重受阻且浪费流量。
- **根因**：使用 `import.meta.glob('/public/...')` 扫描 public 动态多媒体（动图/大插画），被 VitePWA Workbox 探测为工程依赖并纳入核心预缓存清单。
- **红线**：严禁对 `public/` 下的大体积多媒体或动态插画使用 `import.meta.glob`；必须通过虚拟模块输出纯文本路径数组，静态预缓存排除动态媒体，改为运行时按需 CacheFirst 缓存。

### 42. iOS WebKit 针对 Web App Manifest 凭据限制（iOS PWA Manifest Credential Drop）

- **症状**：iOS Safari 点击「添加到主屏幕」不识别 PWA，仅生成普通网页快捷方式且无法以独立 Standalone 模式启动。
- **根因**：在 Manifest 链接上配置了 `crossorigin="use-credentials"`，iOS WebKit 判定需同源凭据而直接静默丢弃该 Manifest 响应。
- **红线**：无跨域认证诉求的 Web App Manifest 严禁配置 `useCredentials: true`；保持公开无凭据获取，并在 viewport 补充 `viewport-fit=cover` 适配安全边距。

### 43. Service Worker 活跃连接阻断与浏览器缓存重置竞态（SW Active Connection & Storage Teardown Race）

- **症状**：点击“清空离线缓存”后操作无限挂起或界面看似没被清空。
- **根因**：运行中的 SW 或并发请求持有 open 连接导致 `indexedDB.deleteDatabase()` 永久 blocked；注销 SW 后未刷新页面导致挂载的图片重新触发缓存写入。
- **红线**：重置环境严禁直接裸调整库删除；局部清理清空目标 objectStore，全局重置需解绑注销 SW、清理 CacheStorage 并设立 600ms 定时器强制 `window.location.reload()` 斩断幽灵线程。

### 44. Vite 虚拟模块在 load() 钩子误调 this.addWatchFile 触发目录导入解析崩溃（Vite Virtual Module addWatchFile Directory Panic）

- **症状**：Vite 开发服务器启动或编译时崩溃，报 `Failed to resolve import ".../public" from virtual module`。
- **根因**：在虚拟模块的 `load()` 钩子中对目录调用 `this.addWatchFile(dir)`，Vite 的 import-analysis 插件将其推入依赖并错误尝试将其作为 JS 模块解析。
- **红线**：严禁在 Vite 插件 `load()` 或 `transform()` 钩子中对目录或静态资源调用 `this.addWatchFile()`；目录或非模块文件的变更监听必须收敛到 `configureServer` 利用 `server.watcher` 处理。

### 45. 现代异步 API 认知误区与宏任务错误逃逸（Promise.try & Promise.withResolvers Invariants）

- **症状**：宏任务异常未被捕获击穿主事件循环；超时竞态定时器未被回收导致内存泄漏与无意义唤醒。
- **根因**：误以为 `Promise.try` 能捕获脱离执行栈的宏任务（`setTimeout`）抛错；误以为 `Promise.withResolvers` settle 后不需要清理竞争定时器。
- **红线**：严禁在未包裹 Promise 的宏任务中依赖 `Promise.try` 兜底；配合 `Promise.withResolvers` 的超时定时器在 settled 时必须显式 `clearTimeout`，严禁在生产引入 TC39 Stage 1-2 非标转译。

### 46. 现代 AbortSignal 认知误区与不可撤销定时器隐患（AbortSignal.timeout vs Managed AbortController）

- **症状**：高频搜索或切页时事件循环堆积大量未触发的悬空定时器，阻碍垃圾回收并引起连接竞争。
- **根因**：`AbortSignal.timeout()` 不提供提前取消机制，即便请求毫秒级完成，底层系统定时器仍会挂满设定时长；向 `AbortSignal.any()` 传入非 Signal 对象抛出 TypeError。
- **红线**：高频并发短生命周期 RPC 严禁裸用 `AbortSignal.timeout()`；必须采用受控的 `AbortController` + `setTimeout` 并在 `finally` 显式清除定时器，给 `AbortSignal.any` 传参前需做类型校验。

### 47. 前端 CacheStorage 存储配额“逆向减法归因”与首部抽样偏差陷阱（CacheStorage Subtraction Attribution & Head Sampling Bias）

- **症状**：缓存统计页面误报“纸间核心资产”膨胀至数十兆，画页缓存体积被严重低估 50+ MB。
- **根因**：从固定前 40 项小缩略图顺序抽样估算全量画页产生严重偏差；用全库总占用减去抽样画页逆向推导核心资产，导致剩余画页占用全被误算给 App Shell。
- **红线**：严禁使用 `total - sampled` 逆向推算核心资产，严禁在异质媒体缓存上使用顺序头部抽样；必须直接度量 `workbox-precache` 真实 App Shell 体积，逆向推导画页并纳管所有 Runtime 媒体桶。

### 48. 长列表与画卷收折中的“无限滚动失控”与“遮罩幽灵焦点”陷阱（Runaway Infinite Scroll & Ghost Focus Anti-Pattern）

- **症状**：长列表快速滚动时瞬间挂载数百个 DOM 节点导致掉帧卡死；遮罩盖住末尾卡片导致键盘与读屏器聚焦到不可见链接。
- **根因**：无节制挂载 `useIntersectionObserver` 贪婪追加；试图用纯 CSS 遮罩伪造收折而未真正剥离 DOM 与焦点流。
- **红线**：长列表严禁无脑挂载长距离无限滚动哨兵，严禁在功能性卡片上覆盖半透明遮罩产生幽灵焦点；必须实行受控虚拟分批切片（JS 控 DOM），溢出提示使用独立尾格并提供平滑滚顶收起出口。

### 49. View Transition 异步更新回调跳过引发的 Promise 永久悬空挂起陷阱（ViewTransition Update Callback Skip & Hanging Promise）

- **症状**：后台标签页或频繁切换路由时，页面导航被永久卡死，外部 `await` 永远无法完成。
- **根因**：后台非激活或过渡被抢占时，浏览器直接让 View Transition 报错并跳过执行传入的 `updateCallback`，导致依赖其触发的外部 Promise 永久处于 Pending 状态。
- **红线**：严禁假设 `document.startViewTransition(cb)` 的回调必然会执行；必须在 `updateCallbackDone` 与 `finished` 的 catch 阶段设置兜底拦截，未执行时立即降级执行状态更新并兑现 Promise。

### 50. 阅读器末页完结标记在同路由组件复用下的状态泄漏陷阱（Reader End-of-Book State Leak on Route Component Reuse）

- **症状**：连续阅读时，读完第二部作品后滑动至末页，完结标记不再触发，无法自动沉底归档。
- **根因**：同路由切书时 Vue 原地复用组件实例，末页防抖标记 `hasTriggeredCompleted` 留在闭包中永久为 true，未被销毁重置。
- **红线**：严禁在依赖局部一次性状态的视图组件中忽略 `:key` 隔离；滚动视口内末页卡片必须绑定 `:key="`${source}/${sourceId}`"` 强制切书时重置生命周期。

### 51. 阅览室沉浸式暗室背景与浅色全局控件的对比度碰撞陷阱（Reader Dark Room & Light Global Controls Contrast Collision）

- **症状**：阅读器暗室中幽灵按钮如同隐形，深色文字叠在纯黑背景上无法看清操作。
- **根因**：固定纯黑背景（`#0d0e0c`）的阅读器直接复用了继承浅色主题的前景文字（`--ink-0`），对比度击穿 WCAG 4.5:1 底线。
- **红线**：暗室环境严禁直接复用全局浅色前景变量与按钮样式；文字必须统一使用 `--reader-ink`，底板边框采用 `--reader-surface-strong`，按钮显式声明 `:focus-visible` 焦点环。

### 52. 多行文本截断在首屏批量挂载下的强制同步重排死锁（Forced Reflow & Layout Thrashing in Clamped Lists）

- **症状**：书架批量挂载卡片时主线程阻塞数十毫秒，首屏渲染严重掉帧（DevTools 红色长任务警告）。
- **根因**：组件在 `onMounted` / `nextTick` 中密集同步读取被 `line-clamp` 截断元素的 `scrollHeight` 与 `clientHeight` 触发 Forced Reflow。
- **红线**：严禁在组件初始化生命周期同步读取 DOM 几何排版属性提前探测截断；排版测量必须严格推迟至读者意图交互时刻（JIT 纯按需测量），生命周期内禁止全局 ResizeObserver 轮询。

### 53. 动态图片转码中的惊群效应与 HTTP 内容协商缓存污染陷阱（Thundering Herd & HTTP Content Negotiation Poisoning in Dynamic Image Transcoding）

- **症状**：并发请求同一图片时 CPU 和 I/O 尖峰；不支持 WebP 的客户端从共享代理/CDN 拿到无法解码的损坏图片；资源缺失误报 502。
- **根因**：锁外并发执行 Pillow 转码引发惊群；透明内容协商响应缺少 `Vary: Accept` 导致 CDN 缓存单一副本；源文件不存在粗暴映射为 502。
- **红线**：动态转码必须采用 Double-Checked Locking 互斥收敛，内容协商响应必须带 `Vary: Accept`，源文件缺失必须精准返回 404，见 ADR 0012。

### 54. 反向代理资产强缓存覆盖与 Cloudflare 边缘 Service Worker 换届死锁陷阱（Reverse Proxy Cache Assets & Edge SW Stale Deadlock）

- **症状**：反代开启 Cache Assets 或 Cloudflare 缓存带 TTL 的 sw.js/manifest，导致客户端长期获取旧版 SW，内嵌预缓存资源 404 且新旧版本换届死锁。
- **根因**：反向代理全局强缓存覆盖了应用层 no-cache 标头；Cloudflare Bot 挑战未豁免 PWA 入口导致后台静默 fetch 报 403。
- **红线**：严禁在反代网关全局开启 Cache Assets；SW/Manifest 必须由应用层直发 no-cache；Cloudflare 必须配置 Bypass Cache 与 WAF 白名单放行 /sw.js 与 /manifest.webmanifest，避免后台静默拉取被 403 阻断。

### 55. Cloudflare 免费版 Vary 忽略与边缘缓存越权穿透陷阱（Cloudflare Free Vary Ignored & Edge Cache Auth Bypass）

- **症状**：客户端发了 WebP 请求仍收到旧 JPEG 格式；外部未登录访客直接敲入图片 URL 可绕过鉴权直接命中 CDN 边缘缓存获取私有图片。
- **根因**：Cloudflare Free 边缘忽略 `Vary: Accept`；边缘缓存配置后未对未授权请求实施边缘前置阻断，完全绕过源站鉴权。
- **红线**：严禁依赖 Vary: Accept 做公共 CDN 透明格式协商（前端需使用显式 `.webp` 后缀）；CDN Anycast 边缘必须配置 WAF 鉴权门禁（无凭证 Cookie 直接 403），见 ADR 0012。

### 56. Cloudflare Under Attack 常态化质询与 WAF 鉴权门禁逻辑反转陷阱（Cloudflare IUAM Challenge & WAF Auth Gate Inversion）

- **症状**：已登录合法读者在后台非交互 fetch 时频繁遭遇 403 Forbidden 瘫痪；或配置 WAF 规则后反向阻断已登录用户。
- **根因**：常态开启 Under Attack 模式导致后台无 UI 的 fetch 无法通过 JS 质询；图形化配置 WAF 门禁时漏配逻辑非（`not`）造成条件反转。
- **红线**：严禁常态开启 Under Attack 模式；若需高防必须配置已登录读者凭证豁免规则（Skip 安全级别）；媒体 WAF 门禁表达式必须核对逻辑非（`not (cookie contains ...)`），质询期延长至 1 个月。

### 57. Nginx 反代网关源站 IP 白名单与 Real-IP 变量覆盖误杀陷阱（Nginx Real-IP Overwrite & Origin Access Control Trap）

- **症状**：在 Nginx 配置了 Cloudflare IP 白名单后，全站所有合法正常读者均被全量阻断为 403 Forbidden。
- **根因**：配置 `real_ip_header CF-Connecting-IP` 后，`$remote_addr` 被重写为客户端真实公网 IP，白名单拿着客户端 IP 比对 Cloudflare 网段必然失败。
- **红线**：启用 Real-IP 穿透的网关严禁使用基于 `$remote_addr` 的 `allow/deny` 指令限制 CDN 回源；必须改用 Cloudflare Transform Rules 注入私有通信密钥（`X-Origin-Secret`），网关核验标头准入。

### 58. 微件胶囊散落手写与无障碍按压态断层（Universal Chip & Polymorphic ARIA Trap）

- **症状**：标签胶囊内边距字阶视觉漂移，读屏器无法感知开关按压状态，点击删除按钮误触发卡片跳转。
- **根因**：在各组件中手动散写 `<button class="chip">` 或 `<span class="tag-chip">`，漏标 `:aria-pressed` 且未拦截删除事件冒泡。
- **红线**：严禁在业务组件散落手写原生 chip/tag 胶囊；统一使用多态组件 `AppChip`，展示场景自适应输出 `<span>`，交互场景输出带焦点环与 `:aria-pressed` 的 `<button>`，删除内建冒泡拦截。

### 59. 代理穿透与出站下载下的 SSRF 预解析与 GFW 超时死锁陷阱（Proxy-Aware SSRF & GFW DNS Deadlock）

- **症状**：配置了上游代理下载外部漫画时，每个页面卡死 80+ 秒系统 DNS 超时，工作池彻底瘫痪。
- **根因**：出站请求为了防 SSRF 在本地同步调用 `socket.getaddrinfo`，在大陆境内网络受 DNS 污染阻塞，破坏了代理端远端解析机制。
- **红线**：在依赖上游网络代理的场景下严禁在本地同步执行 `socket.getaddrinfo()` 预探测；改用字面量 IP 私网过滤 + 官方 CDN 根域白名单后缀校验 + 内网镜像显式声明防护。

### 60. 上游拦截响应伪装合法图片与文件魔数防御陷阱（Upstream WAF Disguise & Magic Bytes Trap）

- **症状**：下载的画页在阅读器中裂图，以图搜图或 Pillow 提取特征时抛出 `UnidentifiedImageError` 引发批处理崩溃。
- **根因**：仅凭 HTTP 200 和 `len >= 100` 判断图片成功，上游 WAF 返回的人机验证 HTML 或 JSON 报文被直接命名为 `.jpg` 落盘。
- **红线**：严禁仅凭响应长度或 HTTP 状态假定图像合法直接落盘；写入磁盘前必须严格检查二进制文件前导魔数（Magic Bytes：JPEG/PNG/WebP/GIF/AVIF），不符立即故障转移或报错回滚。

### 61. 短篇画卷封面越界与动态收敛陷阱（Dynamic Cover Count Convergence Trap）

- **症状**：收录 1~2 页短篇漫画时，控制台持续爆出第 3、4 张封面 404/500 报错与破图。
- **根因**：Provider 盲目将固定常量 `COVER_COUNT=4` 写入元数据，请求封面时索引越界超出实际总画页数。
- **红线**：严禁在 Provider 中为 `ComicMeta.cover_count` 直接赋予未经边界收敛的全局常量；必须动态收敛为 `cover_count = min(COVER_COUNT, total_page_count) if total_page_count else COVER_COUNT`。

### 62. 哔咔移动端 REST 接口 Query 参数签名遗漏与假成功静默截断陷阱（PicAcg HMAC Query Stripping & Silent Truncation Trap）

- **症状**：哔咔分卷与画页列表在第一页被误判为空并截断，导致全书 `page_count: 0`、`chapters: []` 坏档且无法预缓存封面。
- **根因**：哔咔 REST API HMAC 签名强制要求相对 URI 保留 Query 字符串，剥离后服务端静默返回 200 无 data 假成功。
- **红线**：计算哔咔 HMAC 签名严禁剥离 Query 字符串；导入时校验 `page_count > 0`，遇坏档穿透缓存触发回源重拉自愈，见 ADR 0013。

### 63. 章节子路由缓存脱节与缩略图静默落盘感知失效（Chapter Subroute Cache Disconnect & Thumbnail-Implied Page Caching Trap）

- **症状**：章节子路由中缩略图已渲染但徽标卡在“待缓存”，单话缓存结束后状态不自动收敛。
- **根因**：缩略图暗中落盘未向上通知；`api.detail` 命中 `useMemoize` 陈旧缓存；子路由误用全书轮询而非单话轮询。
- **红线**：严禁在章节子路由调用全书缓存轮询；缩略图加载感知需向上冒泡更新内存状态；单话缓存完成后必须通过 `bypassCache` 穿透并逐出 `memoizedDetail`。

### 64. 3D 变换下卡片视口投影尺寸缩放与 Scroll-Snap 吸附回弹陷阱 (3D Transform Bounding Box & Scroll-Snap Spring-back Trap)

- **症状**：带有 3D 旋转透视的轮播图中，点击翻页卡片未切换，连续点击才跳动，出现回弹假死。
- **根因**：使用 `getBoundingClientRect().width` 读取首张卡片时获取到的是透视压缩后的投影宽度，计算的步长小于相邻卡片间距，位移未能跨过 CSS scroll-snap 吸附中位线被强行回弹。
- **红线**：严禁在带有 CSS 3D 变换的轮播项上使用 `getBoundingClientRect()` 计算滚动步长；必须基于不受变换影响的排版属性（`offsetLeft + offsetWidth / 2`）结合原生 `scrollIntoView({ inline: 'center' })` 定位。

### 65. 详情页返回参数丢弃与折叠批次基线污染陷阱 (Router Query Stripping & Pagination Baseline Pollution Trap)

- **症状**：详情页返回书架时分馆与搜索参数全部丢失，滚动位置重置；折叠面板“收整”按钮失效或无法收回初始 12 条。
- **根因**：返回按钮硬编码无参 `router.replace({ name: 'library' })`；将列表恢复条数（如 24）直接赋给 `initialStep` 污染了基础收整基线。
- **红线**：详情页返回按钮严禁硬编码无参 replace，优先检测 `history.state?.back` 调用 `router.back()`；`usePaginationFold` 必须将挂载初态切片与折叠收起基线彻底解耦。

### 66. 常驻 SSE 长连接挂起与挂机任务被 `useIdle` 误切断陷阱 (Persistent SSE Idle Hanging & Premature Idle Teardown Trap)

- **症状**：网络面板持续挂起 pending 长连接；挂机长耗时下载（>10 分钟）因无操作被 `useIdle` 意外掐断导致丢失事件。
- **根因**：全站默认常驻 `/api/events/stream`；未将连接生命周期与后台任务状态解耦，被前端空闲检测误切断。
- **红线**：严禁前端默认常开 SSE 长连接；长连接必须由后台活跃任务按需拉起并于任务归零后 5 秒防抖熔断，严禁使用盲目超时的 `useIdle`，见 ADR 0009。

### 67. 标签托盘高度重排冲击波与卡片常驻合成图层踩踏陷阱（Tag Tray Reflow Blast Radius & Resident VT Layer Trap）

- **症状**：展开次级标签筛选时卡片连续位移穿过吸顶毛玻璃与水印背景，引发 GPU 合成雪崩与严重掉帧假死。
- **根因**：流式布局中使用 CSS 高度过渡动效推挤海量复杂卡片，导致逐帧强制重排与全屏滤镜重绘。
- **红线**：严禁在海量卡片主干流中使用高度过渡展开次级标签；标签收纳统一收敛为基于 Popover API + Anchor Positioning 的顶层气泡浮层（`AppPopover`），吸顶栏增加 `isolation: isolate`。

### 68. 条漫切片腰斩与阅读器行内装订页脚冲突（Inlined Page Footer vs Webtoon Slices）

- **症状**：连续切片条漫在画面中间被插入页脚外边距与单页投影腰斩切断；视网膜屏接缝处漏出 0.5px 微缝。
- **根因**：对无缝条漫套用了传统分页漫画的行内页脚和单页尺寸规则；非首图未作亚像素微咬合。
- **红线**：连续条漫模式严禁插入占文档流高度的行内页脚、投影或外边距；状态机必须锁定单列全宽并移除行内页脚，改用悬浮胶囊指示，非首图施加 `margin-top: -1px` 消除接缝。

### 69. 单本作品偏好反向污染全局基线与无界字典膨胀陷阱（Per-Comic Preference Bleed & LocalStorage Bloat Trap）

- **症状**：打开单本条漫自适应设置后，后续打开的所有普通日漫都被强制变异为条漫模式；切换作品遗留上一本排版脏状态。
- **根因**：单本独立偏好写回了全局默认持久化配置；切书时未以全局基线重置共享响应式单例；存储字典未设容量上限。
- **红线**：严禁在活跃作品上下文内修改全局默认持久化存储；切换作品必须以全局配置为真理源重置单例，单本覆盖字典配置 `MAX_OVERRIDES = 100` 实施 LRU 淘汰并保持双轨可见。

### 70. 万级分页偏移跳跃、以图搜图历史断层与全量展开虚假触底陷阱 (Paginated Library Offset-Mismatch, Visual Search Amnesia & Pseudo-Unfold Trap)

- **症状**：展开全部时中间藏书被跳过；以图搜图命中历史藏书却被前端过滤显示“暂无匹配”；完成条与折叠卡矛盾并发渲染甚至 OOM 崩溃。
- **根因**：分页仅靠 `(page - 1) * page_size` 计算致基数跳跃；前端内存仅有首屏无法承接服务端向量检索结果；展开数量基于推测导致提前归零且无显存上限。
- **红线**：严禁流式追加仅靠 `page * page_size` 计算偏移（需解耦显式 `offset`）；向量搜图必须直通服务端定向检索；展开全部必须设置安全上限（如 240 本）并基于实际 DOM 长度计算剩余。

### 71. 同路由 Query 强制滚顶与流式分页失步假死陷阱 (Same-Path Scroll Reset & Frozen Stream Append Trap)

- **症状**：书架切换分类胶囊或筛选时视口被暴力拉回顶部；流式追加第 2 页后 DOM 展现卡在第 24 本不加载新卡片。
- **根因**：Vue Router `scrollBehavior` 对非后退导航默认 `{ top: 0 }`；`watch(items)` 未识别增量追加主动顺延 `visibleCount`。
- **红线**：同路由仅 query/hash 变更时必须阻止滚顶（`if (to.path === from.path) return false`）；数据源增量扩展时必须识别并自适应展开新切片。

### 72. DOM 属性子串匹配误伤与 iOS PWA 桌面图标漂移陷阱 (Attribute Substring Selector Collisions & Apple Touch Icon Mutation Trap)

- **症状**：iOS 添加到主屏幕图标随刷新随机变化为看板娘，甚至桌面图标变白块或退化为网页截图。
- **根因**：使用 `link[rel*='icon']` 模糊子串选择器更新 Favicon 时，误伤并动态覆写了 iOS 专用的 `<link rel="apple-touch-icon">`。
- **红线**：严禁使用 `link[rel*='icon']` 模糊子串选择器；动态 Favicon 严格限定为 `link[rel='icon']:not([sizes]), link[rel='shortcut icon']`，`apple-touch-icon.png` 必须保持绝对静态与 PNG 规范。

### 73. 局部状态隔离引起的全局基线死锁与不透明选择反模式（Isolated Override Deadlock & Opaque Scope Anti-Pattern）

- **症状**：阅读器内修改设置永远只作用于单本作品，全局默认基线变成不可见、不可修改的死锁黑盒，存量脏配置无法自愈。
- **根因**：为防止污染全局而将设置面板入口单向降级为单本覆盖，缺失全局修改入口。
- **红线**：严禁在未提供全局配置入口的情况下将设置单向降级为作品专属覆盖；面板必须采用「本作偏好 / 全局默认」双轨制透明公开，支持即改即分离与存量基线自愈。

### 74. 页面导航挂起死锁与执行上下文销毁竞争陷阱 (Navigation Deadlock & Context Race Trap)

- **症状**：自动化驱动本地 SPA 页面跳转时工具调用挂起死锁，直至协议超时（180s）才中断。
- **根因**：页面导航工具底层在 SPA 上下文急剧销毁与重建时等待 DOM 稳定与 load 事件，在 PWA/HMR 环境下极易陷入死锁。
- **红线**：严禁对本地带 PWA/HMR 的 SPA 页面直接调用自带 DOM 观察等待的页面导航工具；改用脚本执行工具驱动 `window.location.href` 原生跳转，页面就绪后再触发性能追踪。

### 75. View Transitions 跨页前进推进时，Vue Router 的 scrollToPosition 诱发全量 DOM 强制同步重排（View Transitions Forward Nav & Vue Router scrollToPosition Forced Reflow）

- **症状**：从书架点击漫画进入详情页时产生 130~210ms 严重顿挫与掉帧。
- **根因**：Blink 准备截取 `::view-transition-new(root)` 快照时，Vue Router 后置微任务触发 `scrollToPosition` 迫使 Blink 对整棵新 DOM 树执行 Forced Reflow。
- **红线**：跨页前进推进严禁在后置微任务中触发滚动重置；必须在过渡捕获间隙瞬时重置视口（`window.scrollTo({ top: 0, behavior: 'instant' })`），`scrollBehavior` 检测标记直接返回 false 短路。

### 76. Vue <TransitionGroup> 的 FLIP 算法与内部 Render 测量在多节点列表重排时引发连环 Forced Reflow

- **症状**：书架加载 48~~120 本漫画后切换分类/筛选条件，主线程出现 30~~168ms 的 Forced Reflow 阻塞，高刷屏连环掉帧。
- **根因**：Vue `<TransitionGroupImpl>` 渲染时无条件遍历所有子节点调用 `getBoundingClientRect` 测算 FLIP 位置，大量节点离场时密集调用 `getComputedStyle` 查询过渡时长，交错触发 Layout Thrashing。详见 [ADR 0014](docs/adr/0014-view-transitions-boundaries-and-shelf-flip-decoupling.md)。
- **红线**：长列表或动态卡片网格（`comic-grid`、`page-grid`、`chapter-grid`）严禁使用 `<TransitionGroup>`；一律回归原生 `<div>` 配合 CSS `@starting-style` 由 GPU 合成器接管入场，由 `scripts/detect-perf.mjs` 门禁规则拦截。

### 77. 多态按钮覆盖 role="button" 引发的无障碍与 Space 键滚动冲突，及微型哨兵污染弹性布局间距陷阱

- **症状**：多态跳转链接被读屏器误报为按钮且按空格无法跳转反而引发页面滚动；Flex 工具栏边界对齐因滚动检测哨兵被推开 16px；阅读偏好设置刷新后静默丢失。
- **根因**：底层跳转链接强加 `role="button"` 破坏原生链接语义且不响应 Space 键；Flex 容器在 1px 哨兵与首尾元素间自动注入 `gap`；单本覆盖与全局基准双轨持久化漏序列化 `autoTurn` 等子字段。
- **红线**：跨页导航的 `<RouterLink>`/`<a>` 严禁赋 `role="button"`；滚动检测哨兵必须用负边距（`calc(-1 * var(--space-4) - 1px)`）完全抵消 Flex gap；单本覆盖与全局基线字段在序列化与互斥锁上必须保持 100% 结构对称。

### 78. HTML-in-Canvas 列表卡片反模式

- **墓碑**：HTML-in-Canvas 列表已删除，由标准 DOM 列表与 canvasProbe 取代。

### 79. SQLite FTS5 台词全文检索幽灵索引、访客隐藏漫画泄漏与多章节页码偏移陷阱

- **症状**：搜出已删除/更新漫画的失效台词；访客意外搜出未公开或隐藏藏书的对白；点击搜索结果跳转阅读器时分卷画页页码错位。
- **根因**：删书或重订时未原子清理 `comic_dialogues_fts`；访客过滤条件在未入库索引（`ci.source IS NULL`）时被 `COALESCE` 误判为公开；分卷 OCR 伴生文件的章内相对页码未折算为全书全局页码。详见 [ADR 0017](docs/adr/0017-comic-dialogue-fts-and-bubble-overlay.md)。
- **红线**：删除/重订漫画必须级联清理 FTS 虚拟表；访客过滤必须双重断言 `ci.source IS NOT NULL AND hidden_from_guest = 0`；多章节台词页码必须由 `sync_comic_dialogues` 读取 `album.json` 映射为全书单调递增全局页号（`1..page_count`）。

### 80. 漫画画页气泡高亮定位的 Letterbox 黑边漂移、Flex 高度传递失效与坐标自适应归一化陷阱

- **症状**：翻页模式下分镜气泡高亮框相对画面下坠 25%~30% 或受黑边影响偏移；慢网下底图未加载完呼吸动画提前播完；顶部边缘气泡徽标被视口截断。
- **根因**：高亮层挂在含 Letterbox 的外层容器，且嵌套 frame 未设明确高/宽高比导致 `img` 的 `max-height: 100%` 退化溢出；在 `!imageReady` 时提前触发呼吸动画；OCR 坐标系存在 0..1000/0..100 标度混杂或未防溢出。详见 [ADR 0017](docs/adr/0017-comic-dialogue-fts-and-bubble-overlay.md)。
- **红线**：高亮覆盖层严禁挂在含黑边的自适应容器上，画页容器必须锁定图片真实宽高比（`:style="{ aspectRatio: naturalRatio }"`）；底图就绪（`imageReady`）前严禁激活呼吸脉冲动效；坐标必须经 `parseBubbleBox` 归一化钳位 [0, 1]，边缘提示徽标自适应翻转方向。

### 81. 前台搜索栏双重意图冲突、破坏性空状态劫持与 Combobox 视口盲航陷阱

- **症状**：在书架搜索书名时突然弹出台词无结果空状态浮层遮挡卡片；键盘上下键选择联想项超出可视区时无法跟随滚动；高亮片段存在 XSS 注入风险。
- **根因**：台词后台自动检索返回 0 条时无差别展开浮层；联想列表滚动容器未联动 `scrollIntoView`；后端 FTS5 `<mark>` 高亮标签若使用 `v-html` 渲染存在注入漏洞。
- **红线**：后台自动防抖检索 0 结果时必须保持静默隐藏，仅用户主动按 `ArrowDown` 才展开空状态；键盘焦点移动必须联动 `scrollIntoView` 确保视口可见；渲染搜索高亮片段严禁裸用 `v-html`，必须通过纯函数解析为 Token 声明式渲染。

### 82. SQLite FTS5 Trigram 短词全表扫描锁死、单库 WAL 写锁争抢与命令前缀输入流解耦陷阱

- **症状**：输入 1~2 字短词检索台词导致 SQLite CPU 100% 挂起数秒甚至死锁；后台批量同步 OCR 台词时前台读者翻页打点与收藏频繁报 `SQLITE_BUSY`；书架搜台词导致卡片网格被清空。
- **根因**：FTS5 trigram 索引要求 $\ge 3$ 字符，短词查询被底层强制降级为逐行 `LIKE '%query%'` 全表扫描；台词倒排索引与用户业务主库混用，单库 WAL 写锁被后台写入独占；搜索框未区分书名过滤与台词全文检索。
- **红线**：前后端严禁放行 `< 2` 字符穿透至 FTS5 引擎（短路拦截返回空，2 字短词走有界 `fetch_limit`）；台词倒排索引必须物理隔离为独立的 `comic_dialogues.db` 专库；台词检索必须通过命令胶囊（如 `/台词`）与书架本地过滤严格解耦。

### 83. 阅读器无条件挂载分镜覆盖层导致长篇画卷性能退化与气泡 URL 状态残留陷阱

- **症状**：长篇漫画（100~200+ 页）在非台词搜索进入时连续滚动/切页卡顿；台词跳转进入后翻阅多页，复制 URL 分享或刷新仍残留旧页气泡高亮。
- **根因**：`ReaderViewport.vue` 在遍历画页循环中无条件实例化 `<ReaderBubbleOverlay>` 产生海量 VNode 与响应式开销；翻页或呼吸动画结束后未清理 URL 查询参数。
- **红线**：覆盖层必须在模板中以 `v-if="targetBubble && targetBubble.page === page"` 精确短路挂载；气泡呼吸高亮结束（2.8s）或翻离当前画页后必须调用 `dismissBubble()` 并通过 `router.replace` 擦除 `bubble_box`/`bubble_text` 参数。

### 84. 进度条四舍五入虚假满额、浮点噪点污染与单页重试缺失陷阱

- **症状**：界面显示进度 100% 但卡在 207/208 页且按钮仍为可点击的“缓存全部”；DOM 内联样式中充斥 16 位高精浮点噪点；单页网络抖动导致整本预取异常中断。
- **根因**：`Math.round` 在 99.5% 时进位成 100% 造成终态认知撕裂；未对浮点计算做精度截断；后端下载循环对单页网络异常直接跳过退出且无瞬态重试。
- **红线**：未完成状态严禁四舍五入到 100%（`current < total` 时用 `Math.min(99, Math.floor(...))` 封顶 99%）；内联样式浮点数必须通过 `truncateProgressFloat` 保留 4 位小数；预缓存循环必须包含就地退避重试（300ms）与漏页通知。

### 85. 条漫连续模式终页高度不足致物理触底失效、流卷停靠态竞态循环与动晕症陷阱

- **症状**：条漫模式下滚动完全触底但页码永远卡在倒数第二页（如 160/161），且无法触发章末卡片与下一话跳转。
- **根因**：最后一页物理高度小于视口高度时，容器滚动触底后末页顶边仍处于视口中下部，仅依赖 `offsetTop - scrollTop` 绝对距离判定导致算法始终误判倒数第二页为最近页。
- **红线**：连续滚动模式严禁仅依赖页面顶边到视口顶端的绝对距离判定当前页，当 `position >= max - 24` 时必须确定性夹紧至 `lastGroupIndex`；非边界采用视口上方 40% 有效阅读线几何相交探测；自动翻页严禁在条漫（竖向连续）模式下启用。

### 86. 超长单本主滚动容器全量 offsetTop 重排风暴致 Chrome 崩溃与 iPad WebKit 惯性动量锁死

- **症状**：900+ 页拆帧漫滚动时 Chrome 崩溃或 CPU 100% 假死；iPadOS Safari 触控滑屏惯性动量瞬间锁死且滚动条闪烁。
- **根因**：高频 `handleScroll` 中通过 `querySelectorAll` 遍历全部 DOM 节点密集读取 `offsetTop`/`offsetHeight` 引发 Forced Reflow；iPad 合成器线程与主线程几何失步触发 WebKit 保护性终止动量。
- **红线**：滚动事件中严禁对全部画页 DOM 执行全量 `querySelectorAll` 线性测量；超长图集严禁盲目移除 `content-visibility: auto`；必须采用局部邻域探测（当前页 $\pm 2$ 页）结合二分查找收敛（$O(1) \sim O(\log N)$）。

### 87. 海量藏书与长篇画卷前端高频计算反模式（O(N) 遍历、比较器内 new Date 与击键全量小写字符串风暴）

- **症状**：千页单本切页卡顿；书架按收录时间排序时严重 GC 掉帧；搜索框打字输入卡顿吞字；日漫 RTL 模式拖动滚动条跳往相反章节。
- **根因**：页码换算使用 $O(N)$ 循环遍历二维数组；`sort` 比较器内部反复构造 `new Date()` 解析字符串；过滤时每击键一次对每本书的所有属性做 `.toLowerCase()` 产生海量临时字符串；滚动定位插值未考虑 RTL 物理倒序。
- **红线**：单调页码映射必须采用数学封闭解 $\lfloor (\text{page} - \text{first}) / \text{ppv} \rfloor$ 计算；排序前必须单遍提取时间戳数值，中文排序复用单例 `Intl.Collator`；击键过滤必须使用 WeakMap 缓存全文本；RTL 模式横向滚动必须使用 `1 - position / max` 插值。

### 88. 缓存对账与轮询接口高频同步 I/O 导致磁盘争抢陷阱

- **症状**：前端高频轮询 `/cache` 进度接口导致服务器磁盘 I/O 100% 跑满，并发下载时发生文件截断或元数据竞争错乱。
- **根因**：轮询热路径中无条件执行全量磁盘对账，在循环内部逐页调用 `os.path.exists()` 产生上千次系统调用；对账修改直接无锁写回 `album.json`。
- **红线**：轮询查询接口必须为纯内存只读快照，严禁触发同步落盘写入；对账必须用单次 `os.scandir` 收集已有文件名后做内存 Set 判定；更新缓存标记必须在持有漫画锁下局部合并，与画页物理迁移和派生生成解耦。

### 89. 翻页模式大跨度跳转阈值与正反候选页探测陷阱

- **症状**：高分屏或双页拼卷模式下正常单屏翻页发生卡顿掉帧，快速连续翻页时视口定位回退卡顿。
- **根因**：大跨度跳转门禁硬编码绝对像素（600px）导致正常双页翻页被误判为手动拖拽跳转；快速翻页候选邻域仅限 $\pm 1$ 组导致探测频繁脱靶回退到二分查找。
- **红线**：大跨度跳转门禁严禁使用固定像素阈值，必须采用动态视口相对阈值（`pageSize * 0.5`）；局部邻域探测必须使用 $\pm 2$ 双向候选集（`[cur, cur+1, cur-1, cur+2, cur-2]`）覆盖跨组快速翻页。

### 90. 万级藏书客户端多维搜索与主线程 CPU 掉帧陷阱（Web Worker 卸载、极简 ID 传递与三层防御）

- **症状**：书架藏书量达万级时，在搜索框打字输入卡顿、光标停滞、输入法吞字。
- **根因**：万级图书过滤与排序在主线程全量运算（20~50ms）；若将完整对象全量传给 Web Worker，浏览器的 `structuredClone` 序列化开销抵消卸载收益。
- **红线**：Web Worker 通信严禁双向全量传输重型业务对象数组（通信协议仅传轻量参数与 `string[]` ID 列表）；DOM 渲染必须由 `usePaginationFold` 受控折叠（默认 12 张卡片，软封顶 120 张）；书架卡片严禁使用 `content-visibility: auto` 以免隐式激活 `contain: paint` 裁切悬浮阴影。

### 91. Composable 传参膨胀与跨层对象聚合反模式

- **症状**：调用高阶编排 Composable 时入参列表长达数十行，参数极易错位导致类型漂移与隐蔽 Bug，组件脚本突破 150 行。
- **根因**：将所有子状态机无脑扁平解构为数十个平铺离散的 Ref 和回调，破坏了领域聚合边界与代码可维护性。
- **红线**：封装高阶 Composable 严禁设计接收 10 个以上平铺离散参数的巨型签名；高阶调度器必须接收子状态机命名对象聚合包（如 `{ settings, bubble, data, paging, chrome }`）并在函数体内部就地解构。

### 92. Vue 模板增量 TS 检查与 Composable 解构漏绑陷阱

- **症状**：`vp check` 报通过但运行白屏或报 `TS2339`/`TS2551` 属性不存在，模板绑定的响应式变量静默失效。
- **根因**：`vp check` 仅校验脚本内部类型，无法深入检测 `.vue` 模板 `<template>` 内部表达式；逻辑从组件抽取到 Composable 时漏在 setup 顶层解构模板引用的属性。
- **红线**：任何涉及 `.vue` 文件的变更交付前必须运行 `pnpm type-check`（基于 `vue-tsc --build` 增量验证）；Composable 返回值必须声明清晰契约并在 `<script setup>` 顶层精准解构模板绑定的 Ref。

### 93. 轮询状态提前覆写与任务终止反馈静默吞没陷阱

- **症状**：后台长任务（如画页预缓存）结束时，精心设计的完成 Toast 提示或回调完全未弹出，静默终止。
- **根因**：轮询回调顶部过早将服务端 `job.running` 赋值覆盖本地响应式状态 `caching.value`，后续判断 `wasCaching` 时已是覆写后的 `false`，导致终态分支永远不可达。
- **红线**：严禁在判断任务终态前提前将服务端 `job.running` 赋值给记录本地状态的 Ref；必须先捕获状态快照（`const wasCaching = caching.value`）或通过显式状态机事件驱动终态反馈。

### 94. 组合式函数双向依赖与临时 Ref 拆分身份陷阱

- **症状**：组件初始化时报 TDZ 引用错误；状态双写竞态导致数据不一致；`<script setup>` 代码行数膨胀突破 150 行。
- **根因**：Composable 之间循环依赖，在视图层创建临时中间 Ref 并通过 `watch` 反向同步，使单一实体分裂为两个 Ref 镜像（Split Identity）。
- **红线**：严禁在 `<script setup>` 中为了避让组合式函数初始化次序创建桥接用中间 Ref 与双向 watch；数据源必须按拓扑序初始化并通过原生 Ref 单向传递，相互依赖的回调采用延迟局部委托函数挂接。

### 95. 复合画卷重新装订与缩略图粗暴失效陷阱

- **症状**：单话重新装订导致整本数十个章节的缩略图全部失效需重新生成；远端刷新将手工装订补录的画页全量覆盖破坏。
- **根因**：单话替换粗暴清空整本 `thumbs_dir`；带 `custom_pages: true` 的漫画缺少远端刷新阻断门禁；多章节复合命名未聚类导致章节丢失。详见 [ADR 0020](docs/adr/0020-hybrid-chapter-re-binding-and-pattern-grouping.md)。
- **红线**：单话装订严禁无差别清空整本缩略图/封面，仅清理目标话目录下的 WebP 缩略图；严禁远端 Provider 刷新覆盖带 `custom_pages: true` 的漫画（API 路由 400 阻断并前端隐匿按钮）；复合分话必须使用正则聚类与单调重排。

### 96. CSS 变量虚假防御与属性过渡反模式陷阱

- **症状**：渐变背景 hover 时产生生硬闪烁与无谓重排；Token 调整时组件颜色未同步；打包体积因重复 keyframes 膨胀并伴随命名污染。
- **根因**：组件内手写硬编码 Fallback（如 `var(--accent, #b34a36)`）掩盖变量拼写错误；渐变属于 `<image>` 无法被传统 `transition: background` 平滑插值；散落组件重复手写 `@keyframes spin`/`shimmer` 基础动画。详见 [ADR 0021](docs/adr/0021-css-governance-modern-properties-and-tokens.md)。
- **红线**：组件内严禁手写静态 Hex/像素 Fallback，全站除 `tokens.css` 外 0 Hex 残留；渐变过渡必须通过 `@property` 注册类型化自定义属性，纯色背景明确用 `transition: background-color`；通用基础动画必须收敛至全局 `main.css`，严禁在业务组件中重复手写 `@keyframes`。

### 97. Vue 3.6 Vapor Mode 虚树假设与私有原语反模式陷阱

- **症状**：启用 Vapor 模式后抛出 `TypeError: Cannot read properties of undefined` 白屏崩溃，或嵌套 RouterLink 时单测报 `shapeFlag` 错误。
- **根因**：Vapor 模式直接编译为原生 DOM 与微粒 Effect，根本不存在 VNode 树（`instance.vnode` 为 `undefined`）；高密度叶子节点滥用 VDOM 容器 `<RouterLink>` 破坏微粒直驱红利。详见 [ADR 0023](docs/adr/0023-vue-3-6-vapor-mode-local-probe-and-progressive-enhancement.md)。
- **红线**：Vapor 组件内严禁读取 `getCurrentInstance()?.vnode` 或使用 `<style>` 内部的 `v-bind()`；高密度叶子组件严禁滥用 `<RouterLink>`（改用原生 `<a>` 配合 `router.push()` 渐进路由）；严禁在 `vite.config.ts` 全局开启 Vapor，必须以 `<template vapor>` 在叶子组件局部探针推进。

### 98. Vue 3.6 RC 与 Vitest 双包危害与实例割裂陷阱

- **症状**：Vitest 单测报 `TypeError: Cannot read properties of null (reading 'vapor')` 或路径别名解析失败。
- **根因**：`@vue/runtime-vapor` 仅发布 ESM 产物，Vitest 在 Node 环境默认以 CJS 加载 `@vue/test-utils`，导致多实例上下文割裂（`currentInstance` 恒为 `null`）；pnpm 严格依赖拓扑下相对路径别名失效。
- **红线**：严禁在 `vitest.config.ts` 中单独将 `vue` 别名指向独立单文件或硬编码相对物理路径；严禁在子模块中硬编码散落的 RC 小版本；必须通过 `createRequire` 全链路解析 ESM Bundler 单例，并通过 pnpm Catalog 统一锁定版本。

### 99. 全局按键切话监听穿透、macOS 历史导航抢占与伪存活 Ref 声明陷阱

- **症状**：Mac 用户按 `Cmd+[` 返回上一页时被误截获为切话且路由栈撕裂；弹窗打开时按键导致背景切话；长按连发卡死导航队列；代码中充斥 `void dropZoneRef` 伪存活代码。
- **根因**：`keydown` 监听未过滤 `metaKey`/`ctrlKey`/`altKey` 修饰键；未检测活动模态层与 `e.repeat`；旧式 Composable 无法穿透模板 ref 导致平息 linter 警告时产生胶水代码。
- **红线**：单键快捷键严禁遗漏修饰键拦截与活动模态层（`dialog[open]`）过滤，切话需 `preventDefault()`；严禁在组件中写 `void <ref>` 伪占位或单节点 `:ref="(el) => ..."` 胶水；DOM 容器统一使用 Vue 3.5 `useTemplateRef` 声明注入，函数 Ref 仅限 `v-for` 字典寻址。

### 100. 本地路径导入与长耗时 RPC 一刀切短超时引发的时序撕裂与 I/O 阻塞陷阱

- **症状**：本地大量图片导入时前端 15s 精准报错超时，但后台却默默入库成功，刷新后漫画已存在；导入期间 NAS 磁盘 I/O 狂飙数分钟。
- **根因**：全站一刀切 15s 超时无法承载重型磁盘 I/O；同卷文件导入使用 `shutil.copy2` 产生全量冗余物理拷贝；同步导入请求中同步逐章生成多话封面阻塞 HTTP 响应。
- **红线**：严禁对重型导入任务施加 15s 短超时（必须放宽至 60s~120s 分级超时）；同卷文件导入严禁全量物理复制（优先 `os.link` 硬链接，跨卷 `EXDEV` 回退复制）；严禁在主导入请求中同步生成全量多章节封面，多话封面交由后台异步转码。

### 101. 单测全量 Mock 模块导出缺失与 Pinia 上下文隔离陷阱

- **症状**：单测抛出 `No "createRouter" export is defined on the "vue-router" mock` 或 `getActivePinia() was called but there was no active Pinia` 导致套件崩溃。
- **根因**：`vi.mock` 使用简单对象替换彻底覆写了第三方库原生导出；测试依赖 Store 的 Composable 时未激活 Pinia 实例。
- **红线**：第三方核心模块的 `vi.mock` 必须采用 `async (importOriginal) => ({ ...await importOriginal(), ... })` 保全底层导出；涉及 Store/Composable 测试必须在 `beforeEach` 中调用 `setActivePinia(createPinia())` 建立沙箱隔离。

### 102. 源代码内嵌巨型多字节字符字面量致 IDE/LSP 卡死与静态数据解耦陷阱

- **症状**：开发者在 VS Code/Cursor 中打开代码文件时编辑器卡死假死，Pyright/Tree-sitter 耗尽 CPU；轻量测试导入模块变慢。
- **根因**：Python/TS 源文件中直接内嵌数千字超长单行字符串字面量（如 3881 对简繁映射表），冲垮语法高亮与 AST 分析；模块顶层即时构建重型映射表。
- **红线**：严禁在源代码文件中直接内嵌数千字符以上的静态数据字典或超长字符字面量；静态映射必须物理解耦为独立的二进制/压缩伴生文件（如 `zh_tables.dat`），并通过双重检查锁与线程安全单例惰性加载。

### 103. 模块拆分动态反射、Mixin MRO 遮蔽与非原子性写入时序陷阱

- **症状**：单测单独运行时单例方法静默失败；多继承子类调用具体实现时抛出 `NotImplementedError`；画页替换写盘失败后旧台词索引被永久误删无法恢复；公网直连时安全限流被伪造 IP 绕过。
- **根因**：重构拆分后使用 `sys.modules.get` 动态反射主应用符号破坏类型追踪；`ComicStoreBase` 桩方法在 MRO 顺序中排在 Mixin 之前导致实际实现被遮蔽；写入前提前执行索引清理破坏 Crash-Safe 事务；无条件信任 `X-Forwarded-For`。
- **红线**：严禁在生产代码中使用 `sys.modules.get` 动态反射（必须显式导入与直接调用服务）；多继承顺序必须为 `class ComicStore(*Mixins, ComicStoreBase)`；必须遵循先写盘成功再原子清理关联索引（Write-Then-Delete）；直连或未配置受信任反代时严禁信任外部转发标头。

### 104. CSS Token 标尺断层、Undefined 变量静默回退与层叠上下文遮挡反模式

- **症状**：搜索下拉选单或自动补全浮层被下方的卡片封面硬生生切断遮挡。
- **根因**：浮层声明了未在 `tokens.css` 中定义的 `--z-dropdown`，浏览器静默回退为 `z-index: auto`；书架头部后方的卡片因 `contain` 与 `transform` 形成独立层叠上下文，DOM 顺序在后直接绘制覆盖在前方元素之上。
- **红线**：严禁在组件中使用未在 `tokens.css` 注册的伪 CSS Token（Z-Index 标尺必须全局统筹注册）；承载绝对定位下拉浮层的父容器必须显式提升层叠上下文（`position: relative; z-index: var(--z-dropdown)`）。

### 107. Starlette StaticFiles 与 FastAPI HTTPException 继承断层导致 SPA Fallback 穿透失灵

- **症状**：真机 Docker / NAS 部署环境下刷新前端路由（如 `/discovery`）直接返回 JSON 404 错误，而单测全绿。
- **根因**：FastAPI 的 `HTTPException` 是 Starlette `HTTPException` 的子类，Starlette 的 `StaticFiles` 抛出的是父类，自定义 SPA 静态处理只捕获子类导致 404 异常逃逸；单测私造 Mock 类未走真实生产 ASGI 挂载实例。
- **红线**：继承/扩展 `StaticFiles` 必须联合捕获 `(HTTPException, StarletteHTTPException)`；单测必须直接引入生产 ASGI 实例（`from app.main import app`）进行端到端检验；静态目录解析必须提供环境变量与候选链自愈解析。

### 108. 存储拆分重构中画页物理路径与全局页码合成脱靶致 502 穿透陷阱

- **症状**：多章节漫画第 2 话以后的画页和缩略图大面积报 502 Bad Gateway；本地重新装订的漫画缓存标记被反向刷为 False。
- **根因**：拆分存储层时错误使用全局递增页码 `f"{index:05d}{ext}"` 动态合成文件名，破坏了 `page.file` 单一事实源；文件找不到回退到远端下载，而本地自建漫画 URL 为空引发异常，路由未细化错误直接包装成 502。
- **红线**：寻址画页物理路径严禁通过 `index` 猜测合成，必须无条件读取 `page.file`；`ensure_page` 中画页 `not page.url` 时严禁调用远端下载（直接抛 FileNotFoundError 并由路由转 404）；元数据缓存校验必须基于纠偏后的单一真实路径。

### 109. 超长画卷离屏毛玻璃与无限动画引发合成雪崩及翻页页码自激震荡陷阱

- **症状**：千页单本滚动时高刷屏严重掉帧、移动端显存崩溃；条漫点击翻页时页码来回抽搐跳动；平滑滚动途中页码不断闪烁回弹。
- **根因**：离屏占位组件堆砌 `backdrop-filter: blur` 与无限循环 CSS 动画引发 GPU 合成雪崩；粗暴卸载式虚拟滚动导致未知高度条漫 `scrollHeight` 突变且破坏气泡覆盖层（`ReaderBubbleOverlay`）挂载；程序化跳转期间滚动事件监听器被动触发反向覆盖当前页。
- **红线**：离屏占位骨架严禁使用 `backdrop-filter` 与无限循环动画，改用纯 CSS 静默暗色纸质背景并懒加载；严禁对长卷引入破坏 DOM 锚点的激进卸载式虚拟列表（采用 `useReaderHydration` 迟滞注水保留 DOM 外壳）；程序化跳转（`scrollToGroup`）必须挂载静音互斥锁阻断页码反向覆盖。

### 110. 阅读器胶片预览轨局部切片全局索引脱靶与浏览器修饰键穿透陷阱

- **症状**：多章节漫画第 2 话以后的胶片预览轨缩略图全量瘫痪为空白纸框；按 `Ctrl+S`/`Ctrl+T` 触发系统快捷键时被阅读器错误拦截触发全屏或跳页；日漫 RTL 模式无法居中。
- **根因**：局部过滤切片的缩略图列表将全局 `group.index` 传入基于局部窗口运行的 `isGroupHydrated` 导致越界判定脱靶；全局快捷键未校验修饰键；RTL 滚动容器坐标系为负值，正值绝对定位被归零截断。
- **红线**：滑动注水窗口校验严禁传入全局分组索引，必须传入局部循环索引 `gIdx`；快捷键监听器顶层严禁遗漏 `ctrlKey || metaKey || altKey` 修饰键前置阻断；RTL 容器滚动定位必须采用物理中心相对差值（`rail.scrollBy({ left: delta })`）。

### 111. 矮切片阅读线穿透反噬、离屏伪 100dvh 崩塌与异步撑高重排自激翻页风暴

- **症状**：16:9 拆帧漫或矮切片滚动时在当前页正中央被误判为已读完并强行跳到下一组；向上滚动时滚动条剧烈跳变并反弹回后方页码；点击 HUD 上一屏按钮视口被强行弹回。
- **根因**：滚动探测硬编码视口高度 40% 阅读线，矮切片高度小于偏置导致阅读线穿透到下一页；连续长卷误用 `contain-intrinsic-block-size: 100dvh`，离屏占位与真实矮画面尺寸倒挂 600px+ 导致布局巨幅塌陷；HUD 点击处于视口外未重置初始微调锚点。
- **红线**：连续长卷严禁使用超越画页高度的固定视口偏置（阅读线取 `Math.min(0.4 * clientHeight, 0.5 * pageHeight)`）；连续模式画页严禁使用 `content-visibility: auto` 与 100dvh 内在尺寸；所有 HUD 交互必须触发 `onUserInteract` 并在 4 秒超时后彻底自毁初始锚点。

### 112. 领域断言契约错位、跨层反向类型依赖与工具投机性泛化陷阱

- **症状**：漫画通用多章判定传入标准领域对象时静默返回 false；底层 Worker 编译报循环依赖与类型导入错误；组件中散落重复的手写类型判断。
- **根因**：领域守卫凭空假设结构，未兼容书架摘要（`chapter_titles`）与漫画详情（`meta.chapters`）字段差异；底层纯算法模块反向依赖上层 Composable 类型；缺少单一出口的工具库治理。
- **红线**：通用断言工具必须严格根据 `src/types/index.ts` 契约做多态解包；`src/utils/` 底层纯函数严禁反向导入上层 `composables` 或 `views` 的符号与类型；全站数值与类型守卫必须收敛至 `@/utils/is` 与 `@/utils/math`，拔除冗余中转导出。

### 113. 网盘层级倒置、PDF 多卷归并断层与画卷删除全链路自愈陷阱

- **症状**：网盘多级目录导入导致番外被排在正篇卷册之前；删除中间章节导致全书页码断层且阅读器报错；千页 PDF 扫描分话触发 Cloudflare 524 超时。
- **根因**：递归扫描字符自然排序导致前缀错乱；删话未重排剩余章节的 `start` 与全局页码；合订本 PDF 无目录时无界逐页运行 OCR 耗时数分钟击穿网关超时；追加/替换时将散图目录当作 PDF 路径传给探测器。详见 [ADR 0024](docs/adr/0024-pdf-comic-ingest-and-dual-track-chapter-splitting.md)。
- **红线**：合订本导入推荐单目录扁平化多卷命名；章节删除后必须压实全局单调连续页码表（1..N）；无书签 PDF 探测章节严禁全量逐页 OCR，必须限制采样步长与最大扫描页数（`MAX_OCR_SCAN_PAGES = 40`，标明为 `pdf.py:273` 的局部变量）并在提取到目录时短路早退；后端章节起始页必须由权威指针 `chap_start_page = global_idx` 强制兜底。

### 115. Vue 3 模板引用隐式解绑、双轨双向状态脱节与大体量对象深度代理风暴

- **症状**：重构重命名导致模板 DOM 引用断联失效；受控弹窗父子状态脱节且组件散落 `@update:xxx` 胶水代码；大体量藏书列表初始化卡顿与 GC 掉帧。
- **根因**：旧式 `ref(null)` 字符串耦合易脱节；手写 props/emit 双轨状态与本地镜像脱节；将成百上千本漫画对象放入深层 `ref()` 导致成千上万个 Proxy 实例引发代理风暴；组件未回收定时器与常驻全局监听。
- **红线**：模板 DOM 引用严禁使用旧式 `ref(null)`（统一收敛为 `useTemplateRef`）；父子双向状态严禁手写 `@update:xxx` 胶水与 `internalOpen` 镜像（统一使用 `defineModel`）；书架全量 items 与阅读器 detail 数据集严禁使用深层 `ref()`（必须使用 `shallowRef`）；组件卸载必须依托 `useTimeoutFn` 与 `onWatcherCleanup` 实现休眠期 0 监听。

### 116. 单子元素下 space-between 空间坍塌与本地车号 LOC_loc_ 叠字口吃

- **症状**：自建漫画卡片底部缓存进度条因缺失浏览量突兀靠左对齐，书架排版撕裂；自建车号显示为丑陋的 `LOC_loc_2026...` 双重前缀。
- **根因**：Flexbox 单子项下 `justify-content: space-between` 规范退化为 `flex-start`；自建生成 `source_id` 已带 `loc_`，前端格式化印章时又拼接一层 `LOC_`。
- **红线**：子元素数量动态变化的 Flex 容器中锚定右侧项严禁依赖默认对齐（必须显式赋予 `.card-progress { margin-left: auto; }`）；自建漫画 `source_id` 严禁内置 `loc_` 前缀，印章统一为 `LOC_{source_id}`（上传走时钟，路径导入走文件夹名，详见 ADR 0027）。

### 117. 外部创作平台 API 契约与本地分卷暂存流水线解耦、URL 响应式污染与深层直达失衡

- **症状**：外部平台自动化入库接口被误删报错；书架筛选打字或切标签时触发 `NavigationCancelled` 异常且历史栈抖动卡顿；原生 Popover 进场动画缺失生硬跳变。
- **根因**：将外部创作者平台（Paper Studio）的 Machine API（`POST /create`）与内部暂存 PDF 管道混淆；书架筛选响应式循环中高频调用 `router.replace` 污染历史栈；原生 Top Layer 浮层只声明 `allow-discrete` 未配置 `@starting-style`。
- **红线**：严禁废弃外部平台 Machine API 契约 `POST /api/library/local/create`；书架筛选严禁在输入循环中高频调 `router.replace`（内存为 SSOT，仅挂载时单向恢复，分享走显式复制直达链接）；原生 Top Layer 离散过渡必须显式声明 `@starting-style`。

### 118. 多图源鉴权凭据落盘 TOCTOU 权限真空、SSRF 端口/畸形 IP 绕过、并发重登惊群与 CDN 候选池兜底反向放行

- **症状**：敏感 Token 在 NAS 上以 0644 暴露；SSRF 白名单被 `evil.com:80@127.0.0.1` 绕过；会话过期并发预取触发官方验证码或 IP 封禁；日志泄漏明文密码。
- **根因**：写文件后异步调用 `chmod` 存在 TOCTOU 窗口；域名校验前先剥离端口导致 `@` 凭据注入穿透，未阻断点分十进制变形；并发重登缺少锁内时间戳复检；CDN 降级池在全被拦截后兜底放行原始恶意域名。详见 [ADR 0025](docs/adr/0025-jmcomic-auth-proxy-decoupling-and-multi-cdn.md)。
- **红线**：敏感凭据持久化严禁先写后 `chmod`（必须在基类通过 `os.open(..., 0o600)` 原子创建并替换）；SSRF 校验必须先阻断 `/?#@%` 再剥离端口并校验合法主机名；并发重登入锁后必须做 15s 冷却复检；容灾候选池全灭时严禁兜底放行未经检验的域名；日志严禁记录明文密码与代理凭据。

### 119. 禁漫 AVS 会话与网页客户端分流错配导致假下架，以及操作级 RPC 污染全局状态引发 Toast 双重弹窗

- **症状**：禁漫受限漫画已登录仍被 302 拦截判定为下架死锁；单次导入/编辑失败在右下角同时弹出两条一模一样的错误 Toast。
- **根因**：移动端登录产出 `AVS` Token，后端却写死用不认 AVS 且需验证码的 HTML 客户端拉取；操作级 RPC 失败向全局 `store.error` 写入局部错误触发全局 watch 弹窗，同时局部 catch 又显式弹窗，且 `useToast` 缺少短时去重。详见 [ADR 0025](docs/adr/0025-jmcomic-auth-proxy-decoupling-and-multi-cdn.md)。
- **红线**：第三方图源拉取必须 API 客户端优先（识别 AVS、免验证码）并以 HTML 为容灾降级；操作级 RPC 异常严禁写入全局 `store.error`（仅局部捕获展示）；`useToast` 必须以 1.5s 窗口对同一 `(text, tone)` 实施幂等去重并刷新定时器。

### 120. 图像分析中未统一色彩空间导致调色板与非标准格式极值误判

- **症状**：PDF 空白衬页与单色黑白页被误判为非单色内容未被过滤，或不同颜色被误判为单色。
- **根因**：直接对 PIL `Image` 对象调用 `getextrema()` 时未统一色彩模式，在调色板（`mode="P"`）或 CMYK 下返回的是调色板索引极值而非真实 RGB 发光像素值。
- **红线**：严禁在未规范化色彩空间前对图像的 `getextrema()` 结果直接做明暗或均一性判定；基于像素极值的算法必须前置执行 `im.convert("RGB")` 标准化为 24 位 RGB 后再分析。

### 121. 单测黑盒契约与测试生命周期隔离

- **症状**：组件代码重构内部状态时单测发生假阳性崩溃；测试用例偶发超时（Flakiness）或因全局 Fake Timers 未清理污染后续套件。
- **根因**：单测通过 `wrapper.vm.*` 直接访问组件私有状态破坏黑盒原则；测试中使用真实延时宏任务 `setTimeout` 或裸调 `vi.useFakeTimers()` 在断言失败后未执行恢复。
- **红线**：单测严禁访问私有 `wrapper.vm.*`（坚持以公开 DOM、ARIA、Props 与 Emits 为断言依据）；严禁在单测中使用真实 `setTimeout`；假时钟与 Mock 必须在 `beforeEach`/`afterEach` 中严格对称管理（`afterEach` 必调 `vi.useRealTimers()` 与 `vi.restoreAllMocks()`）。

### 122. 局域网纯 HTTP 访问缺少安全上下文导致 WebMCP / document.modelContext 无法注册与失效

- **症状**：本地开发时 WebMCP 工具注册正常，但通过局域网 IP（`192.168.x.x`）纯 HTTP 访问时 `document.modelContext` 为 `undefined` 且工具无法注册。
- **根因**：Chromium 规范将 WebMCP 列为高权限特性，强制要求安全上下文（`isSecureContext === true`）；`localhost` 天然受信任，但局域网纯 HTTP 被判定为不安全环境直接隐藏该 API。
- **红线**：严禁在局域网纯 HTTP 环境误判 `document.modelContext` 缺失为打包 Bug；前端必须保留 `?.` 可选链防御；局域网调试通过 `chrome://flags/#unsafely-treat-insecure-origin-as-secure` 放行，生产部署必须挂载 SSL 证书推进全站 HTTPS。

### 123. 路由过渡前置滚顶污染 HTML5 历史快照导致书架返回归零

- **症状**：在漫画详情页点击“返回书架”或浏览器后退时，书架滚动条总是回到最顶部，丢失先前的浏览位置。
- **根因**：在路由跳转尚未完成离开前（如 `beforeResolve` 或点击时）过早调用 `window.scrollTo(0, 0)`，污染了当前页在 `window.history.state` 中的滚动快照；Vue Router 接收到错误的 `{ top: 0 }`。
- **红线**：严禁在路由跳转离开前裸调 `window.scrollTo(0, 0)`；路由滚顶必须交由 `router.options.scrollBehavior` 调度；书架核心视图必须由单例状态机（`useShelfState().shelfScrollY`）记录真实位置并在返回时最高优先级复原。

### 124. SegmentedTabs 双向绑定与 `@change` 守卫冲突导致 Tab 切换被吞

- **症状**：点击 SegmentedTabs 选项有高亮切换动画，但完全不触发数据加载与网络请求。
- **根因**：子组件通过 `defineModel` 在点击时先执行了 `modelValue.value = key`，父组件在 `@change` 回调中若包含 `if (source.value === key) return` 防重复守卫，判定恒为 true 导致数据加载被静默拦截。
- **红线**：严禁在消费 `defineModel` 组件 `@change` 事件的处理函数中编写 `if (state.value === val) return` 防重复守卫；防重仅校验请求并发状态（`loading`/`refreshing`），切换源时主动重置过期 `feed`。

### 125. 外部 Provider 榜单接口隐式必填参数遗漏

- **症状**：哔咔排行榜拉取报错 HTTP 502 Bad Gateway，或缩略图拼接出 `static/static/` 导致 404 挂图。
- **根因**：哔咔官方排行榜接口必须携带类别参数 `ct`（如 `VC`），仅传时间跨度 `tt` 触发上游 400 校验错误；缩略图路径前缀存在已带与未带 `static/` 两种格式。
- **红线**：调用外部非公开反代 API 严禁仅凭直觉传参，必须严格核对抓包协议与必填参数（哔咔榜单固定附带 `ct="VC"`）；图源缩略图路径拼接前必须校验 `thumb_path.startswith("static/")` 做前缀规范化。

### 126. 外部图源 Web 阅读器与 API 移动端域名分流漂移陷阱

- **症状**：点击“原站预览”跳转哔咔漫画时浏览器报错无法解析或证书脱靶；历史缓存中留存失效的旧域名。
- **根因**：哔咔官方域名 `picacomic.com` 仅用于移动端 API，面向 Web 浏览器的镜像域名为 `picawang.com`；外部链接散落组件各处且历史缓存未自愈。
- **红线**：严禁将用于移动端 API 签名的网关域名直接作为前端浏览器外链；全站外部跳转链接必须在 `src/utils/source.ts` 中单源收敛；存储层加载榜单缓存时必须自动检测旧域名并纠偏原子回写。

### 127. 榜单高频轮替临时图片落盘引发孤儿碎片与磁盘膨胀

- **症状**：发现页浏览排行榜后大量临时封面残留在 NAS 磁盘上无法回收，或前端直连远端图片触发防盗链与 CORS 挂图。
- **根因**：发现页排行榜为 12 小时高频轮替数据，为全量未收录作品自动下载封面会导致无主孤儿文件与上游 CDN 限流封禁；直接访问远端图片缺少 Referer 伪装。
- **红线**：严禁将发现页排行榜未收录作品的临时封面写入 `backend/data/` 物理磁盘；排行榜封面必须按需查看，后端设立上限 100 张、TTL 1 小时的纯内存 LRU 代理端点（`GET /api/discovery/cover`），出期自然逐出，磁盘 0 残留。

### 128. FastAPI Query 参数直接在单测调用时的对象类型断层

- **症状**：单测直接调用 FastAPI 路由函数时抛出 `AttributeError: 'Query' object has no attribute 'strip'` 崩溃。
- **根因**：在单测中直接调用路由函数且未传递某个 Query 参数时，形参不会自动解析为 `None`，而是拿到函数签名上的默认值对象 `fastapi.params.Query` 实例。
- **红线**：可调用的路由函数内部严禁对可选 Query 参数直接调用字符串方法；参数签名推荐写为 `param: str | None = None`，或在函数体内使用 `param.strip() if isinstance(param, str) else ""` 安全防御。

### 129. 漫画移除影子索引遗漏与全链路级联清理缺陷

- **症状**：书架删除漫画后刷新列表该书重新浮现，必须点两次才彻底删掉；在途下载任务使已删漫画复活；离线模式下又把已删漫画逆向注水到书架。
- **根因**：删除接口仅删物理文件与台词，遗漏了 SQLite `comics_index` 影子索引的注销；在途下载任务未熔断并在 `finally` 阶段重建了索引；前端 IndexedDB 离线快照未同步清理。
- **红线**：严禁在移除作品时仅执行物理文件删除；必须通过 `purge_comic_db_records` 原子级联清理影子索引、台词 FTS、进度、喜欢与单本通行证；删书前必须调用 `cancel_job` 熔断后台任务，前端必须同步清理 IndexedDB 离线快照。

### 130. 通用服务端 MCP 工具过度暴露与概率性越权反模式

- **症状**：大模型在长对话、间接提示词注入或歧义讨论下误调写工具，导致私有书库被意外写入、全本缓存耗尽带宽或藏书被删。
- **根因**：大模型行为具备概率性，服务端 MCP 暴露了添加入库、全本缓存、删除等非幂等重型写工具，且通用 MCP 管道无法区分具体人类说话人。
- **红线**：通用服务端 MCP（`/mcp/sse`）严禁注册任何具有破坏性、非幂等或高消耗的写工具（必须坚守纯只读与沙箱外链签发定位）；外部 Bot 机器人若需支持推书入库，必须由 Bot 代码在调用前执行确定性身份校验（`sender_id === CURATOR_ID`）再调后端 REST API。

### 131. 临时通行证会话 Cookie TTL 错配与边缘 CDN 越权穿透陷阱

- **症状**：单本临时通行证（如 2 小时）在服务端数据库过期删除后，访客仍能持续通过浏览器读取 Cloudflare 边缘缓存的漫画画页。
- **根因**：后端设置鉴权 Cookie 时硬编码默认 30 天 `max_age`；Cloudflare WAF 只要放行有效 Cookie，Anycast 边缘节点就直接从 Edge 缓存返回图片，根本不回源校验 Token。
- **红线**：临时通行证与有时效读者证严禁写入固定 30 天 `max_age` 的会话 Cookie（必须与服务端 Token TTL 动态对齐自毁）；严禁假设服务端单方删除 Token 即可防住边缘 CDN 缓存；前端换取 Cookie 后必须用 `replaceState` 剥离 URL 携带的临时 token。

### 132. 组合式函数多态返回类型逃逸与空对象样板代码陷阱

- **症状**：Composable 在早退分支使用 `as any` 导致调用方丢失 TypeScript 自动补全与类型检查，或手写冗长平铺的 `undefined` 字段字典。
- **根因**：为了平息 TypeScript 返回类型不匹配报错而粗暴逃逸，或者手工维护所有工具属性的空对象字面量造成样板代码膨胀。
- **红线**：Composable 早退分支严禁使用 `as any` 逃逸，亦不可手写全量 `xxx: undefined` 假对象字典；必须基于映射类型定义通用泛型（如 `WebMCPComposableReturn<K>`），使早退分支能单行 `return { isSupported: ref(false) }` 且类型安全。

### 133. 非 DOM 响应式变量的匈牙利命名误导与缝合别名反模式

- **症状**：纯数字页码变量被命名为 `progressEl` 引起类型与理解误导；重构后函数内部写 `const lastReadPage = progressEl` 产生冗余影子别名。
- **根因**：错误将用于指代真实 DOM 节点的 `*El` 匈牙利后缀用于非 DOM 变量；重构时为了避免破坏下游调用而在函数体内部做影子赋值缝合。
- **红线**：严禁给任何非 DOM 变量（数值、字符串、布尔）添加 `*El` 后缀；严禁在函数作用域内书写同名影子桥接别名；内部变量直接采用正统语义名，仅在 Composable 导出边界挂载 `@deprecated` 兼容属性。

### 134. tempfile.mkstemp 0600 权限锁死与 NAS 跨卷原子写入陷阱

- **症状**：Docker 容器写入 NAS 挂载卷后 Windows/普通用户报 `Permission denied`（`-?????????` 乱码）；文件替换时报 `EXDEV: Invalid cross-device link`。
- **根因**：`tempfile.mkstemp` 底层强制 0600 权限；临时文件写在系统的 `/tmp` 目录而目标位于 NAS 挂载点，跨物理设备导致 `os.replace` 丧失原子性并抛出 EXDEV。
- **红线**：多端/NAS 共享持久化存储严禁使用 `tempfile.mkstemp`；用于原子替换的临时文件严禁写在不同挂载卷下（必须在目标文件同目录下创建隐藏临时文件，继承宿主 umask，`fsync` 刷盘后同卷 `os.replace`）。

### 135. 路径导入封面选择器被未知页数锁成 1/1/1/1

- **症状**：自建工坊切到“服务器目录导入”时，封面页码无法填写真实画页（如 25），输入后被自动强制纠偏打成 1/1/1/1。
- **根因**：前端将“暂存张数尚未读取”误当成“整本书只有 1 页”，默认给 `CoverIndicesPicker` 设置了 `maxPage: 1` 注入 HTML `max=1`，失焦纠偏强制打死。
- **红线**：严禁将上传暂存文件的 `|| 1` 回退值用于封顶路径导入；`CoverIndicesPicker` 省略 prop 时必须表示未知页数（`maxPage: null`，不封顶），仅已知页数时才施加封顶；越界页码创建时原样写入，读取时由后端夹取。

### 136. 常驻 --reload 开发服务在保存瞬间对真库执行破坏性迁移

- **症状**：保存 `backend/app/db.py` 的瞬间，真实数据库 `comic_dialogues.db` 的派生台词索引当场清零，且单测全绿无法发现。
- **根因**：`backend/server.py --reload` 在保存文件瞬间热重载触发 `init_db()`，未做列集合包含判定直接执行 DROP TABLE 重建但未带自动回填；单测全部在 temp 隔离目录运行掩盖了开发库故障。
- **红线**：修改台词 schema 与迁移逻辑前必须确认无 `--reload` 服务在跑；严禁将派生索引 `comic_dialogues_fts` 当作有状态原件；迁移判据必须写成列集合包含判断（缺列才重建），且重建必须自带 `backfill_dialogue_index` 自动回填与核验三连。

### 137. OCR 算力机 GPU 的三段静默失效链

- **症状**：台词 OCR 安装了 GPU 依赖但速度依然是 CPU 慢速（掉速 4 倍），且没有任何报错。
- **根因**：CPU 与 GPU 版 onnxruntime wheel 共用同一目录，后装覆盖导致 `CUDAExecutionProvider` 虽列出但建会话静默退回 CPU；缺失 CUDA/cuDNN 的动态库未加入 `LD_LIBRARY_PATH` 时静默回落；WSL2 下 `nvidia-smi` 路径未探测导致误判为纯 CPU。
- **红线**：严禁拿 `get_available_providers()` 当作 GPU 生效依据，必须真建会话看 `get_providers()[0]`；同一环境严禁 CPU 与 GPU 版 onnxruntime 并存（GPU 安装前必须整目录删除原包）；GPU 缺失或回落 CPU 必须显式打出原因并由 `build_engine(True)` 抛错阻断，带卡机器严禁将 CPU 设为默认算力线。

### 138. `git clean -xdf` 会把整个书库连同派生索引一起删掉

- **症状**：运行常规清理命令后，书库所有原图、`album.json`、OCR 伴生文件及数据库全部消失被删库。
- **根因**：`.gitignore` 忽略了 `backend/data/**`，而 `git clean -x` 语义是连带被 ignored 的文件一起删除。
- **红线**：全仓库严禁运行 `git clean -x*`（清理未跟踪文件只能用不带 `-x` 的 `git clean -df`）；清理构建产物必须点名删除（`rm -rf dist .venv-ocr`）；牢守核心不变量 1，严禁以任何方式删除 `backend/data/` 目录。

### 139. 台词索引的两处"静默不一致"：写删键分叉与计数随身份变

- **症状**：传入脏 ID 时台词能定位读取但删书后留下永久孤儿台词；同一本书同一页在访客与馆长界面显示的命中气泡数不一致。
- **根因**：定位目录用清洗后的安全名，而写库与删除用调用方原始 ID 或目录名导致键分叉；候选池 `fetch_limit` 原按身份分档，导致池内截断的 `bubble_count` 随身份变化。
- **红线**：同一张表的定位、写入与删除必须共用唯一定位函数 `_dialogue_key()`；命中数与统计字段严禁依赖访问者身份分档（`fetch_limit` 统一为 `min(max(limit*5, 50), 200)`）；评分标尺 `visible_scores` 仅取当前身份可见行以防泄露隐藏藏书。

### 140. 只删包目录不卸发行版：pip 报"已满足"，留下 import 即失败的空壳环境

- **症状**：安装脚本一路跑通，但运行时报 `ModuleNotFoundError: No module named 'onnxruntime'`，而 `pip list` 明明显示包已安装。
- **根因**：脚本仅删除了包目录，但下划线命名的 `onnxruntime_gpu-*.dist-info` 元数据仍残留，导致 pip 误判为已满足安装条件而跳过文件写入。
- **红线**：清理共用包目录必须遵循先 `pip uninstall -y` 彻底卸载、再物理清理残留目录、最后全新安装的完整链路；安装后必须执行真机 `import` 验证物理路径；跨版本清理 glob 必须同时匹配连字符 `-` 与下划线 `_`。

### 141. 一行噪声替整页定性：已单独丢弃的行不该有页级判据的权力

- **症状**：剧情漫画正文尾页完全搜不到台词，真库实测 60 页/119 行被误杀。
- **根因**：页级副文本分类判据包含 `_is_noise_line`，而噪声行自身已被丢弃不入库，却因单行水印/页码噪声将整页正常对白全部判为不可检索的副文本。
- **红线**：两级判据中，第二级页级定性的证据集合必须先按第一级单行过滤结果剔除，被丢弃的行严禁参与页级判定；判据改动后只需通过 `scripts/sync_ocr.py --force` 重新灌库即可秒级生效。

### 142. 相对间距 + 传递闭包 = 整页糊成一个气泡：链条式误并

- **症状**：对白、拟声词与单字噪声被合并为一个巨大气泡覆盖 50% 页面积，阅读器高亮遮住半页画面。
- **根因**：聚类算法采用相对自身尺寸的间距判据，且并查集计算传递闭包，导致大框连大框、横排连竖排在画面中拐角接力链条式误并。
- **红线**：聚类必须施加三道硬否决闸：同向（横/竖）才许同组、笔画粗细比 $\le 2$ 阻断拟声词与大标题、合并后分量外接框面积 $\le 20\%$；聚类调优必须基于原始行 dump 离线快速秒级评估，严禁重跑 GPU 推理。

### 143. 把"大图降采样"当免费提速杠杆：默认早降过了，再降就掉台词

- **症状**：降低 OCR 图像尺寸试图提速时整句日文台词丢失或乱码；端到端字数差异掩盖单句漏识。
- **根因**：RapidOCR 预处理默认已将长边降采样至 2000，进一步降低尺寸会直接导致细小文字特征丢失；90% 以上耗时在 ONNX GPU kernel 内部，换用语言无法解决文本分组后处理缺陷。
- **红线**：明确记录“已结案、别再提”三条禁令：① 否决大图降采样（默认已压至 2000，再降提速无收益且掉字，配置保持默认）；② 否决换用 Rust OCR（已重测确认 Python/ONNX 足以支撑性能，且跨进程通信开销得不偿失）；③ 否决两步式文字行重切分；验证模型质量必须逐串 diff 而非只看聚合字数。

### 144. 裸 MagicMock 当 Request：`state` 的自动属性让鉴权用例全绿却什么都没验

- **症状**：鉴权逻辑修改后单测全绿，真机部署却在事件流接口当场报 401 鉴权失败。
- **根因**：`get_user_context` 优先读取 `request.state.user_context`，而裸 `MagicMock()` 自动为任何属性返回 Mock 对象，导致代码走入意外分支，实际上根本未经过鉴权校验。
- **红线**：单测请求替身严禁使用裸 `MagicMock()`（必须挂载普通属性对象 `req.state = type("State", (), {})()`）；新加鉴权判据后必须做故意改坏的变异验证；鉴权出口测试优先使用 `TestClient` 走真 ASGI 栈（无限流握手改用直接 await handler）。

### 145. 常驻 `--reload` 把半截迁移灌进真库：新列全 NULL，而 `sync_meta` 认定它已经同步好了

- **症状**：台词检索接口整体返回空，但数据库总行数正常、元数据完整，真库 8095 行新列全为 NULL。
- **根因**：开发时常驻 `--reload` 服务，修改代码保存瞬间服务重启，用旧的 INSERT 往新加列的表中回填导致新列全为空，随后写入 `last_synced_mtime` 误将半成品索引认证为已同步。
- **红线**：给派生表加列时严禁在 `--reload` 常驻时分步保存（先改写入侧再改 schema，必要时停掉 reload）；迁移后必须严格校验新列非空（`WHERE <col> IS NULL` 为 0）；出问题必须调用 `db.backfill_dialogue_index(force=True)` 绕开增量元数据强制重灌，严禁手删数据库文件。

### 146. FTS5 trigram 的两条硬边界：两字查询没有 token，`bm25()` 不认别名

- **症状**：两字高频词在 FTS5 中检索一律返回 0 行，或排序报错崩溃。
- **根因**：SQLite FTS5 trigram 分词只产出 $\ge 3$ 字符 token，两字词无论如何改写均无法命中倒排索引；`bm25()` 函数入参只识别完整虚拟表名，传入 SQL 别名会抛错。
- **红线**：两字短词查询严禁试图通过通配符改写走 MATCH（必须走带限制的 LIKE 扫描并按 `词频 ÷ 长度` 排序）；`bm25()` 必须使用完整表名 `bm25(comic_dialogues_fts)`；相关度归一化必须在本次候选池内取 min/max，严禁写死满分常数。

### 147. 长耗时计算或物理 I/O 霸占 SQLite 事务：并发线程与跨进程写锁饿死下游

- **症状**：同步 OCR 伴生台词或后台清扫时，整个服务瞬间卡顿，前端读者翻页、保存阅读进度或点赞红心大面积报 `sqlite3.OperationalError: database is locked`。
- **根因**：在 `with get_dialogue_db() as conn:` 事务包裹期间执行了 CPU 密集的 ONNX 向量推理（`embedding.encode_documents`）或耗时的文件系统孤儿扫描（`is_dir()` 探测），导致写锁被长时间独占，阻塞其他工作线程与连接。
- **红线**：严禁在 SQLite 事务上下文内部执行耗时超过 5ms 的 CPU 密集计算（如神经网络推理、特征编码）或物理文件系统 I/O 遍历；必须采用「读出数据 → 退出事务 → 纯内存计算/磁盘检测 → 开启事务批量写入」三段式架构，事务内只留纯 SQL 执行。

### 148. 无界内存防爆破追踪与 Vue Router 数组查询参数穿透

- **症状**：后台常驻服务在遭遇扫描器海量随机凭据探测后内存持续缓慢泄漏；阅读器在某些外部重定向附带重复 query key 时气泡高亮全部失效。
- **根因**：防爆破记录（`_login_failed_history` / `_login_failed_creds`）只在失败时追加但未设常态化 TTL 批量驱逐，过期键无限驻留内存；Vue Router 解析 `?bubble=1&bubble=2` 时将值解析为数组，而清洗函数假定只接收纯字符串，导致类型断言失败整条丢弃。
- **红线**：所有基于内存字典的限流/防爆破容器必须内置带容量触发的 TTL 惰性清扫（`_prune_stale_login_tracking`）；前端解析 URL 查询参数（如 `parseBubbleBox`）必须前置考虑数组入参（`Array.isArray(raw) ? raw[0] : raw`），确保参数容错性。

---

## 🚦 交付门禁

详见 [AGENTS.md](../AGENTS.md) 交付门禁与各模块专属文档。
