# CONTEXT.md — 纸间 · Paper Room 领域术语表

> 本项目只有一份 context（单体前端 + 后端）。本文件是纯术语表，不含实现细节。
> 术语达成共识后即时更新；ADR 单独放 `docs/adr/`。

## 品牌与定位

- **纸间（Paper Room）**：产品名。定位是"本地优先的个人漫画收藏夹"，不是公开站点，也不是泛化爬虫。
- **私人阅览室 / 卡片目录（Reading room / Card catalog）**：产品视觉语言的隐喻——暖纸色、墨色、朱砂色，像图书馆卡片与旧书脊；明确禁止紫色渐变、玻璃拟态堆叠、霓虹、emoji 当图标。

## 核心概念

- **本子（Comic / Book）**：书库里的一条漫画作品记录。用户视角的"一本"。
- **车号（display_id）**：作品在来源站点的唯一编号（如禁漫 `523607`，本地自建 `LOC_tiya-frames`），是"放进纸间"时用户需要输入或生成的标识。`display_id` 与 `source` 组合才是全局唯一。
- **来源（Source / Provider）**：作品的远端或本地出处（`jm` 禁漫、`local` 本地自建/本地目录导入；预留 `picacg` 哔咔）。每个来源有独立的 `short_label`、编号格式、数据目录 `library/<source>/<source_id>/`。
- **本地自建漫画（Local Comic）**：由用户直接上传图片文件或指定服务器已有文件夹（如视频拆帧目录）收录生成的作品。`source = "local"`，无远端依赖，直接持久化于 `library/local/<source_id>/`。
- **收录（Import）**：把一本作品"放进纸间"的动作。规则：先查本地 `album.json`，命中则 `from_cache=true` 绝不请求远端；首次收录缓存前 4 页做封面。本地自建漫画收录时即时生成封面与缩略图。
- **本地化（Caching / Cachify）**：把页面图片下载到本地（`cached_pages` / `cache_complete`）。图片必须走解密工具，禁止直接保存下载字节；本地自建漫画页面在导入时即为 100% 本地化。
- **并发上传队列（Concurrent Upload Queue）**：批量上传大量图片（如数百张拆帧图）时的客户端流量阀门。采用受限并发（3~4 路）分批推送到后端，兼顾上传速度与服务器连接稳定性。
- **封面（Cover）**：作品的预览图，默认取自首页前 4 页，或由馆长自定义指定 4 个全局页码序号（`cover_indices`）；书架卡片与详情页轮播的视觉锚点。
- **封面序号自定义（Cover Indices）**：允许馆长在自建工坊或编辑资料弹窗中显式指定 4 个全局页码序号（如 `[1, 10, 25, 50]`），书架与详情页轮播卡片将按此顺序展示这 4 张页面作为封面。
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
- **单话按需离线（Chapter-level Caching / Cache by Chapter）**：多章节漫画支持在章节卡片与章节详情页触发针对该单话的后台图片下载任务，弥补“全本预缓存（MAX 600页）”在超长作品（数千页/上百话）下的粗粒度缺陷与反爬风险。
- **章节相对页码（Chapter-relative Page Index）**：多章节作品中面向读者展示的章内相对页码（`local_page = global_page - chapter.start + 1`，如第 3 话第 2 页，全书第 47 页）。详情页“继续阅读”按钮与阅读器 HUD 统一采用章内相对页码呈现，消除与单话总页数的认知割裂。
- **长章节目录分批展开（Chapter Index Chunked Rendering）**：面对上百话的超长连载漫画（如 152 话），详情页章节目录采用分批展开（首屏 24 话 + 滚动/按需增量），防止一次性向 DOM 树灌入数百个组件与并发封面网络请求。
- **详情元数据内存态热复用（Detail In-memory SWR Cache）**：跨章节子路由与父详情页回跳时，直接命中 Pinia 内存已有完整元数据对象，避免几兆字节的巨型 JSON 重复传输与主线程反序列化，实现秒级无感回退。
- **任务驱动轮询（Job-driven Polling）**：详情页与章节页的缓存进度轮询仅在后台存在明确处于运行态的任务（`job.running === true`）时启动，任务完成或页面静默时严禁无限循环发请求。
- **增量更新 / 增量追加（Incremental Refresh / Incremental Append）**：针对书库已有漫画的更新动作。
  1. 远端漫画（JM）：保持本地已有图片与元数据缓存不变，仅拉取远端新增章节或新页码；
  2. 本地自建漫画（Local）：支持向指定单话追加新页（如追加后续拆帧帧数），或追加新一话章节，系统自动重算全局页码映射与缩略图。
- **标签编辑与管理（Tag Management）**：馆长可自由为漫画（含自建与远端收录）追加自定义标签或删除已有标签，即时同步至全局标签筛选池。
- **重新装订（Re-binding / Full Page Re-binding）**：用馆长指定的纯图片文件或服务器本地目录彻底替换已有漫画的画页。系统原子清空旧页面文件并按文件名自然升序重新生成 `00001.webp` ~ `0000N.webp`、更新 `page_count`、重建全套封面与缩略图。
- **重新装订保护（Re-bound Pages Protection）**：远端漫画（如 JM）在画页被馆长重新装订后打上的防护标记（`custom_pages: true`）。此状态下漫画保留来源出处与元数据，但免疫远端图片的自动同步与覆盖，确保馆长重新装订的高清图卷不被远端污染。
- **阅读器（Reader）**：沉浸式读图界面，支持三种模式。见下方"阅读器"组。

## 收藏夹状态

- **书库（Library / Shelf）**：用户的全部收藏集合，书架页展示。
- **标签（Tag）**：作品上的分类标签，书架页可筛选；标签数量用于排序展示。
- **筛选（Filter）**：书架页对收藏的检索手段——标题/车号/作者/标签关键词、标签点选、"只看喜欢"。
- **以图搜图（Visual search / Image search）**：通过上传/粘贴截图特征比对，快速定位所属本子及具体匹配页码的检索能力。
- **识图芯片（Image search chip）**：搜索输入框内呈现当前检索图片的紧凑卡片微件，包含微缩预览、点击查看大图与清除按钮（×）。
- **匹配结果（Match result）**：识图检索命中的作品（`source`/`source_id`）、具体页码（`page_index`）与匹配置信度。
- **识图增量追加（Incremental Feature Indexing）**：识图引擎默认的工作流。仅对新缓存图片提取 ORB 特征并直接追加未索引向量至倒排索引；原有特征与聚类中心 100% 保留，秒级完成，零重复计算。
- **全量重置重训（Full Quantizer Retraining）**：重新运行 K-Means 聚类（512 聚类中心）并重建全量倒排索引的高开销维护行为（`--full` 参数），仅在首次初始化或模型重构时使用。
- **特征倒排索引同步（Quantizer-Invlists Alignment）**：量化聚类中心（`quantizer.bin`）与特征倒排列表（`invlists.bin`）必须基于同一次训练产生的聚类中心构建。若量化器被重新训练而倒排列表未同步重置重建，将产生**索引失步（Index Desynchronization）**，导致特征向量落入错误聚类桶，使真实匹配退化为低分噪点。发生失步时必须重置已索引标记并重建倒排索引。

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
- **继续阅读（Last-read）**：每本作品独立记录"上次翻到第几页"（`comic-shelf:last-read:<source>/<sourceId>`），详情页据此显示"继续阅读"。
- **自动切换（Auto-turn）**：按固定间隔（5/10/15/30 秒）自动翻到下一屏的辅助功能；开启后 HUD 常驻，手动操作重置计时。
- **阅览室暗色环境（Reader room）**：阅读器固定的深色环境（`--reader-*` tokens），不随系统亮/暗主题切换，与书房（书架首页）的亮色纸面刻意区分。

## 基础设施

- **书库数据（Library data）**：后端 `backend/data/library/` 下的本地持久化，不得删除。
- **常青设计系统规范（Living Design System）**：`DESIGN_NOTES.md` 所承载的纸间全站设计规范与单一真理源。包含品牌哲学、禁止清单、Token 契约、组件架构与核心设计红线（如 §13 顶层解构定律）。
- **设计演进里程碑归档（Design Milestones Archive）**：`docs/design-archive/` 下收录的纸间历史演进推演、挑刺与重构记录，供历史溯源，与常青设计规范物理解耦。
- **设计令牌（Design tokens）**：`src/styles/tokens.css` 中的颜色/间距/字号/圆角/动效体系，UI 改动必须收敛到 token，禁止硬编码漂移。
- **实验开关（Experiment）**：`HTML-in-Canvas 卡片`——把书架卡片整块 DOM 绘制进 canvas 的实验性渲染路径，由实验 store 控制开关。
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
- **访客阅览速率限流（Guest Rate Limiting / Token Bucket）**：针对持有有效凭证的爬虫多线程拖图攻击的中间件级防护。针对 `guest` 角色分配每分钟 120 页 + 45 页瞬时突发容量的内存令牌桶，超额触发 HTTP 429，在保障人类高速翻阅与预加载的同时秒级阻断批量爬虫。
- **新藏书默认隐身策略（Default Hide for New Imports）**：全局安全性偏好配置（`guest_hide_new_comics`）。开启后新收录或导入的藏书元数据默认打上 `hidden_from_guest: true`，须由馆长核验并确认适合借阅后主动解除隐藏，杜绝私人藏书漏标外泄。
- **通行证异常态预警（Abnormal Pass Alert）**：馆长访客名册中对遭遇设备高频争抢或爬虫速率受限的通行证呈现的告警印章（`〔 ⚠️ 设备频繁争抢锁定中 〕`）与提示，辅助馆长一秒识别异常并一键重置密钥清场。
- **用户专属状态（User-Isolated State）**：以用户身份（馆长 `curator` 或具体访客通行证）为隔离维度的个性化数据，包含「喜欢（Favorite）」与「继续阅读进度（Last-read Progress）」，在后端 SQLite 持久化并支持多设备无缝同步，不同访客与馆长之间互不污染。
- **轻量状态数据库（Lightweight State Database / SQLite）**：后端基于 Python 内置 `sqlite3` 的单文件持久化数据库（`backend/data/comic_shelf.db`），专门高效承载通行证与用户行为高频状态；与文件系统自包含的本子元数据（`album.json`）正交解耦。
- **本子全局隐藏（Global Guest-Hidden / `hidden_from_guest`）**：本子维度的全局元数据属性。打上此标记的漫画仅馆长可见，对所有访客通行证一律隐藏（API 统一响应 404），从根源杜绝敏感或私人收藏向访客泄露。
- **双口令门禁（Dual-Secret Gate）**：单输入框智能识别。未授权者在门禁处被 100% 拦截（HTTP 401），支持馆长密钥或有效访客通行证验证进入，零元数据与图片泄露。
- **全屏零残留门禁（Zero-DOM Gate View / Zero-DOM Gate）**：未鉴权状态下前端根组件（`App.vue`）采用顶层 `v-if` 条件渲染。未通过鉴权前绝对不挂载 `AppHeader`、`RouterView` 及任何业务视图，屏幕仅渲染独立的门禁纸室，使浏览器 DOM 树内物理级不存在任何书库/漫画数据，彻底免疫控制台 `display: none`、节点删除或样式覆写窥探。
- **馆长（Curator / Admin）**：拥有纸间全部管理权限（收录、删除、标记全局隐藏、重新装订、派发通行证）的最高身份，由馆长密钥鉴权，享有独立的 `curator` 喜欢与阅读记录。
- **访客（Guest / Reader）**：持有有效访客通行证的阅览者身份。仅拥有浏览书架、检索筛选、阅读翻页与以图搜图权限；享有独立的个人喜欢与阅读进度；界面完全隐藏所有管理与破坏性控件。
- **读者借书证 / 借阅凭证浮层（Reader Pass Popover）**：访客模式下顶栏身份印章展开的轻量卡片。呈现当前读者姓名、专属书架状态与防误触「交还凭证 / 退出」操作；彻底剥离任何管理特权与“解锁馆长”字样，退出时主动释放当前设备的并发席位并平滑回到门禁。
- **正文阅读令牌桶限流（Guest Token Bucket Rate Limiting）**：针对访客角色的漫画正文与缩略图（`/file`、`/thumbnail`）二进制流量阀门（120 页/分钟持续速率 + 45 张突发桶）；书架封面（`/cover`）独立解耦，防范批量展示误杀。
- **新书默认隐藏（Default Hide for New Imports）**：全站安全隐私策略。开启后远端收录与本地扫描的漫画初始自动标记为访客不可见（`hidden_from_guest: true`），需经馆长核验后主动公开。

- **防盗链（Hotlink Protection）**：基于现代浏览器 `Sec-Fetch-Site: cross-site` 识别及 Referer 校验机制，严禁外部第三方网站跨站直连纸间作为存储桶或图片代理。
- **外部目录白名单（Allowed Directories Whitelist）**：环境变量 `COMIC_SHELF_ALLOWED_DIRS` 构筑的安全沙箱。仅允许馆长扫描导入位于该白名单内的服务器本地目录，彻底防止任意路径文件遍历与探测攻击。
- **视图过渡（View Transition）**：全站单页与局域状态变更时的平滑快照过渡机制，包括页面层级路由推进/后退（`forward` / `backward` Types）、封面到详情大画幅的「共享封面形变」、局域视图过渡（`Element.startViewTransition`）以及弹窗与按钮状态演进，无缝遵循纸间 `--duration-1/2/3` 与无障碍降级。
- **共享封面形变（Shared Cover Morph）**：书架卡片封面（`comic-cover-active`）与本子详情 Hero 封面在路由跳转时的动态连续尺寸与位置插值（神奇移动）。
- **局域视图过渡（Element-Scoped Transition）**：局限于单个组件 DOM 子树内的独立状态过渡（如图片装订就绪、收藏按钮红心状态、并发步进器），不阻塞整页交互与全局重绘。
- **缩略图预热与渐进呈现（Thumbnail Pre-warming & Progressive Reveal）**：详情页与子章节页通过 360px JPEG 缩略图（48 页/批增量渲染）按需下发，同时在后端磁盘完成原图持久化解密；阅读器直接读取本地文件并通过 GPU 硬件加速透明度淡入呈现，达成 0 远端重复请求与毫秒级秒开。
- **书架静默回源（Shelf SWR / Stale-While-Revalidate）**：书架首页在内存已有数据时先即时呈现现有卡片，后台静默向后端对齐最新状态，仅在初次无数据时展示骨架屏，杜绝切页时卡片重载与骨架屏闪烁。
- **请求中止与竞态隔离（Request Abort & Race Cancellation）**：利用 `AbortController` 与组件生命周期绑定，在瞬时进出页面或并发触发检索（如以图搜图重选、排行榜切档）时主动取消上一轮未完成的网络请求，避免无效流量与状态覆盖。
- **字阶底线与自适应排版（Typography Floor & Fitting）**：纸间对单行文字自适应（如阅读器顶栏标题、车号徽章）设立的排版保护原则。在采用现代弹性缩放防溢出的同时，强制受限于离散字阶底线（≥ `--text-xs` / 12px），极小徽标（`--text-caption` / 11px）优先借助 `font-size-adjust` 渐进增强突破 12px 限制并保持盒模型稳定，杜绝 `transform: scale()` 模糊与偏移；单行容器长文本防折行压缩（未来 `text-fit: shrink per-line`）严格限定于阅读器 HUD 与工具栏等单体上下文，严禁侵入书架网格阵列，坚守卡片阵列固定字阶与多行截断，杜绝卡片间字号忽大忽小破坏视觉节律。
- **纸间统一图标集（Unified Archive Iconography）**：全站矢量图标单源字典体系。统一步调为暖纸细线条描边与朱砂印章质感（1.8px 细描边 / 24px 网格），彻底杜绝跨平台字符（`✕`/`✓`/`×`）渲染字重撕裂与重复内联 SVG 碎片。
- **现代浮层体系（Modern Floating System）**：基于 HTML Popover API 与 CSS Anchor Positioning 规范构建的无依赖顶层浮动交互基建，包含 `Modal`（强中断模态对话框）、`AppPopover`（富交互锚定浮层）、`AppDropdown`（操作选单与选择器）与 `AppTooltip`（`popover="hint"` 轻量气泡提示），彻底消除散落的绝对定位胶水代码与 z-index 冲突。
- **气泡提示（Tooltip / AppTooltip）**：`popover="hint"` 声明式轻量提示微件，专门承载辅助性只读文案；覆写浏览器 User-Agent 样式实现零幽灵滚动条；内置**悬停安全桥（Hover Bridge）**，遵循 WCAG 2.1 1.4.13 国际标准，支持光标无缝移入划词选读与复制。复杂表单、按钮列表与多级菜单严格收敛至 `AppPopover` / `AppDropdown`。
- **文本多行自适应截断与纸印气泡（Text Clamping & Paper Tooltip）**：全站卡片与元数据网格中对超长文本施加的行数预算约束（`line-clamp-N`）。配合基于 HTML Popover API + CSS Anchor Positioning 的按需气泡，在保证书架卡片严整对齐的同时，提供 100ms~350ms 延迟的无感查阅与选词复制。
- **零开销懒浮层架构（Zero-DOM & Zero-Listener Floating Architecture）**：针对百张卡片长列表性能建立的浮层优化定律。默认仅渲染普通语义文本标签，浮层 DOM 节点与全局 `window` 滚动/尺寸监听器仅在激活可见时按需挂载，休眠时监听器占用与多余 DOM 精确为 0，彻底免疫高频滚动卡顿。
- **内联手风琴折叠（Inline Disclosure / 叙述展开）**：详情页中对长篇叙述简介采用的非侵入展示策略。默认展示前 3 行并提供「展开全文 ▾ / 收起 ▴」切换按钮，完美保留汉化组段落换行与空格，规避浮动气泡对图书呼吸感与移动端触控的遮挡。
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
- **分级离线缓存策略（Tiered Offline Caching）**：App Shell 核心静态资产预缓存（Stale-While-Revalidate）、API 动态元数据优先回源（Network-First）、漫画页面原图与缩略图离线命中（Cache-First）配合 LRU 淘汰配额（如 500MB / 1000 张上限）与手动清理。
- **阅览室存储与设备卡片（Storage & Device Card）**：基于 `AppPopover` 呈现的客户端离线状态微件，承载 PWA 安装状态、存储占用标尺、分项容量明细与图片缓存安全清理。
- **独立应用与视口检测（PWA Standalone Mode）**：通过 `display-mode: standalone` 媒体查询及 iOS `navigator.standalone` 探测读者是否以桌面/手机独立窗口形式运行纸间，提供无地址栏与沉浸阅读器全屏联动。
- **周期性更新检查（Periodic Service Worker Update Check）**：应用在长期待机或回到前台时，在后台以 `cache: 'no-store'` 每小时静默探测远端 `sw.js` 脚本哈希并触发更新，避免读者客户端被旧版本 Service Worker 僵死。
- **意图预热（Prefetch on Intent）**：在读者光标悬停（`pointerenter`）、键盘聚焦（`focusin`）或触屏接触（`touchstart`）时，静默并发预热目标视图组件 chunk 与详情元数据（写入 `useMemoize` 内存），将异步模块拉取与接口耗时无感消化在读者的决策延迟（100~300ms）内。
- **即时元数据占位（SWR Hero Placeholder）**：跨页面跳转进入详情页时，优先直接复用书架 Store 已持有的 `LibrarySummary` 渲染顶部 Hero 真实标题与封面，使共享封面形变（`comic-cover-active`）精准生效，杜绝抓取纯灰骨架屏导致的二次闪烁与排版跳变。
- **顶栏控件组（Header Control Group）**：顶栏右侧承载设备存储状态（`StoragePopover`）、访客簿（`GuestModal`）与身份认证（`useAuth`）的操作按钮集合。在桌面端以「图标 + 紧凑单源字体标签」呈现；在移动端（`≤640px`）统一步调收敛为 36px 正方形纸印图标按钮（`--control-sm`），文字无感隐退，通过视觉印章与提示语对齐，触控命中区经由伪元素平滑扩展至 44px 标准。
- **紧凑首屏标语（Compact Hero Banner）**：书架首屏 `LibraryHero` 的响应式形态。桌面端展开双栏文学宣言与大号统计；移动端（`≤640px`）自动收紧为单行标题与单行内联统计点缀（`本数 · 本地页 · 总页`），折叠长篇说明，释放首屏 70% 纵向空间，让书单与搜索框在手机第一屏即可直接阅读。
- **标签流式抽屉（Tag Tray / Overflow Tray）**：书架标签筛选条（`TagFilterBar.vue`）中对高频标签（前 8 个）之外的溢出标签进行收纳的独立容器。通过纯 CSS 复合轨道插值无级展开，配合 WCAG 无障碍焦点圈闭，消除卡片重排跳版。
- **无级尺寸插值（Grid Track Interpolation / interpolate-size）**：基于现代 CSS Grid `grid-template-rows: 0fr ⇄ 1fr` 与 `interpolate-size: allow-keywords` 驱动的高度自适应折叠动画机制。在不依赖 JS 计算 `scrollHeight` 的前提下实现 0 布局开销的丝滑进出场。
- **自动翻页自定义秒数（Custom Auto-Turn Interval）**：阅读器自动切屏设置项。支持在预设选项（5/10/15/30秒）之外由读者就地输入 1~300 秒自定义数字，提供自适应阅读节奏。
- **HUD 暂停态指示（HUD Paused Indicator）**：阅读器右下角 HUD 在自动翻页暂停时呈现的视觉形态。由朱砂印章色 `IconPause` 矢量图标与「继续」操作文案构成，杜绝出现空白状态。
- **静态扩展名别名与边缘强缓存（Static Extension Aliasing & Edge Cache）**：为了让 Cloudflare 等通用 CDN 默认识别静态图片并激活边缘缓存，图片二进制与缩略图端点同时暴露语义化扩展名别名（`.webp`、`.jpg`），彻底杜绝无后缀动态请求反复穿透家庭宽带跨洋回源。

- **探针静音与访问日志门禁（Probe Quiet Filtering & Access Log Gate）**：Uvicorn 访问流水日志过滤机制。对容器健康探针与高频心跳在返回 200 正常时默认静音，仅在异常报错时输出；支持环境变量彻底关闭请求日志，消除控制台刷屏。
- **内外网分流（Split-Horizon DNS）**：纸间倡导的局域网与公网融合网络拓扑。同一域名在家庭局域网内通过本地 DNS 重写直连 NAS 内网 IP，享受千兆内网零延迟；公网环境下解析至 Cloudflare 命中边缘缓存，兼顾多端单点登录、PWA 离线缓存隔离与极致阅览性能。
- **单向系统事件流（Unified System Event Stream / SSE）**：基于 FastAPI 异步协程与 `asyncio.Queue` 驱动的零轮询长连接通道（`/api/events/stream`），承载新版本构建广播、后台书库变动与未来 AI 任务流式状态。在无事件时 0 CPU 挂起，断线自动重连，彻底消除前端 HTTP 定时轮询负载。
- **纸印更新气泡与双重提醒（Prompted Update Toast & Dual Notice）**：PWA Service Worker 发现新静态资产构建就绪时激活的轻量交互机制。在屏幕边缘浮现极具纸间水墨质感的非侵入提示胶囊（支持「立即装订 (刷新)」与「稍后」），并在顶栏设备微件保留朱砂徽标，沉浸翻阅时自动避让。
- **视口与唤醒回源校验（Visibility & Online Wakeup Sync）**：利用 VueUse `useDocumentVisibility` 与 `useNetwork` 在页面重获焦点或网络自愈时触发的轻量 Service Worker 脚本比对（`registration.update()`），以 0 业务接口开销确保长期待机设备自愈回源。
- **闲时意图预热（Idle & Intent Prefetching）**：跨路由异步视图组件（如阅读器）的加载策略。首屏渲染期间通过 `requestIdleCallback` 在主线程空闲时静默预热，同时在交互按钮上绑定 `pointerenter`/`focusin`/`touchstart` 意图触发，杜绝预热流量混入初始关键请求链（Critical Request Chains）。
- **静态资产传输压缩（Static Transfer Compression / GZip Middleware）**：单容器与 NAS 本地部署时后端全局挂载的动态压缩中间件（阈值 1000 字节）。将 CSS/JS/JSON 资源体积压缩 60~85%，消除未压缩静态文件对初始渲染的阻塞。
- **封面渲染预算（Cover Dimension Budget / 720px）**：封面与缩略图的物理像素规格。默认采用 720px 宽度（JPEG/WebP 高画质），完美匹配 360~375px 卡片容器在 Retina 2x 屏幕下的物理细腻度，兼顾视觉质感与网络/解码开销。
- **服务自愈与优雅退出熔断（Self-Healing Startup & Graceful Shutdown Timeout）**：本地开发环境与单容器部署的服务生命周期保护机制。启动前自动探测 8000 端口，识别并自愈回收历史残留的 Uvicorn/Python 僵尸进程；Uvicorn 配置 3 秒优雅停机超时熔断（`timeout_graceful_shutdown=3`），结合开发脚本（`dev.sh`）的进程树两阶段退出（`SIGTERM` -> 2s 缓冲 -> `SIGKILL` 兜底），彻底消除端口幽灵占用与孤儿进程。
- **单向系统事件流主动注销（SSE Active Stream Teardown）**：后端优雅停机或热重载时针对 `/api/events/stream` 挂载的长连接实施的主动熔断机制。通过向活跃的 `asyncio.Queue` 投递 `None` 退出哨兵（Poison Pill），唤醒阻塞在 `queue.get()` 上的生成器协程即刻退出并关闭 HTTP 响应流，避免持久长连接阻止 Uvicorn 关停流程。
- **响应式阶梯封面（Responsive Stepped Covers / srcset & sizes）**：基于 HTML5 `srcset`（`w` 物理宽度描述符）与 `sizes` 布局槽位规范的多阶封面分发体系。根据书架卡片槽位（~180px）、详情页 Hero 槽位（~360-480px）与设备像素比（1x/2x/3x DPR），由浏览器自主决策拉取最适宜规格图片（如 360w / 720w），兼顾移动端低内存与高分屏细腻度；严格遵循 `sizes` 显式声明守则，杜绝缺省 `sizes` 导致浏览器默认按 100vw 误拉超大原图；配合现代 `sizes="auto"`（Chrome 126+, Firefox 150+）在懒加载场景实现原生排版尺寸联动。
- **核心资产预缓存（Core Assets Precache）**：Workbox 在客户端首次加载时静默拉取并写入 CacheStorage 的核心静态代码与界面图标外壳（App Shell）。设计规范要求核心预缓存严格收敛在 1.5 MB 预算内，超大媒体资产严禁入列；客户端存储面板独立测量其所在缓存桶，与动态图片完全物理隔离。
- **物理存储正向归因（Physical Storage Attribution）**：阅览室设备离线容量的分项统计范式。由浏览器真实物理配额总用量（`usageDetails.caches` 或 `usage`）扣除独立测出的轻量 App Shell 核心资产，将读者翻阅产生的所有漫画画页、封面及插画的真实磁盘开销全额归因于「漫画阅览缓存」，消除首部抽样偏差与核心资产虚假膨胀。
- **离线插画池（Illustration Pool）**：全站看板角色与加载插画的按需运行时缓存池（`/loading-*.webp`）。通过虚拟模块编译期探测、运行时 `CacheFirst` 懒加载策略，兼顾离线可用性与首屏秒开，杜绝首屏吞吐近 10 MB 媒体的流量黑洞。
- **iOS 桌面引导（iOS PWA Add-to-Home Guidance）**：针对 WebKit 缺少 `beforeinstallprompt` 规范特性的平台交互补偿。在 iOS Safari 视口下以典雅纸面徽印呈现「Safari 分享 ➔ 加到主屏幕」引导，并在 Web Manifest 层面剔除凭据陷阱，保障 Standalone 独立视口无缝唤起。
- **Service Worker 边缘穿透（PWA Edge Bypass）**：Cloudflare 等 CDN 边缘对 `sw.js` 与 `manifest.webmanifest` 实施的绝对穿透规则（Bypass Cache）。确保客户端版本发现永远直通源站，彻底隔绝因 CDN 缓存旧 SW 引发的旧哈希静态资源 404 连锁崩溃。
- **统一构建插件架构（Modular Vite Plugins / `plugins/`）**：根目录收敛的自定义构建扩展体系。将文件系统探测、虚拟模块生成（如 `virtual:illustrations`）等非标准逻辑从 `vite.config.ts` 抽离解耦，由 `tsconfig.node.json` 全局类型纳管，保持主配置文件轻巧可读，为未来构建插件提供规范单一源。
