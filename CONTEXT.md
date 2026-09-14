# CONTEXT.md — 纸间 · Paper Room 领域术语表

> 本项目只有一份 context（单体前端 + 后端）。本文件是纯术语表，不含实现细节。
> 术语达成共识后即时更新；ADR 单独放 `docs/adr/`。

## 品牌与定位

- **纸间（Paper Room）**：产品名。定位是"本地优先的个人漫画收藏夹"，不是公开站点，也不是泛化爬虫。
- **私人阅览室 / 卡片目录（Reading room / Card catalog）**：产品视觉语言的隐喻——暖纸色、墨色、朱砂色，像图书馆卡片与旧书脊；明确禁止紫色渐变、玻璃拟态堆叠、霓虹、emoji 当图标。
- **动态看板头像（Dynamic Brand Icon）**：浏览器标签页 Favicon 与应用顶栏（`AppHeader` / `GateView`）的随机形象轮换机制。每次刷新页面时从预设头像池挑选，仅作用于活跃网页会话内部装饰，严禁篡改系统级桌面图标。
- **PWA 桌面图标（PWA App Icon / Apple Touch Icon）**：读者将纸间添加到操作系统主屏幕时的系统级独立应用门面。由静态 180×180 / 192×192 PNG（`apple-touch-icon.png` 与 `pwa-*.png`）与 Web App Manifest 固化定义，具有跨会话的绝对确定性，严禁随网页刷新而动态漂移。

## 核心概念

- **本子（Comic / Book）**：书库里的一条漫画作品记录。用户视角的"一本"。
- **车号（display_id）**：作品在来源站点的唯一编号（如禁漫 `523607`，本地自建 `LOC_tiya-frames`），是"放进纸间"时用户需要输入或生成的标识。`display_id` 与 `source` 组合才是全局唯一。
- **来源（Source / Provider）**：作品的远端或本地出处（`jm` 禁漫、`local` 本地自建/本地目录导入、`picacg` 哔咔）。每个来源有独立的 `short_label`、编号格式、数据目录 `library/<source>/<source_id>/`。
- **本地自建漫画（Local Comic）**：由用户直接上传图片文件或指定服务器已有文件夹（如视频拆帧目录）收录生成的作品。`source = "local"`，无远端依赖，直接持久化于 `library/local/<source_id>/`。
- **哔咔漫画（PicAcg Comic）**：由哔咔数据源收录的作品。`source = "picacg"`，使用 24 位十六进制 ObjectId 标识；逆向协议与端点单一权威参考 `https://github.com/wgh136/PicaComic`；画卷原生为标准 JPEG/PNG 格式，不设切片混淆但需分流鉴权；封面策略首图优先采用官方 `thumb` 并转码 720px/360px WebP，续接正文前 3 页构成书架 4 叠牌展开。
- **收录（Import）**：把一本作品"放进纸间"的动作。规则：先查本地 `album.json`，命中则 `from_cache=true` 绝不请求远端；首次收录缓存前 4 页做封面。本地自建漫画收录时即时生成封面与缩略图。
- **服务端本地化（Server-side Caching / Cachify）**：把页面图片下载到服务器本地磁盘（`backend/data/library/`，对应 `cached_pages` / `cache_complete`）。图片必须走解密工具，禁止直接保存下载字节；本地自建漫画页面在导入时即为 100% 本地化。此概念属于后端存储范畴，严格区别于移动/浏览器端的离线运行状态。
- **批次增量预缓存（Paged Batch Prefetch / Stepped Server-side Caching）**：针对单本总页数超出单次下载配额上限（`MAX_PREFETCH`，默认 600 页）的超长连载漫画，在触发全本本地化时建立的步进式顺延调度机制。系统通过探查磁盘与元数据，按全局页码从小到大提取未缓存（`cached === false`）画页切片取前 N 页执行下载；单批完成后全书若尚未全部就绪，维持未终态并支持馆长在详情页再次点击“缓存全部”顺延下一批，直至全本 100% 本地化。与远端发布新章节时的「增量更新（Incremental Refresh）」严格解耦。
- **并发上传队列（Concurrent Upload Queue）**：批量上传大量图片（如数百张拆帧图）时的客户端流量阀门。采用受限并发（3~4 路）分批推送到后端，兼顾上传速度与服务器连接稳定性。
- **画卷文件暂存区（Staged File Rack / File Staging Drop Zone）**：在自建工坊（`CreateComicView`）、重新装订（`ReplacePagesModal`）与追加页面（`AppendPagesModal`）中用于批量暂存新画页的双模输入容器。支持网页多图拖拽暂存与服务器本地目录就地扫描；对暂存图片执行基于文件名自然序号的排序、首尾页码概要校验与批量清空，并将拖拽悬停与点击唤起文件选择对话框统一封装收敛。
- **封面（Cover）**：作品的预览图，默认取自首页前 4 页，或由馆长自定义指定 4 个全局页码序号（`cover_indices`）；书架卡片与详情页轮播的视觉锚点。
- **自适应封面轮播与直达居中（Snap-aligned Coverflow with Direct Centering）**：详情页顶部多封面浏览微件。保持原生 CSS `scroll-snap` 物理吸附特性的同时，以显式索引跟踪替代模糊步长猜测；支持点击侧边露出卡片就地直达居中，箭头按钮按序步进并在端点自适应禁用，彻底消除 3D 透视缩放导致的步长失真与多点一次故障。
- **封面序号自定义（Cover Indices）**：允许馆长在自建工坊或编辑资料弹窗中显式指定 4 个全局页码序号（如 `[1, 10, 25, 50]`），书架与详情页轮播卡片将按此顺序展示这 4 张页面作为封面。
- **双模增量封面（Dual-Format Incremental Cover Cache）**：纸间封面缩略图的持久化缓存策略。书架与章节封面同时支持 `.jpg` 与现代 `.webp` 格式，基于客户端 `Accept` 请求头透明协商；当磁盘缺失 `.webp` 时就地增量生成并物理落盘，后续请求 100% 毫秒级直读。
- **全生命周期封面预热（Active Cover Pre-warming）**：系统在作品导入、更新封面（`cover_indices`）、重绑归档及后台异步预热（`prefetch_comic`/`prefetch_chapter`）时，即刻物理生成对应页面的 `360px` 与 `720px` 双模（WebP + JPEG）缩略图，彻底消除书架与详情页冷启动延迟。
- **喜欢（Favorite）**：给一本作品打上的"已喜欢"标记，可用来筛选（只看喜欢）。
- **页面索引（Page index）**：详情页展示所有页码缩略图的区段，点击任意页直接进阅读器；为性能按 24 页分批增量呈现。
- **画卷折叠架（Collapsed Thumbnail Rack）**：页面索引与书架网格中，将超出视觉行数预算的项进行物理折叠收纳的容器槽位；搭配尾格余量徽印与控制胶囊，实现从容的主动展开体验。
- **尾格余量徽印（Overflow Tile Badge / +N 徽印）**：折叠状态下当前可见批次最后一个卡片/图块上浮现的半透明水墨磨砂遮罩与朱砂印章，标明 `+余 N 页` 或 `+余 N 本`，读者点击该图块即可就地触发步进铺开。
- **步进展开与全量展开（Stepped & Full Unfold）**：画卷与书架的展开动作规范，提供“再看 24 页/12 本”（渐进探索）与“展开全本/全架”（一览无余）的双轨操作，并支持“收起画卷”回退。
- **滚动逃逸根治（Runaway Scrollbar Mitigation）**：彻底阻断传统基于长距离 IntersectionObserver 哨兵引起的无节制贪婪自动追加，将页面纵向滚动条的主动掌控权交还读者，维持页面紧凑与内存可控。
- **书架增量呈现（Shelf Chunked Rendering / 48 图预算）**：书架首页因每本漫画包含 4 张展示封面（1 主封面 + 3 叠牌封面），采用 12 本/批（严格对应 12 × 4 = 48 张封面图）的增量渲染机制；首屏固定 12 本并由尾格折叠卡收纳后续藏书，将首屏 DOM 与解码压力控制在 48 图预算内，彻底避免 `content-visibility: auto`（`contain: paint`）在卡片 Hover 浮动时的像素硬截断与阴影死黑。
- **章节（Chapter / 話）**：一本多话合集里的一个独立 photo。模型上每章有 `{id,index,title,page_count,start}`，
  `start` 是该章在**全书全局页码**里的起始页。多话作品详情页按「章节目录」摆放（封面 + 章节信息），
  点某话进入「章节子路由」看该话页索引；阅读器页码/继续阅读/封面仍走全局页码。单章节作品 `chapters` 为空。
- **章节子路由（Chapter Sub-route / ChapterView）**：多话漫画单个话的独立专注页面（`/comic/:source/:sourceId/chapter/:chapterId`）。承载本话的页面索引、章节导航条、单话缓存触发与画页管理，与详情页目录形成层级呼应。
- **章节视口居中定位（Chapter Viewport Centering / Instant Center Anchor）**：章节子路由详情（ChapterView）中的横向章节切换条（ChapterSwitcher）在读者初次载入或从阅读器退出返回时，通过视口相对几何差值计算将当前激活话的卡片瞬间无感居中（Instant Jump）；在同级切话与键盘交互时平滑平移（Smooth Scroll），确保长篇多话作品在任何切入链路下均能即刻看见当前话与前后文脉络。
- **层级树状导航与下级路由防卫（Hierarchical Up Navigation & Downward Navigation Guard）**：纸间路由体系基于四级树状面包屑（Rank 1 书库/发现 ⇄ Rank 2 本子详情 ⇄ Rank 3 章节子路由 ⇄ Rank 4 阅读器）建立的确定性导航契约。区分“向上层级导航（Up Navigation）”与“历史时序后退（History Back）”：
  1. 章节子路由向父详情返回时采用「来源感知出栈 + 替换兜底」，上一页为父详情时出栈还原滚动与折叠，否则就地替换（`router.replace`），严禁 push 污染历史栈；
  2. 章节子路由内同层切话使用 `router.replace` 维持单话专注视口，杜绝历史栈爆炸；
  3. 本子详情页对返回按钮挂载下级路由拦截守卫，当历史上一页指向本漫画的下级子路由（章节/阅读器）时禁止 `router.back()`，兜底回退至书架，彻底消除下级回弹死循环。
- **单话按需离线（Chapter-level Caching / Cache by Chapter）**：多章节漫画支持在章节卡片与章节详情页触发针对该单话的后台图片下载任务，弥补“全本预缓存（MAX 600页）”在超长作品（数千页/上百话）下的粗粒度缺陷与反爬风险。
- **缩略图落盘即缓存（Thumbnail Implied Page Caching）**：页面索引网格请求画页缩略图时，后端解密拉取原图生成缩略图并即刻将该画页标记为本地化（`cached = true`）；前端感知缩略图加载完成即刻乐观翻转「本地」印章并推进单话进度，消除“明明图片已加载却显示待缓存”的认知割裂。
- **未达终态不进位法则（Non-terminal Floor Clamp / 99% 封顶律）**：全站所有缓存进度条与百分比计算（`AppProgressBar`、`CacheProgress`、`DetailActionBar`）遵循的确定性语义契约。只要当前任务尚未达到完全就绪终态（`cached < total` 或 `complete === false`），百分比显示严格封顶为 99%（向下取整 `Math.min(99, Math.floor(...))`），当且仅当全部就绪（`cached >= total`）时才允许显示 100%，彻底根除“数字显示 100% 却提示差一页未入库”的认知断层。
- **本地落盘自愈对齐（Local Cache Reconciliation）**：在拉取本子详情（`/api/library/{source}/{source_id}`）或请求缓存进度时，后端执行轻量自愈检测：针对 `page.cached === false` 的画页探查磁盘对应图片文件是否已完整存在，若已落盘则即刻修正元数据与数据库并翻转为本地化，彻底消除因阅读器直读或网络抖动导致的磁盘与元数据失步。
- **防爬节流与并发阀门（Anti-Scraping Pacing & Concurrency Gate）**：针对远端图源（如哔咔、禁漫）设立的并发保护屏障（`download_gate` 默认 3 路并发）与拟人化随机抖动延迟（`PICA_DOWNLOAD_PACING_MS = 250ms ±20%`），杜绝批量拉取缩略图或画页时触发远端 IP 封禁。
- **章节相对页码（Chapter-relative Page Index）**：多章节作品中面向读者展示的章内相对页码（`local_page = global_page - chapter.start + 1`，如第 3 话第 2 页，全书第 47 页）。详情页“继续阅读”按钮与阅读器 HUD 统一采用章内相对页码呈现，消除与单话总页数的认知割裂。
- **长章节目录分批展开（Chapter Index Chunked Rendering）**：面对上百话的超长连载漫画（如 152 话），详情页章节目录采用分批展开（首屏 24 话 + 滚动/按需增量），防止一次性向 DOM 树灌入数百个组件与并发封面网络请求。
- **详情元数据内存态热复用（Detail In-memory SWR Cache）**：跨章节子路由与父详情页回跳时，直接命中 Pinia 内存已有完整元数据对象，避免几兆字节的巨型 JSON 重复传输与主线程反序列化，实现秒级无感回退。
- **任务驱动轮询（Job-driven Polling）**：详情页与章节页的缓存进度轮询仅在后台存在明确处于运行态的任务（`job.running === true`）时启动，任务完成或页面静默时严禁无限循环发请求。
- **增量更新 / 增量追加（Incremental Refresh / Incremental Append）**：针对书库已有漫画的更新动作。
  1. 远端漫画（JM / 哔咔）：支持拉取远端新增章节，亦全面开放馆长手动追加新章节或向指定话追加画页（接续停更作品）；手动追加后自动标记重新装订保护，转入本地优先单一真理源；
  2. 本地自建漫画（Local）：支持向指定单话追加新页（如追加后续拆帧帧数），或追加新一话章节，系统自动重算全局页码映射与缩略图。
- **复合画卷章节智能切分（Pattern-based Chapter Auto-Grouping）**：针对单层目录下文件名包含章节与页码复合前缀（如 `1-1.avif`, `2-1.avif`, `c1_01.jpg`, `第1话_01.png`）的画卷集合，系统在全量装订或批量导入时自动提取前缀并聚类为独立章节。优先对齐并继承原漫画的已有章节标题，超出部分自动按 `第 N 话` 顺延命名并计算 `start` 与全局单调页码。
- **单话靶向重新装订与缩略图局部失效（Targeted Chapter Re-binding & Scoped Thumbnail Invalidation）**：针对多章节作品中特定单话的画卷替换。系统原子清空并写入目标话的画卷目录，精准失效并重建该话画页的缩略图及所属章节封面，严禁波及或误清空全本其他未改动章节的缓存与封面；同步自动重算后续所有章节的 `start` 起始偏移量与全书 `page_count`。
- **标签编辑与管理（Tag Management）**：馆长可自由为漫画（含自建与远端收录）追加自定义标签或删除已有标签，即时同步至全局标签筛选池。
- **重新装订（Re-binding / Full Page Re-binding）**：用馆长指定的纯图片文件或服务器本地目录彻底替换已有漫画的画页。系统原子清空旧页面文件并按文件名自然升序重新生成 `00001.webp` ~ `0000N.webp`、更新 `page_count`、重建全套封面与缩略图。
- **重新装订保护（Re-bound Pages Protection）**：远端漫画（如 JM / 哔咔）在画页被馆长重新装订或手动追加章节后打上的防护标记（`custom_pages: true`）。此状态下漫画保留来源出处与元数据，但免疫远端图片的自动同步与覆盖，确保馆长重新装订的高清图卷与手动补更章节不被远端污染。
- **阅读器（Reader）**：沉浸式读图界面，支持三种模式。见下方"阅读器"组。

## 收藏夹状态

- **书库（Library / Shelf）**：用户的全部收藏集合，书架页展示。
- **案头藏书（Active Desk Shelf / activeComics）**：书架主网格中陈列的未读与在读作品集合，按收录时间倒序优先排布于视觉核心区，维持读者案头的淘书新鲜感与阅读重心。
- **卷末归档专匣（Shelf Archive Drawer / completedComics）**：位于主书架底部的折叠收纳专匣，用于归档安置已读完的作品。提供克制的微降权视觉质感与双向受控展开，既保持已读书卷的典雅陈列，又彻底消除已读积压对淘书的干扰；在全架书卷均已读完时智能感知展开。
- **标签（Tag）**：作品上的分类标签，书架页可筛选；标签数量用于排序展示。
- **筛选（Filter）**：书架页对收藏的检索手段——标题/车号/作者/标签关键词、标签点选、"只看喜欢"、阅读状态（全部/在读/已读）。
- **书架检索 Web Worker 卸载（Shelf Search Web Worker Offloading / Dual-track Filtering）**：面对万级藏书构建的双轨计算卸载契约。藏书少于 1000 本或处于 Node/Vitest 环境时，直接在主线程执行纯函数，耗时 < 0.5ms 且保障环境平稳；藏书达到或超过 1000 本时无感切入专用后台工作线程，通信仅单向传递微量查询参数与几十 KB 的有序 ID 数组，主线程利用预构建 Map 进行 $O(1)$ 指针还原，彻底消除深拷贝反序列化风暴与主线程击键掉帧。
- **万级藏书三层防御架构（Three-tier Defense Architecture for Large-Scale Shelf）**：面对上万本海量藏书展开与检索建立的从计算、DOM 到像素渲染的立体防御护城河。第 1 层通过 Web Worker 卸载多维过滤与拼音排序 CPU 运算；第 2 层通过 `usePaginationFold` 受控折叠（搜索时立即重置切片为初始 12 本）死锁 DOM 节点预算；第 3 层通过展开软封顶（120 本）与 CSS `contain: layout style` 约束局部重排，结合原生图片 `loading="lazy"` 与 3D 副封面交互后延时解码，既杜绝海量展开瞬间 DOM 爆炸，又彻底消除 `content-visibility: auto`（`contain: paint`）对卡片 `-0.35rem` 悬浮浮动与弥散外阴影（`--shadow-2`）的死黑硬件裁切。
- **阅读状态分段筛选（Reading Status Segmented Filter）**：读者作品阅读进度的单选互斥维度（`全部` / `在读` / `已读完`），与正交的个人偏好（`只看喜欢`）解耦，并通过 URL Query 双向持久化。
- **阈值流式展开与安全刹车（Threshold Stream Loading & Safety Brake）**：书架网格的自适应流式加载机制。在维持「48 图预算」与「滚动逃逸根治」底线的前提下，前 N 批（默认 5 批 / 60 本）支持触底无感平滑自动追加；达到安全阈值后主动挂起自动追加并唤起折叠函套卡，防止无限滚动冲垮浏览器显存并阻断底部「卷末归档专匣」的可触达性。
- **标签溢出抽屉（Overflow Tag Tray / 标签托盘）**：书架标签筛选条中承载高频 8 个标签之外溢出标签的平滑折叠展开容器。采用现代无级尺寸插值（`interpolate-size`）实现文档流内的原位平滑推展，配合纯 CSS 硬件层级隔离，在克制视觉决策超载的同时根除逐帧重排掉帧。
- **书架上下文记忆与视口锚定（Shelf Context Memory & Viewport Restoration）**：跨路由跳转与回退时对读者案头阅览状态的完整保护机制。在同一 SPA 会话中持久保持案头藏书展开批次、卷末归档专匣开闭、检索关键词与标签筛选态；在读者从本子详情或阅读器返回书架时，优先以记忆批次同步展开 DOM 骨架，并于 `nextTick` 精准还原离开时的垂直滚动视口（`scrollY`），根除视口高度截断（Clamping）与“打开的又回去了”的体验断裂。
- **以图搜图（Visual search / Image search）**：通过上传/粘贴截图特征比对，快速定位所属本子及具体匹配页码的检索能力。
- **识图芯片（Image search chip）**：搜索输入框内呈现当前检索图片的紧凑卡片微件，包含微缩预览、点击查看大图与清除按钮（×）。
- **匹配结果（Match result）**：识图检索命中的作品（`source`/`source_id`）、具体页码（`page_index`）与匹配置信度。
- **识图增量追加（Incremental Feature Indexing）**：识图引擎默认的工作流。仅对新缓存图片提取 ORB 特征并直接追加未索引向量至倒排索引；原有特征与聚类中心 100% 保留，秒级完成，零重复计算。
- **全量重置重训（Full Quantizer Retraining）**：重新运行 K-Means 聚类（512 聚类中心）并重建全量倒排索引的高开销维护行为（`--full` 参数），仅在首次初始化或模型重构时使用。
- **特征倒排索引同步（Quantizer-Invlists Alignment）**：量化聚类中心（`quantizer.bin`）与特征倒排列表（`invlists.bin`）必须基于同一次训练产生的聚类中心构建。若量化器被重新训练而倒排列表未同步重置重建，将产生**索引失步（Index Desynchronization）**，导致特征向量落入错误聚类桶，使真实匹配退化为低分噪点。发生失步时必须重置已索引标记并重建倒排索引。
- **台词全文检索（Dialogue Full-Text Search / FTS5）**：通过在搜索栏输入作品对白、名台词或汉化吐槽，在毫秒级内直接定位所属漫画、具体画页与气泡坐标的深度内容检索能力；由 SQLite FTS5 倒排索引支撑，与以图搜图（`imsearch`）互为图文双翼。
- **简繁双向检索（Simplified/Traditional Bidirectional Search）**：台词检索中消除海峡两岸汉化组字符差异的透明映射机制。输入简体自动覆盖港台繁体译文，输入繁体亦能命中大陆简体文本，杜绝精准匹配下的假性漏搜。
- **图文双模联合检索（Multimodal Hybrid Search）**：将局部特征以图搜图（`imsearch`）与台词全文检索（FTS5）有机结合的复合检索能力。支持在指定漫画或作者范围内限定台词搜索，亦在识图命中页码时即时带出对应对白摘要供读者校验。
- **台词联想浮层（Dialogue Search Popover）**：书架搜索栏键入关键词时按需展开的水墨纸本下拉分镜面板。采用静默伴生原则（检索无结果时保持隐身，不打扰本地书架常规检索），展示命中文本、朱砂金墨 `<mark>` 高亮、微缩封面与页码气泡元信息，支持 WAI-ARIA Combobox 无障碍键盘视口跟随与回车直达。
- **声明式分镜高亮切分（Tokenized Declarative Highlight）**：为杜绝 XSS 注入风险，将后端 FTS5 返回的带 `<mark>` 标签的台词片段纯函数解析为结构化 Token 数组（`{ text: string, isMark: boolean }[]`），在 Vue 模板中声明式渲染，不使用任何 `v-html`。

## 阅读器

- **未读（Unread）**：用户尚未翻阅过的作品（`last_page === 0` 或尚无进度记录）。
- **在读（In-progress / Reading）**：用户已翻阅但尚未读完全部的作品（`0 < last_page < page_count`）。
- **已读完（Completed / Read）**：用户已翻阅至全本最后一页或末页结尾卡的作品（`last_page >= page_count`）。若作品后续追加新话/新页导致总页数增加，将自愈回落至在读状态。
- **读完滞后（Read Completion Deprioritization / Sinking）**：书架默认“最近收录”排序下的两层分桶策略。未读与在读作品按收录时间倒序优先排在上方，已读完作品按收录时间倒序整体沉底归档，消除已读积压对淘书新鲜感的干扰。
- **接卷推荐（Next Reads / Reader End Recommendation）**：阅读器末页结尾卡呈现的智能选书微件。在排除本书与全部已读完作品后，优先挑选相同作者、原作或高标签重合度的未读/在读藏书，并以最新未读兜底，实现无缝连续阅览。
- **阅读模式（Reader Mode）**：三种——`竖向连续`（垂直滚动无吸附）、`竖向翻页`（一次一屏）、`横向翻页`（左右滑动，支持 RTL 日漫方向）。
- **每屏页数（Pages per view）**：一次显示 1 / 2 / 4 页；窄屏（<=680px）只允许 1/2。
- **图片适配（Fit）**：`适应宽度` 或 `适应高度`，影响图片在屏内的缩放方式。
- **画卷视口（Reader Viewport）**：阅读器中承载多排版模式（纵向连续/纵向翻页/横向翻页）与分屏画页渲染（`ReaderViewport.vue`）的核心滚动视口容器。
- **跨话横幅（Chapter Banners / 话首·话末横幅）**：多章节阅读模式下在当前话第一页与最后一页底部浮现的「← 上一话」与「本话完 · 下一话 →」导航交互胶囊（`ReaderChapterBanners.vue`）。
- **离散滚轮步进与双轴分流（Discrete Wheel Stepping & Dual-Axis Discrimination）**：横向翻页模式下兼顾 PC 鼠标机械滚轮与触控板的物理映射范式。水平主导手势全额放行原生视口平滑滑移；垂直主导滚轮经阈值保护转换为单屏离散步进，自适应 LTR 与 RTL（日漫）阅读流向，通过原生物理滚动无缝联动内核级滚动驱动动画与进度条，彻底消除强制吸附对小位移滚轮的回弹假死。
- **继续阅读（Last-read）**：每本作品独立记录"上次翻到第几页"（`comic-shelf:last-read:<source>/<sourceId>`），详情页据此显示"继续阅读"。
- **自动切换（Auto-turn）**：按固定间隔（5/10/15/30 秒）自动翻到下一屏的辅助功能；开启后 HUD 常驻，手动操作重置计时。在竖向翻页与横向翻页离散模式下生效。
- **自动流卷 / 匀速漫游（Auto-scroll Stream / Continuous Auto-Scroll）**：竖向连续（条漫）排版模式下自动阅读的特化形态。由 `requestAnimationFrame` 驱动视口以设定速率（40/80/140 px/s 或自定义）匀速向下平滑滑移，彻底替代离散切屏翻页；具备交互瞬时避让（Soft Yield，滚轮/触控介入时暂避并在停顿 1.5s 后平滑自愈恢复）与话末平缓停靠（Dock & Hold）特性。
- **绝对触底夹紧与视口中心线探测（Scroll Bottom Clamping & Viewport Center Intersection）**：解决条漫分镜切片高度不一、末页顶边无法触及视口顶端导致页码停滞与下一话横幅缺失的几何法则。当滚动容器距底部小于等于 24px 时，强制夹紧至当前话末页并激活跨话状态；非触底状态以视口有效阅读线（视口上方 40% 处）与画卷相交计算当前页码，消除短切片识别盲区。
- **流式行内收尾卡片（In-flow Chapter Transition Card）**：竖向连续长卷模式下位于全话末页正文文档流下方的章节完结与切话微件。自然顺接于末页画卷之后并带有充足的视口呼吸垫高留白，替代遮挡正文的绝对定位悬浮胶囊，确保全话末尾分镜与台词 100% 完整可见。
- **阅览室暗色环境（Reader room）**：阅读器固定的深色环境（`--reader-*` tokens），不随系统亮/暗主题切换，与书房（书架首页）的亮色纸面刻意区分。
- **条漫无缝拼接（Webtoon Seamless Stitched View / Gapless Scroll）**：在竖向连续阅读模式下，通过彻底剥离行内占位页脚、外边距（gap/padding）与页面阴影（box-shadow），并将画卷视口强制约束为适应全宽（Fit Width），使图源切片的上下边缘以 0 像素物理咬合，还原韩漫/条漫原本浑然一体的垂直连续长卷。
- **浮动画卷页标（Floating Page Pill）**：条漫无缝模式下替代行内装订页脚的浮动微件。位于视口边缘，在滚动时感应浮现，停顿后静默淡出，完全不侵入长条漫画的正文文档流。
- **全局基线阅读设置（Global Baseline Reader Settings）**：全站所有未单独设定偏好的漫画所共同继承的基础排版规范，持久化于本机 `comic-shelf:reader-settings:v1`。
- **单本专属偏好（Per-Comic Overrides）**：读者针对特定作品独立调整并记忆的排版配置（`comic-shelf:reader-overrides:v1`），优先级高于全局基线；支持条漫自适应识别并允许一键清除恢复跟随全局。
- **排版作用域双轨制（Dual-Scope Reader Preference / Tabbed Scopes）**：阅读设置面板中向读者明确开放的「🌐 全局默认」与「📖 本作偏好」双轨配置体系。读者可自由决定调整是影响全站新书还是仅作用于当前作品，彻底消除隐式黑盒选择。
- **条漫排版硬约束（Seamless Webtoon Layout Constraint）**：长卷无缝拼接模式下对「适应全宽（Fit Width）」与「单屏单页（PagesPerView=1）」的排版硬约束，防范切片高 DPR 错位与横向宽度撕裂。
- **翻页锁定整屏入目（Paged Discrete Full-Frame Constraint）**：竖向翻页与横向翻页模式下“一次一屏”的离散视野契约。强制锁定为整屏完整入目，禁止在翻页模式下产生屏内二次纵向滚动，确保每一次翻页动作均呈现完整分镜画幅。
- **宽高比锁定帧（Aspect-Ratio Lock Frame）**：阅读器画页包裹容器与底层图片绝对 1:1 贴紧的几何契约。画页解码后将其真实物理宽高比注入外层包裹帧，消灭容器内部的留白与溢出，确保台词气泡覆盖层与物理画面在任何视口比例下以零像素误差精确咬合。
- **刚性翻页吸附（Rigid Page Snap）**：竖向与横向翻页模式下的确定性翻页物理约束。读者滑动停手后必严格对齐至单页起始边界，杜绝悬停在两页交界处的伪连续漂移。
- **气泡呼吸高亮（Breathing Bubble Overlay）**：阅读器接收到台词检索直达意图时（`?page=42&bubble_box=...`），在目标画页对应的归一化气泡矩形（`[ymin, xmin, ymax, xmax]`）上浮现暖纸朱砂金色半透明覆盖层，呼吸闪烁 2 秒后自然平滑淡出并原地静默擦除 URL 查询参数；非台词检索进入或翻离当前页时物理不挂载覆盖层，零 DOM 重排且不打扰后续连续阅读心流。

## 基础设施

- **书库数据（Library data）**：后端 `backend/data/library/` 下的本地持久化，不得删除。
- **常青设计系统规范（Living Design System）**：`DESIGN_NOTES.md` 所承载的纸间全站设计规范与单一真理源。包含品牌哲学、禁止清单、Token 契约、组件架构与核心设计红线（如 §13 顶层解构定律）。
- **设计演进里程碑归档（Design Milestones Archive）**：`docs/design-archive/` 下收录的纸间历史演进推演、挑刺与重构记录，供历史溯源，与常青设计规范物理解耦。
- **设计令牌（Design tokens）**：`src/styles/tokens.css` 中的颜色/间距/字号/圆角/动效体系，UI 改动必须收敛到 token，禁止硬编码漂移。
- **淘汰特性：HTML-in-Canvas 列表实验（Deprecated: HTML-in-Canvas List Experiment）**：曾作为探索将书架卡片 DOM 绘制进 Canvas 的试验，经实机评估，因 GPU 显存膨胀（每卡独立 Canvas 纹理暴涨）、CSS Grid 下 ResizeObserver 自激震荡（无限增长死循环）以及交互语义退化，已被作为反模式彻底从主干废弃移除；书架坚守原生 DOM + 48 图增量预算的高性能纯净架构。
- **前瞻能力探针（Experimental Capability Probe）**：位于 `src/utils/canvasProbe.ts` 的零依赖纯函数探测工具，用于安全侦测浏览器对 WICG `HTML-in-Canvas`（`drawElementImage` 与 `<canvas layoutsubtree>`）的原生支持度。仅供未来富排版图文合成实验室与 2D 互动游戏探索使用，与主干书架生产视图物理隔离。
- **双平台架构边界（Dual-Platform Architecture: Paper Studio vs Paper Room）**：明确纸间（Paper Room / comic-shelf）作为**读者端与成品展馆**的轻量定位（只负责作品收录、离线阅读、以图搜图与手稿回放）；而重型的 AI 生图调试（ComfyUI / Midjourney / Flux）、分镜修版与 VTracer 批量矢量压制交由独立的**创作者工作台平台（Paper Studio）**，两端通过标准 API（`POST /api/library/local/create` 与静态资源管道）松耦合协作，避免向阅读器仓库引入重型依赖与算力争抢。
- **手稿分层资产（Making-of Layer Asset / `.layers.json`）**：由外部 AI 创作工坊（Paper Studio）通过 VTracer 矢量化引擎从光栅画页中提炼的高精矢量图层数据，与原图平级存储（如 `00001.layers.json`）。采用按拓扑层级（底层大面积底色 ➔ 阴影明暗过渡 ➔ 表层勾线与网点 ➔ 高光）排序的紧凑贝塞尔路径数组，体积比 XML SVG 减少 40%，且无需前端进行昂贵 DOM 解析。
- **手稿分层回放台（Making-of Layer Player）**：漫画详情页与阅读器中的轻量暗室弹窗微件。通过 Canvas 2D 原生 `new Path2D(d)` / WebGL 硬件加速在 120 FPS 下流式重绘矢量图层，向读者展示画作的分层生长与运笔制作过程，全过程 0 DOM 节点负担、0 显卡算力争抢。
- **台词伴生资产（Sidecar OCR Asset / `{index}.ocr.json`）**：画页的结构化文字与气泡坐标伴生数据。记录单页分镜气泡的归一化相对坐标 `[ymin, xmin, ymax, xmax]`、对白文本、语种（zh/ja）与识别置信度。与原图平级存储于 `pages/` 目录，与原图二进制解耦。
- **分轨异构语料库（Decoupled Heterogeneous Corpus）**：纸间生态中对漫画分镜（视觉-空间多模态）与 Galgame 剧本（时间-分支文本流）所采取的分流存储架构。漫画保留分镜几何气泡契约（`{index}.ocr.json`），Galgame 保持标准剧本事件流（`JSONL`），在下游特定任务（如翻译微调、剧本生成）时通过投影算子按需组合汇流。
- **二次元专精平行语料与翻译微调（Anime Parallel Corpus & Translation Fine-Tuning）**：通过汉化漫画中日对齐台词与 Galgame 双语剧本提炼的高质量双语对照语料，专用于二次元垂直风格翻译模型微调与生肉本子本地即时汉化。
- **气泡级文本聚类（Bubble-level Line Clustering）**：OCR 伴生数据处理流水线中的空间几何合并规范。将单张画页中散落的多行文本框基于空间欧氏距离与排版流向聚类为完整气泡，提取覆盖完整对白的单一归一化包围盒，避免单行截断搜索与破碎高亮框。
- **幽灵索引清理（Ghost Index Cleanup）**：在漫画删除、画页重新装订（Re-binding）或伴生数据更新时，联动 SQLite FTS5 虚拟表原子删除历史过期台词记录的自愈保障机制，彻底根除“搜得出台词但打开画页不存在或不对版”的索引撕裂。
- **MCP + Skill 双子星架构（MCP & Skill Dual-Layer Agent Architecture）**：纸间面向外部自主 AI 智能体确立的分层协作标准。MCP（Model Context Protocol）充当“设备驱动与原子能力工具箱（Hands & Eyes）”，输出标准 Tool Schema；配套 Agent Skill（`SKILL.md`）充当“业务指南与心智工作流（Brain & Playbook）”，规范调用顺序、权限边界、错误重试与结果包装，杜绝盲目试错调用。
- **插画资产池（Illustration Pool）**：全站看板角色与加载插画的统一发现与随机轮换池（`/loading-*.webp`），支持零配置自动感知新资产。
- **环境暗印水印（Ambient Watermark）**：页面与弹窗底层的极浅角色暗纹，以纸质水印质感呈现，亮色与暗色模式下均保持极低对比度，绝不干扰前景内容与文字可读性。
- **全幅加载占位（Full-frame Page Loading）**：阅读器单页加载时与漫画页面等比撑满的骨架占位，大画幅展示装订插画并彻底消除排版跳动。
- **馆长密钥（Auth Secret / Curator Secret）**：环境变量 `COMIC_SHELF_SECRET` / `COMIC_SHELF_AUTH_TOKEN`。配置后开启门禁防护与馆长全权；未配置时保持零门槛内网模式。
- **访客通行证（Guest Pass / Guest Token）**：由馆长在管理后台动态派发与维护的专属身份凭证，包含用户名/备注、独立 Token、过期时间与启用状态。替代已废弃的旧版全局环境变量访客口令。
- **通行证派发与生命周期（Pass Issuance & Lifecycle）**：馆长为特定朋友或设备创建通行证、延长过期期限（续期）、重置 Token 密钥或即时禁用的安全控制闭环。
- **通行证激活状态（Pass Activation State）**：访客通行证在生命周期中所处的流转阶段，包括「待认领（未设 PIN）」、「使用中（已设 PIN 且有设备接入）」、「已满额（绑定设备达上限）」与「已失效（已过期或手动停用）」。
- **读者自设 PIN 码 / 认领通行证（Reader PIN / Pass Claiming）**：4~6 位纯数字代码，由读者在首次点开通行证时自行设定（将卡片从待认领 `pending` 转化为已认领 `claimed`）。密码经 16 字节随机盐与 100,000 轮 PBKDF2-HMAC-SHA256 哈希后存储于 SQLite，用于确立该通行证的唯一号主身份，彻底阻断群聊转发时的未授权偷用。
- **访客称呼净化与长度规约（Username Sanitization & Length Boundary）**：全站访客昵称收敛为 1~20 字符标准，后端持久化时经 `sanitize_username` 剥离 HTML 尖括号、不可见/零宽字符与表格公式前缀（`=+-@`），结合前端单行文本打点折叠，形成零 XSS、零排版溢出与零 CSV 注入的纵深防护。
- **轮询防重入与超时熔断（Anti-Starvation Polling & Global Request Timeout）**：前端所有状态轮询（`liveCache`、`cacheProgress`）均挂载互斥锁，并在 API 请求封装层统一注入 15 秒超时守护控制器，杜绝因单次网络滞后或服务重启引起的请求并发堆叠，防范浏览器 HTTP/1.1 单域 6 个 TCP Socket 耗尽导致全站假死。
- **双重限流键防 DoS（Dual-Key Rate Limiting / Anti-DoS）**：针对群聊恶意尝试 PIN 码的保护屏障。采用 `(client_ip, pass_id)` 双重键限流：单 IP 输错 5 次仅封禁该攻击者 IP 5 分钟，号主合法设备不受影响；跨 IP 累计超 20 次触发全局 30 分钟保护，彻底杜绝恶意账户锁定拒绝服务（Account Lockout DoS）。
- **门禁口令撞库熔断器（IP Login Brute-Force Limiter）**：针对全屏门禁 `/api/auth/login` 的网络层保护。单个 IP 在 1 分钟内口令错误达到 10 次立即触发 5 分钟 IP 熔断（HTTP 429），防止并发字典碰撞馆长密钥或暴力探测通行证。
- **会话凭据自愈暂存（Session Pending Token Resilience）**：前端解决移动端切屏、浏览器后台重载或误触下拉刷新导致待认领/待输 PIN 状态丢失的韧性基建。在未完成登录前将 `pendingToken` 暂存至 `sessionStorage`，刷新自动自愈恢复表单，登录成功或主动更换口令即刻物理抹除。
- **群聊扩散防互挤屏障（Anti-Group-Spam Gate）**：通行证被认领后，任何新设备打开链接均必须提供正确的个人 PIN 码。未获授权的群友因无法通过 PIN 校验被拦截在门外，彻底消除群内多人轮替挤占与误触发熔断锁的痛点。
- **PIN 码防护漫游（PIN-Guarded LRU Eviction）**：在通过个人 PIN 码确认为合法号主本人的前提下，当号主接入第 N+1 台设备时自动淘汰最久未活跃旧设备（LRU），实现合法号主多端漫游与自愈换机。
- **设备插槽与配额（Device Slots & Quota）**：单个访客通行证允许同时授权绑定的有效物理设备数量（默认 2 台，馆长可调节 1~5 台），用于限制凭证滥用扩散。
- **设备会话凭据（Device Session Token）**：访客凭通行证口令成功登入某台具体设备后颁发的专属设备凭据，独立于通行证本身，支撑单设备的生命周期追踪与精准踢除。
- **防重复发放预警（Anti-Duplicate Safeguard）**：馆长在访客簿分发或复制已被激活使用的通行证时触发的警示反馈，避免误将同一借阅凭据发放给不同好友导致设备互踢。
- **置换频次熔断锁（Eviction Cooling Lock）**：针对脚本高频切 UA 刷设备恶性挤人的防御机制。当单张通行证在 5 分钟内连续发生置换超过 3 次，系统判定为设备争抢异常并启动 10 分钟置换冷却锁：当前已在线设备正常使用，新设备尝试置换时被 HTTP 429 拦截。
- **访客阅览速率限流（Guest Rate Limiting / Token Bucket）**：针对持有有效凭证的爬虫多线程拖图攻击的中间件级防护。针对 `guest` 角色分配每分钟 180 页 + 100 页瞬时突发容量的内存令牌桶，超额触发 HTTP 429，在保障人类高速翻阅、大跨度拖拽与预加载的同时秒级阻断批量爬虫。
- **新藏书默认隐身策略（Default Hide for New Imports）**：全局安全性偏好配置（`guest_hide_new_comics`）。开启后新收录或导入的藏书元数据默认打上 `hidden_from_guest: true`，须由馆长核验并确认适合借阅后主动解除隐藏，杜绝私人藏书漏标外泄。
- **通行证异常态预警（Abnormal Pass Alert）**：馆长访客名册中对遭遇设备高频争抢或爬虫速率受限的通行证呈现的告警印章（`〔 设备频繁争抢锁定中 〕`）与提示，辅助馆长一秒识别异常并一键重置密钥清场。
- **快捷指令中枢（Slash Command Palette）**：书架搜索栏键入 `/` 呼出的纸间快捷指令选单（`/台词`、`/车号`、`/作者`、`/随机`）。支持键盘上下导航、Tab / Enter 快速补全与简写别名（`/d`、`/id`、`/a`、`/r`），统一案头检索与模式切换。
- **命令胶囊（Command Chip）**：搜索输入框选定指令后在左侧呈现的朱砂印章微件（如 `〔 💬 台词 × 〕`）。在胶囊模式下，输入内容与书架网格 100% 物理解耦（冻结书架过滤），彻底消除“一打台词列表全空”的体验割裂；光标位于行首按退格键（Backspace）或点击关闭图标秒级退出模式。
- **短词全表扫描防爆守卫（Short-Query Defense Guard）**：台词全文检索中少于 2 个有效字符时强制阻断 FTS5 与数据库检索，杜绝十万级数据规模下因 Trigram 分词截断导致的无索引 `LIKE %xx%` 全表扫描，保障服务器低功耗稳定运行。
- **用户专属状态（User-Isolated State）**：以用户身份（馆长 `curator` 或具体访客通行证）为隔离维度的个性化数据，包含「喜欢（Favorite）」与「继续阅读进度（Last-read Progress）」，在后端 SQLite 持久化并支持多设备无缝同步，不同访客与馆长之间互不污染。
- **轻量状态数据库（Lightweight State Database / SQLite）**：后端基于 Python 内置 `sqlite3` 的单文件持久化数据库（`backend/data/comic_shelf.db`，约 5MB 级），专门承载通行证、用户行为高频状态以及藏书元数据影子索引；与文件系统自包含的本子元数据（`album.json`）正交解耦，并与台词全文专库物理分离。
- **台词全文专库（Dialogue Dedicated Database / `comic_dialogues.db`）**：后端独立的 SQLite 数据库文件（`backend/data/comic_dialogues.db`），专门承载 `comic_dialogues_fts`（FTS5 Trigram 全文倒排索引）与伴生同步元数据 `comic_ocr_sync_meta`。在万级与十万级（数百万至千万条台词）规模下，将高频耗时批量写入与用户端核心状态完全物理隔离，彻底消除写锁争抢与备份膨胀。
- **藏书影子索引表（Comics Shadow Index / `comics_index`）**：在 `comic_shelf.db` 中维护的元数据查询影子表。保持文件系统 `album.json` 本地单一真理源的前提下，接管万级藏书的分页切片、多字段排序、关键词模糊检索与用户专属状态的动态 SQL JOIN，使万本规模响应保持在毫秒级。
- **台词全文索引表（Comic Dialogues FTS / `comic_dialogues_fts`）**：在独立专库 `comic_dialogues.db` 中维护的 SQLite FTS5 虚拟全文检索表（基于 Trigram 分词）。将 `{index}.ocr.json` 中的对白文本以倒排索引建表，支持读者在书架搜索栏通过模糊台词快速定位目标漫画、具体页码与气泡坐标。
- **Trigram 全文检索分词（Trigram FTS Tokenizer）**：SQLite FTS5 内置的高性能 3-Gram 倒排分词模式。无需外部 Python/C 中文或日文分词扩展，原生支撑中日文无空格文本的任意 3 字以上子串模糊检索。
- **Galgame 剧本语料库（Galgame Script Corpus）**：统一收纳于 `backend/data/corpus/galgame/` 的纯文本剧本资产（JSON Lines 格式）。解耦于漫画画卷，记录场景 ID、发言人、对白、旁白与中日双语对照，作为二次元专精翻译微调与 AVG 分支编译的黄金数据源。
- **全貌统计与列表端点解耦（Decoupled Facet & Paginated List Endpoints）**：将全站总本数、总页数、缓存页数与高频标签池等重量级聚合计算收敛至 `/api/library/facets`（单次或变动驱动），与高频轻量的分页列表 `/api/library` 解耦。
- **本子全局隐藏（Global Guest-Hidden / `hidden_from_guest`）**：本子维度的全局元数据属性。打上此标记的漫画仅馆长可见，对所有访客通行证一律隐藏（API 统一响应 404），从根源杜绝敏感或私人收藏向访客泄露。
- **双口令门禁（Dual-Secret Gate）**：单输入框智能识别。未授权者在门禁处被 100% 拦截（HTTP 401），支持馆长密钥或有效访客通行证验证进入，零元数据与图片泄露。
- **全屏零残留门禁（Zero-DOM Gate View / Zero-DOM Gate）**：未鉴权状态下前端根组件（`App.vue`）采用顶层 `v-if` 条件渲染。未通过鉴权前绝对不挂载 `AppHeader`、`RouterView` 及任何业务视图，屏幕仅渲染独立的门禁纸室，使浏览器 DOM 树内物理级不存在任何书库/漫画数据，彻底免疫控制台 `display: none`、节点删除或样式覆写窥探。
- **馆长（Curator / Admin）**：拥有纸间全部管理权限（收录、删除、标记全局隐藏、重新装订、派发通行证）的最高身份，由馆长密钥鉴权，享有独立的 `curator` 喜欢与阅读记录。
- **访客（Guest / Reader）**：持有有效访客通行证的阅览者身份。仅拥有浏览书架、检索筛选、阅读翻页与以图搜图权限；享有独立的个人喜欢与阅读进度；界面完全隐藏所有管理与破坏性控件。
- **读者借书证 / 借阅凭证浮层（Reader Pass Popover）**：访客模式下顶栏身份印章展开的轻量卡片。呈现当前读者姓名、专属书架状态与防误触「交还凭证 / 退出」操作；彻底剥离任何管理特权与“解锁馆长”字样，退出时主动释放当前设备的并发席位并平滑回到门禁。
- **正文阅读令牌桶限流（Guest Token Bucket Rate Limiting）**：针对访客角色的漫画正文与缩略图（`/file`、`/thumbnail`）二进制流量阀门（180 页/分钟持续速率 + 100 张突发桶）；书架封面（`/cover`）独立解耦，防范批量展示误杀。
- **新书默认隐藏（Default Hide for New Imports）**：全站安全隐私策略。开启后远端收录与本地扫描的漫画初始自动标记为访客不可见（`hidden_from_guest: true`），需经馆长核验后主动公开。

- **防盗链（Hotlink Protection）**：基于现代浏览器 `Sec-Fetch-Site: cross-site` 识别及 Referer 校验机制，严禁外部第三方网站跨站直连纸间作为存储桶或图片代理。
- **外部目录白名单（Allowed Directories Whitelist）**：环境变量 `COMIC_SHELF_ALLOWED_DIRS` 构筑的安全沙箱。仅允许馆长扫描导入位于该白名单内的服务器本地目录，彻底防止任意路径文件遍历与探测攻击。
- **视图过渡（View Transition）**：全站单页与局域状态变更时的平滑快照过渡机制，包括页面层级路由推进/后退（`forward` / `backward` Types）、封面到详情大画幅的「共享封面形变」、局域视图过渡（`Element.startViewTransition`）以及弹窗与按钮状态演进，无缝遵循纸间 `--duration-1/2/3` 与无障碍降级。
- **共享封面形变（Shared Cover Morph）**：书架卡片封面（`comic-cover-active`）与本子详情 Hero 封面在路由跳转时的动态连续尺寸与位置插值（神奇移动）。
- **缩略图预热与渐进呈现（Thumbnail Pre-warming & Progressive Reveal）**：详情页与子章节页通过 360px WebP 缩略图（48 页/批增量渲染）按需下发，同时在后端磁盘完成原图持久化解密；阅读器直接读取本地文件并通过 GPU 硬件加速透明度淡入呈现，达成 0 远端重复请求与毫秒级秒开。
- **原始画质保真与格式解耦（Source Format Page Fidelity）**：正文漫画页（`/file`）100% 保持原始源格式（如 JM 的 WebP、PicACG 的 JPEG 或本地归档的 PNG），严禁对正文画质进行二次有损转码；所有衍生图（书架封面、目录封面与章节缩略图）统一收敛为 WebP 格式（质量 80），兼顾极致源图保真与轻量网络传输。
- **书架静默回源（Shelf SWR / Stale-While-Revalidate）**：书架首页在内存已有数据时先即时呈现现有卡片，后台静默向后端对齐最新状态，仅在初次无数据时展示骨架屏，杜绝切页时卡片重载与骨架屏闪烁。
- **请求中止与竞态隔离（Request Abort & Race Cancellation）**：利用 `AbortController` 与组件生命周期绑定，在瞬时进出页面或并发触发检索（如以图搜图重选、排行榜切档）时主动取消上一轮未完成的网络请求，避免无效流量与状态覆盖。
- **字阶底线与自适应排版（Typography Floor & Fitting）**：纸间对单行文字自适应（如阅读器顶栏标题、车号徽章）设立的排版保护原则。在采用现代弹性缩放防溢出的同时，强制受限于离散字阶底线（≥ `--text-xs` / 12px），极小徽标（`--text-caption` / 11px）优先借助 `font-size-adjust` 渐进增强突破 12px 限制并保持盒模型稳定，杜绝 `transform: scale()` 模糊与偏移；单行容器长文本防折行压缩（未来 `text-fit: shrink per-line`）严格限定于阅读器 HUD 与工具栏等单体上下文，严禁侵入书架网格阵列，坚守卡片阵列固定字阶与多行截断，杜绝卡片间字号忽大忽小破坏视觉节律。
- **纸间统一图标集（Unified Archive Iconography）**：全站矢量图标单源字典体系。统一步调为暖纸细线条描边与朱砂印章质感（1.8px 细描边 / 24px 网格），彻底杜绝跨平台字符（`✕`/`✓`/`×`）渲染字重撕裂与重复内联 SVG 碎片。
- **高精亚像素截断（Subpixel Truncation / 4 位精度规约）**：原子进度条组件（`AppProgressBar`）向 CSS 变量（`--progress`）与 GPU 硬件加速层（`scaleX`）注入浮点数时统一保留 4 位有效小数（精度 0.0001 / 0.01%）。在 4K 宽屏（3840px）下亚像素误差低于 0.38px，杜绝 16 位 IEEE 754 浮点噪点污染 DOM 属性与 CSS 样式。
- **通用微件胶囊（Chip / AppChip）**：纸间设计系统的底层无障碍交互与展示胶囊组件。区别于业务实体「标签（Tag）」，微件胶囊是通用 UI 原子基建，支持只读文本（`<span>`）、状态按压切换（`<button aria-pressed>`，如“只看喜欢”/“只看已读”）、计数值徽印、前后置矢量图标与可删除标记（Removable），单源收敛全站 `.chip` 与 `.chip-button` 视觉表现。
- **标准操作与多态按钮（Action Button / AppButton）**：纸间设计系统的单一入口按钮基建。支持多态渲染（`<button>`、`<RouterLink>` 与 `<a>`）、标准六色变体（`primary` / `secondary` / `ghost` / `soft` / `danger` / `success`）、正圆/方形独立图标形态（`shape="circle" | "square"`）及阅读器暗室主题防护（`theme="reader"`），单源收敛全站操作控件与无障碍焦点环。
- **现代浮层体系（Modern Floating System）**：基于 HTML Popover API 与 CSS Anchor Positioning 规范构建的无依赖顶层浮动交互基建，包含 `Modal`（强中断模态对话框）、`AppPopover`（富交互锚定浮层）、`AppDropdown`（操作选单与选择器）与 `AppTooltip`（`popover="hint"` 轻量气泡提示），彻底消除散落的绝对定位胶水代码与 z-index 冲突。
- **气泡提示（Tooltip / AppTooltip）**：`popover="hint"` 声明式轻量提示微件，专门承载辅助性只读文案；覆写浏览器 User-Agent 样式实现零幽灵滚动条；内置**悬停安全桥（Hover Bridge）**，遵循 WCAG 2.1 1.4.13 国际标准，支持光标无缝移入划词选读与复制。复杂表单、按钮列表与多级菜单严格收敛至 `AppPopover` / `AppDropdown`。
- **文本多行自适应截断与纸印气泡（Text Clamping & Paper Tooltip）**：全站卡片与元数据网格中对超长文本施加的行数预算约束（`line-clamp-N`）。配合基于 HTML Popover API + CSS Anchor Positioning 的按需气泡，在保证书架卡片严整对齐的同时，提供 100ms~350ms 延迟的无感查阅与选词复制。
- **零开销懒浮层架构（Zero-DOM & Zero-Listener Floating Architecture）**：针对百张卡片长列表性能建立的浮层优化定律。默认仅渲染普通语义文本标签，浮层 DOM 节点与全局 `window` 滚动/尺寸监听器仅在激活可见时按需挂载，休眠时监听器占用与多余 DOM 精确为 0，彻底免疫高频滚动卡顿。
- **内联手风琴折叠（Inline Disclosure / 叙述展开）**：详情页中对长篇叙述简介采用的非侵入展示策略。基于现代无级尺寸插值（`interpolate-size: allow-keywords`）与水墨渐隐蒙版，默认展示前 3 行并提供「展开全文 / 收起」搭配折叠指示旋钮切换，展开与收起双向平滑过渡，完美保留汉化组段落换行与空格，规避浮动气泡对图书呼吸感与移动端触控的遮挡。
- **悬停安全桥（Hover Bridge）**：气泡与触发源之间的无形触控延伸区（纯 CSS 伪元素实现）。无缝填补两者之间的物理 margin 空隙，确保光标滑入气泡时轨迹全程处于命中区，彻底杜绝穿过空白缝隙时的闪退痛点。
- **顶层层级与轻量失焦关闭（Top Layer & Light Dismiss）**：利用浏览器原生顶层特性，天然解决浮层被父级 `overflow: hidden` 或 `contain: paint` 截断的问题；原生支持点击外部空白或 Esc 键无缝自动收起。
- **原生顶层模态（Top Layer Dialog / `<dialog>`）**：基于 HTML5 `<dialog>` 元素与 `<Teleport to="body">` 双重构建的顶层模态体系（`Modal.vue`）。一方面享有浏览器原生 Top Layer 层级、`::backdrop` 视口遮罩与输入焦点循环捕获；另一方面通过 Teleport 脱离宿主 DOM 分支，隔绝局部 CSS 继承污染与事件冒泡击穿，兼得渲染顶层与 DOM 拓扑解耦。
- **声明式命令触发器（Command Invoker / `commandfor`）**：基于 HTML Invoker Commands API 的无 JS 交互控制机制。通过 `<button commandfor="id" command="...">` 声明式触发对话框与浮层的打开、关闭或自定义指令（`CommandEvent`），并在无障碍树中自动绑定控制关系。
- **状态切换事件体系（Toggle Event System / `beforetoggle` & `toggle`）**：原生 DOM 浮层与模态状态变更事件机制。在元素显示/隐藏前后派发并携带 `oldState`/`newState` 与触发源 `source`，作为外部声明式操作与 Vue 单向响应式状态机双向对齐的单一同步纽带。
- **锚定回退感知与滑动动效（Anchor Fallback & Sliding Indicator）**：利用 `container-type: anchored` 与 `@container anchored(fallback: flip-block)` 纯 CSS 感知碰撞翻转自适应箭头与安全桥；借助动态 `anchor-name` 实现分段选项卡与选单项的纯 CSS 物理滑动胶囊动效。
- **意图触发与隐式锚定（Interest Invoker & Implicit Anchor）**：基于 HTML `interestfor` 属性与 `:interest-source` / `:interest-target` 伪类的声明式悬停交互规范；触发源与气泡目标天然建立隐式锚点（无需显式声明 `position-anchor`），配合 `interest-delay` 纯 CSS 控制延时与快速划过连环触发。
- **动态鼠标跟随锚点（Mouse-Follow Dynamic Anchor）**：将画卷光标坐标（`--mouse-x`、`--mouse-y`）与纯 CSS 锚点定位相结合的动态定位机制，用于实现 0 渲染重排开销的漫画高倍局部放大镜（Loupe Zoom）与实时悬浮卡片。
- **回到顶部（Back to top / Scroll-to-top）**：纸间长页面（书架、多章节详情）的标准导航辅助微件。采用 VueUse `useWindowScroll` 监听视口（默认 >400px 阈值浮现），以正圆暖纸印章质感呈现，支持自适应 `prefers-reduced-motion` 与键盘焦点平滑转移，阅读器沉浸模式下自动隐身。
- **防退化门禁（Regression Safety Net）**：全仓多层自动化防御机制，包含前端 `vp check`（TS/Vue 静态检查）、后端 `pnpm test:py`（AST 符号自检 + 真实中间件链路与多章节单测），杜绝改动引发核心功能断裂。
- **客户端离线缓存（Client Offline Cache / PWA Cache）**：浏览器 Service Worker 与 CacheStorage 在当前设备上存储的静态资产与阅读图片缓存，受本设备存储配额（`StorageManager`）约束。纯客户端生命周期，区别于后端「本地化持久数据（Library Data）」，可由用户随时一键安全清理且绝不影响服务器书库。
- **静默离线接管（Silent Offline Takeover / Zero-Toggle Offline Resilience）**：客户端全自动网络容灾与离线回退机制。在浏览器断网（`!isOnline`）或服务器连接熔断（`isOffline`）时，系统自动在后台直接从 IndexedDB 镜像（`shelf_snapshots` 与 `comic_details`）恢复书架与藏书案头，呈现典雅的离线状态纸印，无需也不允许用户手动点选任何「只看离线」开关；网络重获连接时静默上报离线阅读事务队列，实现真正的零割裂本地优先体验。
- **分级离线缓存策略（Tiered Offline Caching）**：App Shell 核心静态资产预缓存（Stale-While-Revalidate）、动态 API 直连配合内存态 SWR 复用（严禁 Service Worker 缓存 API 防鉴权脏数据）、漫画页面原图与缩略图离线命中（Cache-First）配合 LRU 淘汰配额（3000 张上限）与手动清理。
- **源私有文件系统（Origin Private File System / OPFS）**：基于 `navigator.storage.getDirectory()` 的浏览器端侧私有沙盒文件系统。作为纸间技术雷达的前瞻储备能力，专用于非 HTTP 语义的单体大文件（如未来的整本漫画离线导出归档包 `.cbf` 或典藏中文字体）的流式落盘，区别于承载网络画卷的 CacheStorage。
- **淘汰索引元数据开销（LRU Expiration Metadata / LevelDB Baseline）**：Workbox Expiration 在 IndexedDB 中维护漫画画页 LRU 淘汰队列时产生的底层磁盘开销（~1.2 MB）。系 Chromium LevelDB 预写日志与数据块预分配的固有物理占位，确保 3,000 张图片上限自动滚动淘汰，非数据泄漏。
- **阅览室存储与设备卡片（Storage & Device Card）**：基于 `AppPopover` 呈现的客户端离线状态微件，承载 PWA 安装状态、存储占用标尺、分项容量明细与图片缓存安全清理。
- **独立应用与视口检测（PWA Standalone Mode）**：通过 `display-mode: standalone` 媒体查询及 iOS `navigator.standalone` 探测读者是否以桌面/手机独立窗口形式运行纸间，提供无地址栏与沉浸阅读器全屏联动。
- **周期性更新检查（Periodic Service Worker Update Check）**：应用在长期待机或回到前台时，在后台以 `cache: 'no-store'` 每小时静默探测远端 `sw.js` 脚本哈希并触发更新，避免读者客户端被旧版本 Service Worker 僵死。
- **意图预热（Prefetch on Intent）**：在读者光标悬停（`pointerenter`）、键盘聚焦（`focusin`）或触屏接触（`touchstart`）时，静默并发预热目标视图组件 chunk 与详情元数据（写入 `useMemoize` 内存），将异步模块拉取与接口耗时无感消化在读者的决策延迟（100~300ms）内。
- **即时元数据占位（SWR Hero Placeholder）**：跨页面跳转进入详情页时，优先直接复用书架 Store 已持有的 `LibrarySummary` 渲染顶部 Hero 真实标题与封面，使共享封面形变（`comic-cover-active`）精准生效，杜绝抓取纯灰骨架屏导致的二次闪烁与排版跳变。
- **顶栏控件组（Header Control Group）**：顶栏右侧承载设备存储状态（`StoragePopover`）、访客簿（`GuestModal`）与身份认证（`useAuth`）的操作按钮集合。在桌面端以「图标 + 紧凑单源字体标签」呈现；在移动端（`≤640px`）统一步调收敛为 36px 正方形纸印图标按钮（`--control-sm`），文字无感隐退，通过视觉印章与提示语对齐，触控命中区经由伪元素平滑扩展至 44px 标准。
- **紧凑首屏标语（Compact Hero Banner）**：书架首屏 `LibraryHero` 的响应式形态。桌面端展开双栏文学宣言与大号统计；移动端（`≤640px`）自动收紧为单行标题与单行内联统计点缀（`本数 · 本地页 · 总页`），折叠长篇说明，释放首屏 70% 纵向空间，让书单与搜索框在手机第一屏即可直接阅读。
- **溢出标签顶层气泡（Overflow Tag Popover）**：书架标签筛选条（`TagFilterBar.vue`）中对高频标签（前 8 个）之外的次级溢出标签进行收纳的顶层微件。基于 HTML Popover API 与 CSS Anchor Positioning（`AppPopover`）构建，浮于文档流与合成图层之上，支持 Light Dismiss 与键盘焦点圈闭。彻底消除原流式抽屉在展开时推挤下游卡片引发的帧级几何重排与 GPU 合成雪崩。
- **无级尺寸插值（Grid Track Interpolation / interpolate-size）**：现代 CSS 尺寸自适应折叠动画机制。仅适用于下游无复杂合成图层/滤镜且不遮挡吸顶玻璃的局部封闭手风琴（如详情页叙述）；严禁用于推挤海量卡片长列表的页面主干流，避免在 144Hz 等高刷设备上触发逐帧几何重排与丢帧。
- **自动翻页自定义秒数（Custom Auto-Turn Interval）**：阅读器自动切屏设置项。支持在预设选项（5/10/15/30秒）之外由读者就地输入 1~300 秒自定义数字，提供自适应阅读节奏。
- **HUD 暂停态指示（HUD Paused Indicator）**：阅读器右下角 HUD 在自动翻页暂停时呈现的视觉形态。由朱砂印章色 `IconPause` 矢量图标与「继续」操作文案构成，杜绝出现空白状态。
- **静态扩展名别名与边缘强缓存（Static Extension Aliasing & Edge Cache）**：为了让 Cloudflare 等通用 CDN 默认识别静态图片并激活边缘缓存，图片二进制与缩略图端点同时暴露语义化扩展名别名（`.webp`、`.jpg`），彻底杜绝无后缀动态请求反复穿透家庭宽带跨洋回源。

- **探针静音与访问日志门禁（Probe Quiet Filtering & Access Log Gate）**：Uvicorn 访问流水日志过滤机制。对容器健康探针与高频心跳在返回 200 正常时默认静音，仅在异常报错时输出；支持环境变量彻底关闭请求日志，消除控制台刷屏。
- **内外网分流（Split-Horizon DNS）**：纸间倡导的局域网与公网融合网络拓扑。同一域名在家庭局域网内通过本地 DNS 重写直连 NAS 内网 IP，享受千兆内网零延迟；公网环境下解析至 Cloudflare 命中边缘缓存，兼顾多端单点登录、PWA 离线缓存隔离与极致阅览性能。
- **任务驱动型单向系统事件流（Task-Driven System Event Stream / SSE）**：基于 FastAPI 异步协程与 `asyncio.Queue` 驱动的按需事件通道（`/api/events/stream`）。常态浏览下彻底断开（DevTools 0 pending 连接、零网络悬挂感）；仅在触发后台漫画导入、全量/章节预缓存等异步任务时自适应拉起，任务完成后经 5 秒平滑防抖冷却自动切断。空闲保活采用 30 秒 keepalive 心跳以穿透网关超时；同设备多标签页变动由原生 `BroadcastChannel` 0 流量接管，彻底消除前端 HTTP 定时轮询与常驻长连接负担。
- **纸印更新气泡与双重提醒（Prompted Update Toast & Dual Notice）**：PWA Service Worker 发现新静态资产构建就绪时激活的轻量交互机制。在屏幕边缘浮现极具纸间水墨质感的非侵入提示胶囊（支持「立即装订 (刷新)」与「稍后」），并在顶栏设备微件保留朱砂徽标，沉浸翻阅时自动避让。
- **视口与唤醒回源校验（Visibility & Online Wakeup Sync）**：利用 VueUse `useDocumentVisibility` 与 `useNetwork` 在页面重获焦点或网络自愈时触发的轻量 Service Worker 脚本比对（`registration.update()`），以 0 业务接口开销确保长期待机设备自愈回源。
- **闲时意图预热（Idle & Intent Prefetching）**：跨路由异步视图组件（如阅读器）的加载策略。首屏渲染期间通过 `requestIdleCallback` 在主线程空闲时静默预热，同时在交互按钮上绑定 `pointerenter`/`focusin`/`touchstart` 意图触发，杜绝预热流量混入初始关键请求链（Critical Request Chains）。
- **静态资产传输压缩（Static Transfer Compression / GZip Middleware）**：单容器与 NAS 本地部署时后端全局挂载的动态压缩中间件（阈值 1000 字节）。将 CSS/JS/JSON 资源体积压缩 60~85%，消除未压缩静态文件对初始渲染的阻塞。
- **封面渲染预算（Cover Dimension Budget / 720px）**：封面与缩略图的物理像素规格。默认采用 720px 宽度（JPEG/WebP 高画质），完美匹配 360~375px 卡片容器在 Retina 2x 屏幕下的物理细腻度，兼顾视觉质感与网络/解码开销。
- **服务自愈与优雅退出熔断（Self-Healing Startup & Graceful Shutdown Timeout）**：本地开发环境与单容器部署的服务生命周期保护机制。启动前自动探测 8000 端口，识别并自愈回收历史残留的 Uvicorn/Python 僵尸进程；Uvicorn 配置 3 秒优雅停机超时熔断（`timeout_graceful_shutdown=3`），结合开发脚本（`dev.sh`）的进程树两阶段退出（`SIGTERM` -> 2s 缓冲 -> `SIGKILL` 兜底），彻底消除端口幽灵占用与孤儿进程。
- **单向系统事件流主动注销（SSE Active Stream Teardown）**：后端优雅停机或热重载时针对 `/api/events/stream` 挂载的长连接实施的主动熔断机制。通过向活跃的 `asyncio.Queue` 投递 `None` 退出哨兵（Poison Pill），唤醒阻塞在 `queue.get()` 上的生成器协程即刻退出并关闭 HTTP 响应流，避免持久长连接阻止 Uvicorn 关停流程。
- **智能按需系统事件流（Smart On-Demand Event Stream / SSE Sleep & Task Lifecycle）**：单向系统事件流的自适应生命周期编排机制。以「任务驱动」为第一原则（`hasActiveTasks || isCoolingDown`），在此基础上叠加阅读器避让（`/read/...` 主动切断以释放 HTTP/1.1 槽位给画页）、视口离开即断（`hidden`）与离线自适应熔断。任务结束后经过 5 秒防抖窗口优雅熔断注销，切回前台或从阅读器退出时自愈对齐（`reconcileState`），兼顾长耗时批量下载稳健性与网络面板极致纯净度。
- **响应式阶梯封面（Responsive Stepped Covers / srcset & sizes）**：基于 HTML5 `srcset`（`w` 物理宽度描述符）与 `sizes` 布局槽位规范的多阶封面分发体系。根据书架卡片槽位（~180px）、详情页 Hero 槽位（~360-480px）与设备像素比（1x/2x/3x DPR），由浏览器自主决策拉取最适宜规格图片（如 360w / 720w），兼顾移动端低内存与高分屏细腻度；严格遵循 `sizes` 显式声明守则，杜绝缺省 `sizes` 导致浏览器默认按 100vw 误拉超大原图；配合现代 `sizes="auto"`（Chrome 126+, Firefox 150+）在懒加载场景实现原生排版尺寸联动。
- **核心资产预缓存（Core Assets Precache）**：Workbox 在客户端首次加载时静默拉取并写入 CacheStorage 的核心静态代码与界面图标外壳（App Shell）。设计规范要求核心预缓存严格收敛在 1.5 MB 预算内，超大媒体资产严禁入列；客户端存储面板独立测量其所在缓存桶，与动态图片完全物理隔离。
- **物理存储正向归因（Physical Storage Attribution）**：阅览室设备离线容量的分项统计范式。由浏览器真实物理配额总用量（`usageDetails.caches` 或 `usage`）扣除独立测出的轻量 App Shell 核心资产，将读者翻阅产生的所有漫画画页、封面及插画的真实磁盘开销全额归因于「漫画阅览缓存」，消除首部抽样偏差与核心资产虚假膨胀。
- **离线插画池（Illustration Pool）**：全站看板角色与加载插画的按需运行时缓存池（`/loading-*.webp`）。通过虚拟模块编译期探测、运行时 `CacheFirst` 懒加载策略，兼顾离线可用性与首屏秒开，杜绝首屏吞吐近 10 MB 媒体的流量黑洞。
- **iOS 桌面引导（iOS PWA Add-to-Home Guidance）**：针对 WebKit 缺少 `beforeinstallprompt` 规范特性的平台交互补偿。在 iOS Safari 视口下以典雅纸面徽印呈现「Safari 分享 ➔ 加到主屏幕」引导，并在 Web Manifest 层面剔除凭据陷阱，保障 Standalone 独立视口无缝唤起。
- **Service Worker 边缘穿透与安全放行（PWA Edge Bypass & WAF Skip）**：Cloudflare 等 CDN 边缘对 `sw.js` 与 `manifest.webmanifest` 实施的绝对穿透（Bypass Cache）与 WAF 人机验证跳过规则（Skip WAF）。确保客户端版本发现永远直通源站且静默探测免遭 403 质询阻断，彻底隔绝因 CDN 缓存旧 SW 或误杀清单引发的静态资源 404 连锁崩溃。
- **统一构建插件架构（Modular Vite Plugins / `plugins/`）**：根目录收敛的自定义构建扩展体系。将文件系统探测、虚拟模块生成（如 `virtual:illustrations`）等非标准逻辑从 `vite.config.ts` 抽离解耦，由 `tsconfig.node.json` 全局类型纳管，保持主配置文件轻巧可读，为未来构建插件提供规范单一源。
- **按需布局探测（Just-In-Time Layout Measurement / JIT Truncation Detection）**：针对网格卡片与多行截断长列表的极致排版探测机制。彻底废除组件挂载期（`onMounted` / `nextTick`）与无差别观察器（`useResizeObserver`）对全量静态文本的无差别强同步重排，将 `scrollHeight` / `clientWidth` 等几何测量严格推迟至读者意图触发时刻（光标进入 `pointerenter`、触控 `touchstart`、焦点聚集 `focusin`），实现首屏网格 0 次 DOM 尺寸测量与 0 毫秒强制重排阻塞。
- **强制重排防御门禁（Forced Reflow Detector / Layout Thrashing Gate）**：全仓前端性能自动化扫描机制（`pnpm detect:perf` / `scripts/detect-perf.mjs`）。静态扫描 `src/` 中所有在生命周期钩子（`onMounted`/`onUpdated`）、响应式监听（`watch`）中同步读取排版属性、高频滚动未节流、触控事件缺少 `passive: true`，以及在海量卡片长列表上滥用 `<TransitionGroup>` 引发连环 `getBoundingClientRect` 测量的代码反模式，筑牢首屏 120fps 防线。
- **延迟生效气泡评估（Deferred Disabled Evaluation）**：现代浮层与按需探测的协同机制。允许浮层触发源在鼠标移入（`pointerenter`）瞬间异步推导截断状态，气泡组件在唤起延迟（`delay`）计时器触发时刻二次核验 `props.disabled`，兼顾 JIT 响应式单向流与零闪烁弹出。
- **凭据边缘免检与安全级别跳过（Auth Cookie Edge Bypass & Security Level Skip）**：Cloudflare Anycast 边缘根据客户端携带的认证 Cookie（默认 `comic_shelf_token` 与 `comic_shelf_device`，支持自定义）实施的精细化质询豁免机制。在全域开启「Under Attack 模式」极高防扫描防护的前提下，自动跳过针对合法读者的安全级别（五秒盾）挑战，消除后台非交互式 API 与漫画原图加载因 `cf_clearance` 失效引发的 403 质询阻断。
- **源站私有印章防线（Origin Auth Secret & Gateway Gate）**：由 Cloudflare Transform Rules 在回源请求中静默注入私有请求头（`X-Origin-Secret`），配合反向代理网关（Nginx Proxy Manager）实施的源站级准入控制。既保障了家庭局域网（Split-Horizon DNS）千兆直连免检，又在家庭公网高位端口（如 38443）遭到全网探测与 IP 嗅探时直接下发 403 阻断，实现非 Cloudflare 边缘回源流量零穿透。
- **端侧元数据离线持久化（Client Metadata IndexedDB Cache / SWR Mirror）**：前端 Pinia Store 与数据层在客户端基于 IndexedDB 构建的结构化元数据快照镜像（包含书架摘要列表、全貌统计与漫画详情）。在冷启动与离线断网时实现 0ms 秒开呈现，联网时静默 SWR（Stale-While-Revalidate）向服务端同步；严格按用户身份隔离，彻底杜绝 Service Worker 裸缓存 API 导致的权限混淆与数据泄露。
- **纸室离线模式（Offline Shelf Snapshot & Offline Mode）**：PWA 在无网络连接时自适应激活的典雅阅览状态。系统在后台静默自动接管，书架完整保留全貌快照并打上「〔 纸室离线模式 〕」暗印状态；卡片维持端侧本地就绪状态，使读者在通勤与飞机等断网环境下依然拥有从容的淘书与阅读体验。
- **缺页纸印骨架（Offline Missing-Page Paper Stamp）**：阅读器在离线状态翻阅未缓存画页时的优雅降级呈现。以纸间暖纸水墨质感的「〔 画页未离线缓存 · 联网后自动载入 〕」占位骨架替代浏览器原生破损图标与粗暴弹退，阅读器 HUD 与其他已缓存画页保持平滑导航。
- **端侧离线记账与联网对齐队列（Offline Action Log & Reconciliation Queue）**：离线模式下读者产生的翻页进度（`last_page`）与喜欢（`favorite`）状态变更的端侧持久化事务队列。状态即时乐观生效于本地视图与 IndexedDB；待设备重获网络连接（`online` 事件或网络自愈）后，由后台静默对齐管道批量回写至后端 SQLite 数据库。
- **捕获间隙瞬时滚动（In-Flight Pre-Capture Instant Scroll）**：View Transitions 跨页前进推进时的零重排滚动重置范式。在旧视图快照已由浏览器离屏捕获（被 GPU 冻结在屏幕上）、新视图尚未挂载的 capture gap 间隙中，瞬时执行 `window.scrollTo({ top: 0, behavior: 'instant' })`，既保证读者视觉零跳动，又使新视图直接在 (0, 0) 原位挂载，切断 Vue Router 挂载后微任务 `scrollToPosition` 诱发的强制同步重排（消除 209ms 阻塞）。
- **惰性三维悬浮（Lazy 3D Elevation）**：针对长列表弱 GPU / 核显显存优化的渲染策略。书架静态空闲状态下所有卡片保持纯 2D 盒模型并剥离高斯模糊与片段着色器，仅在光标悬停（`:hover`）或键盘聚焦（`:focus-visible`）的瞬态单节点按需激活 `perspective` 3D 透视，杜绝数十张卡片同时常驻 3D 合成管线引发的高刷掉帧与显存带宽过载。
- **顶栏双哨兵滚动感知（Dual-Sentinel Header Scroll Observer）**：基于原生 `IntersectionObserver` 的零重排横向滚动状态检测体系。在可滚动的来源导航栏首尾内联注入 1px 隐形哨兵节点，替代传统 `useScroll` / `scrollLeft` 属性轮询，使左右边缘羽化遮罩的显隐切换完全由异步图层相交事件驱动，消除首屏初始化与容器尺寸变动时的 57ms Forced Reflow。
