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
- **页面索引（Page index）**：详情页展示所有页码缩略图的区段，点击任意页直接进阅读器；为性能按 48 页增量渲染。
- **书架增量呈现（Shelf Chunked Rendering / 48 图预算）**：书架首页因每本漫画包含 4 张展示封面（1 主封面 + 3 叠牌封面），采用 12 本/批（严格对应 12 × 4 = 48 张封面图）的增量渲染机制；使用 VueUse `useIntersectionObserver` 监听底部哨兵平滑展开，将首屏 DOM 与解码压力控制在 48 图预算内，彻底避免 `content-visibility: auto`（`contain: paint`）在卡片 Hover 浮动时的像素硬截断与阴影死黑。
- **章节（Chapter / 話）**：一本多话合集里的一个独立 photo。模型上每章有 `{id,index,title,page_count,start}`，
  `start` 是该章在**全书全局页码**里的起始页。多话作品详情页按「章节目录」摆放（封面 + 章节信息），
  点某话进入「章节子路由」看该话页索引；阅读器页码/继续阅读/封面仍走全局页码。单章节作品 `chapters` 为空。
- **增量更新 / 增量追加（Incremental Refresh / Incremental Append）**：针对书库已有漫画的更新动作。
  1. 远端漫画（JM）：保持本地已有图片与元数据缓存不变，仅拉取远端新增章节或新页码；
  2. 本地自建漫画（Local）：支持向指定单话追加新页（如追加后续拆帧帧数），或追加新一话章节，系统自动重算全局页码映射与缩略图。
- **标签编辑与管理（Tag Management）**：馆长可自由为漫画（含自建与远端收录）追加自定义标签或删除已有标签，即时同步至全局标签筛选池。
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

## 阅读器

- **阅读模式（Reader Mode）**：三种——`竖向连续`（垂直滚动无吸附）、`竖向翻页`（一次一屏）、`横向翻页`（左右滑动，支持 RTL 日漫方向）。
- **每屏页数（Pages per view）**：一次显示 1 / 2 / 4 页；窄屏（<=680px）只允许 1/2。
- **图片适配（Fit）**：`适应宽度` 或 `适应高度`，影响图片在屏内的缩放方式。
- **继续阅读（Last-read）**：每本作品独立记录"上次翻到第几页"（`comic-shelf:last-read:<source>/<sourceId>`），详情页据此显示"继续阅读"。
- **自动切换（Auto-turn）**：按固定间隔（5/10/15/30 秒）自动翻到下一屏的辅助功能；开启后 HUD 常驻，手动操作重置计时。
- **阅览室暗色环境（Reader room）**：阅读器固定的深色环境（`--reader-*` tokens），不随系统亮/暗主题切换，与书房（书架首页）的亮色纸面刻意区分。

## 基础设施

- **书库数据（Library data）**：后端 `backend/data/library/` 下的本地持久化，不得删除。
- **设计令牌（Design tokens）**：`src/styles/tokens.css` 中的颜色/间距/字号/圆角/动效体系，UI 改动必须收敛到 token，禁止硬编码漂移。
- **实验开关（Experiment）**：`HTML-in-Canvas 卡片`——把书架卡片整块 DOM 绘制进 canvas 的实验性渲染路径，由实验 store 控制开关。
- **插画资产池（Illustration Pool）**：全站看板角色与加载插画的统一发现与随机轮换池（`/loading-*.webp`），支持零配置自动感知新资产。
- **环境暗印水印（Ambient Watermark）**：页面与弹窗底层的极浅角色暗纹，以纸质水印质感呈现，亮色与暗色模式下均保持极低对比度，绝不干扰前景内容与文字可读性。
- **全幅加载占位（Full-frame Page Loading）**：阅读器单页加载时与漫画页面等比撑满的骨架占位，大画幅展示装订插画并彻底消除排版跳动。
- **馆长密钥（Auth Secret / Curator Secret）**：环境变量 `COMIC_SHELF_SECRET` / `COMIC_SHELF_AUTH_TOKEN`。配置后开启门禁防护与馆长全权；未配置时保持零门槛内网模式。
- **访客密钥（Guest Secret）**：环境变量 `COMIC_SHELF_GUEST_SECRET`（可选）。配置后允许持有该口令的朋友以只读访客身份进入阅览室；若未配置访客密钥且配置了馆长密钥，则为私人独享锁死模式。
- **双口令门禁（Dual-Secret Gate）**：单输入框智能识别。未授权者（未提供有效口令者）在门禁处被 100% 拦截（HTTP 401），零元数据与图片泄露，从根源杜绝公网肉鸡与扫描滥用。
- **馆长（Curator / Admin）**：拥有纸间全部管理权限（收录、删除、标记喜欢、全量离线缓存、调整下载并发）的最高身份，由馆长密钥鉴权。
- **访客（Guest / Reader）**：持有访客口令的阅览者身份。仅拥有浏览书架、检索筛选、阅读翻页（含未缓存页的单页按需懒下载）与以图搜图权限；界面完全隐藏所有数据写入与变更操作控件，已喜欢标记作为只读印章呈现。

- **防盗链（Hotlink Protection）**：基于现代浏览器 `Sec-Fetch-Site: cross-site` 识别及 Referer 校验机制，严禁外部第三方网站跨站直连纸间作为存储桶或图片代理。
- **外部目录白名单（Allowed Directories Whitelist）**：环境变量 `COMIC_SHELF_ALLOWED_DIRS` 构筑的安全沙箱。仅允许馆长扫描导入位于该白名单内的服务器本地目录，彻底防止任意路径文件遍历与探测攻击。
- **视图过渡（View Transition）**：全站单页与局域状态变更时的平滑快照过渡机制，包括页面层级路由推进/后退（`forward` / `backward` Types）、封面到详情大画幅的「共享封面形变」、局域视图过渡（`Element.startViewTransition`）以及弹窗与按钮状态演进，无缝遵循纸间 `--duration-1/2/3` 与无障碍降级。
- **共享封面形变（Shared Cover Morph）**：书架卡片封面（`comic-cover-active`）与本子详情 Hero 封面在路由跳转时的动态连续尺寸与位置插值（神奇移动）。
- **局域视图过渡（Element-Scoped Transition）**：局限于单个组件 DOM 子树内的独立状态过渡（如图片装订就绪、收藏按钮红心状态、并发步进器），不阻塞整页交互与全局重绘。
- **缩略图预热与渐进呈现（Thumbnail Pre-warming & Progressive Reveal）**：详情页与子章节页通过 360px JPEG 缩略图（48 页/批增量渲染）按需下发，同时在后端磁盘完成原图持久化解密；阅读器直接读取本地文件并通过 GPU 硬件加速透明度淡入呈现，达成 0 远端重复请求与毫秒级秒开。
- **书架静默回源（Shelf SWR / Stale-While-Revalidate）**：书架首页在内存已有数据时先即时呈现现有卡片，后台静默向后端对齐最新状态，仅在初次无数据时展示骨架屏，杜绝切页时卡片重载与骨架屏闪烁。
- **请求中止与竞态隔离（Request Abort & Race Cancellation）**：利用 `AbortController` 与组件生命周期绑定，在瞬时进出页面或并发触发检索（如以图搜图重选、排行榜切档）时主动取消上一轮未完成的网络请求，避免无效流量与状态覆盖。
- **字阶底线与自适应排版（Typography Floor & Fitting）**：纸间对单行文字自适应（如阅读器顶栏标题、车号徽章）设立的排版保护原则。在采用现代弹性缩放防溢出的同时，强制受限于离散字阶底线（≥ `--text-xs` / 12px）；书架网格阵列坚守固定字阶与多行截断，杜绝卡片间字号忽大忽小破坏视觉节律。
- **纸间统一图标集（Unified Archive Iconography）**：全站矢量图标单源字典体系。统一步调为暖纸细线条描边与朱砂印章质感（1.8px 细描边 / 24px 网格），彻底杜绝跨平台字符（`✕`/`✓`/`×`）渲染字重撕裂与重复内联 SVG 碎片。
- **现代浮层体系（Modern Floating System）**：基于 HTML Popover API 与 CSS Anchor Positioning 规范构建的无依赖顶层浮动交互基建，包含 `Modal`（强中断模态对话框）、`AppPopover`（富交互锚定浮层）、`AppDropdown`（操作选单与选择器）与 `AppTooltip`（`popover="hint"` 轻量气泡提示），彻底消除散落的绝对定位胶水代码与 z-index 冲突。
- **气泡提示（Tooltip / AppTooltip）**：`popover="hint"` 声明式轻量提示微件，专门承载辅助性只读文案；覆写浏览器 User-Agent 样式实现零幽灵滚动条；内置**悬停安全桥（Hover Bridge）**，遵循 WCAG 2.1 1.4.13 国际标准，支持光标无缝移入划词选读与复制。复杂表单、按钮列表与多级菜单严格收敛至 `AppPopover` / `AppDropdown`。
- **悬停安全桥（Hover Bridge）**：气泡与触发源之间的无形触控延伸区（纯 CSS 伪元素实现）。无缝填补两者之间的物理 margin 空隙，确保光标滑入气泡时轨迹全程处于命中区，彻底杜绝穿过空白缝隙时的闪退痛点。
- **顶层层级与轻量失焦关闭（Top Layer & Light Dismiss）**：利用浏览器原生顶层特性，天然解决浮层被父级 `overflow: hidden` 或 `contain: paint` 截断的问题；原生支持点击外部空白或 Esc 键无缝自动收起。
- **锚定回退感知与滑动动效（Anchor Fallback & Sliding Indicator）**：利用 `container-type: anchored` 与 `@container anchored(fallback: flip-block)` 纯 CSS 感知碰撞翻转自适应箭头与安全桥；借助动态 `anchor-name` 实现分段选项卡与选单项的纯 CSS 物理滑动胶囊动效。
- **回到顶部（Back to top / Scroll-to-top）**：纸间长页面（书架、多章节详情）的标准导航辅助微件。采用 VueUse `useWindowScroll` 监听视口（默认 >400px 阈值浮现），以正圆暖纸印章质感呈现，支持自适应 `prefers-reduced-motion` 与键盘焦点平滑转移，阅读器沉浸模式下自动隐身。
- **防退化门禁（Regression Safety Net）**：全仓多层自动化防御机制，包含前端 `vp check`（TS/Vue 静态检查）、后端 `pnpm test:py`（AST 符号自检 + 真实中间件链路与多章节单测），杜绝改动引发核心功能断裂。
