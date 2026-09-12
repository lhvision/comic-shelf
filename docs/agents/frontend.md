# 前端规则与阅读器行为（详细规则）

## 6. 前端文件地图

| 文件                                               | 职责                                                                                                                                                           |
| -------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `src/views/LibraryView.vue`                        | 书架视图编排：Hero / 导入 / 筛选工具栏 / 卡片网格                                                                                                              |
| `src/views/DiscoveryView.vue`                      | 发现页视图编排：分段榜单切换、分类筛选、榜单卡片网格与一键收录                                                                                                 |
| `src/views/ComicDetailView.vue`                    | 详情视图编排：封面流 / 元数据 / 操作栏 / 章节目录 / 页面索引                                                                                                   |
| `src/views/ChapterView.vue`                        | 章节子路由：某话章节头（本话缓存进度/重命名/删除管理）+ 该话 PageIndexGrid                                                                                     |
| `src/views/CreateComicView.vue`                    | 自建图集工坊：单话/多章节多图拖拽暂存、服务器路径导入、元数据与封面编排                                                                                        |
| `src/views/ReaderView.vue`                         | 阅读器视图编排：模式切换、DOM 分屏挂载、HUD / 顶栏 / 设置面板接线                                                                                              |
| `src/composables/useAuth.ts`                       | 访问鉴权与门禁状态机：Cookie/Token 会话、状态探测、401 拦截联动                                                                                                |
| `src/composables/useGuestPasses.ts`                | 访客通行证名册管理状态机：登记印发、Token 密钥换新、有效期延长、启停与设备踢除联动                                                                             |
| `src/composables/useDiscovery.ts`                  | 发现页排行榜状态机：周榜/月榜/日榜/总榜拉取、分类过滤与收录状态追踪                                                                                            |
| `src/composables/useUploadQueue.ts`                | 受限并发批量上传队列控制器（3 路 Worker 并发、细粒度进度与取消支持）                                                                                           |
| `src/composables/useFileStaging.ts`                | 多图与画页暂存：自然文件名数字排序、格式过滤、`useFileDialog` + `useDropZone` 聚合                                                                             |
| `src/composables/useLocalWorkshop.ts`              | 自建漫画工坊状态机：服务器本地路径扫描、白名单过滤、单话/多章节模式切换与元数据暂存                                                                            |
| `src/composables/useLibrarySync.ts`                | 书架筛选与流式分页协同：URL Query 双向同步、防抖拉取服务端分页、全貌统计联动与 SSE 跨端变动感知                                                                |
| `src/composables/useLibraryFilter.ts`              | 书架检索与多维筛选：模糊搜索、标签频率统计、多模式排序、阅读状态单选三态（全部/在读/已读/未读）、喜欢过滤与以图搜图映射                                        |
| `src/composables/useSearchCommands.ts`             | 快捷指令中枢与命令胶囊状态机：斜杠触发、模糊过滤、键盘选中、模式切换与列表冻结                                                                                 |
| `src/composables/useDialogueSearch.ts`             | 分镜台词全文检索状态机：短词防爆守卫、防抖请求、高亮片段与气泡定位映射                                                                                         |
| `src/composables/useShelfState.ts`                 | 书架会话上下文记忆单例：跨路由纵向视口滚动锚定、展开批次、归档专匣开闭、筛选条件保持与主动置顶重置                                                             |
| `src/composables/usePaginationFold.ts`             | 画卷与书架分批折叠展开状态机：受控步进铺开（24页/12本）、60本安全刹车、显式余量徽印计算与平滑滚顶自愈                                                          |
| `src/composables/useReaderRecommendations.ts`      | 阅读器末页接卷推荐：启发式元数据权重评分（同作者/同原作/共有标签/在读状态）与未读作品遴选                                                                      |
| `src/composables/useImageSearch.ts`                | 以图搜图状态机：文件上传、剪贴板粘贴、拖拽、置信度与状态管理                                                                                                   |
| `src/composables/useReaderData.ts`                 | 阅读器数据流与路由状态机：元数据拉取、`AbortController` 竞态取消、URL 同步与返回路径                                                                           |
| `src/composables/useReaderPaging.ts`               | 阅读器分页与作用域：分组切片、全局/本地页码映射、跨话首尾探测与边界计算                                                                                        |
| `src/composables/useReaderNavigation.ts`           | 阅读器导航与定位：多屏滚动定位、进度计算、横向滚轮适配、跨话切换                                                                                               |
| `src/composables/useReaderKeyboard.ts`             | 阅读器键盘与全屏：按键映射（翻页/切话/首末页）、`useFullscreen` 与 ESC 退出                                                                                    |
| `src/composables/useAutoTurn.ts`                   | 阅读器自动翻页：倒计时状态机、节拍器、页面可见性联动与暂停/继续                                                                                                |
| `src/composables/useReaderChrome.ts`               | 阅读器顶栏/HUD 延时隐藏与交互唤醒控制                                                                                                                          |
| `src/composables/useChapterNavigation.ts`          | 详情/子路由章节导航：锁定章节、章节切片、48 增量渲染、「继续阅读」文案                                                                                         |
| `src/composables/useChapterCache.ts`               | 漫画全书与分话后台缓存轮询与进度状态编排：任务驱动按需轮询、页码 cached 就地对齐与任务生命周期收敛                                                             |
| `src/composables/useReaderSettings.ts`             | 阅读器设置全局状态单例持久化（VueUse `createGlobalState`）                                                                                                     |
| `src/composables/useLastRead.ts`                   | 每部作品继续阅读页码持久化读写                                                                                                                                 |
| `src/composables/useToast.ts`                      | 全局轻量印章通知 Toast 状态机（支持 info / error / success 三态提示）                                                                                          |
| `src/composables/useOfflineStorage.ts`             | 端侧离线物理存储探测与分级清理状态机（StorageManager + CacheStorage 统计）                                                                                     |
| `src/composables/useOfflineSync.ts`                | 客户端离线网络感知与记账对齐流水线：断网记账、联网自愈自动回写与 SWR 书架刷新调度                                                                              |
| `src/utils/offlineDb.ts`                           | 端侧轻量 IndexedDB 引擎（comic-shelf-meta）：书架快照/Facets 分区存储、200 本 LRU 漫画详情淘汰与带 userId 签名的离线操作事务队列                               |
| `src/composables/usePwaInstall.ts`                 | PWA 安装与独立应用视口检测状态机（`beforeinstallprompt` + Standalone）                                                                                         |
| `src/composables/usePwaUpdate.ts`                  | PWA Prompt 模式生命周期状态机：更新捕获、装订刷新与视口唤醒自愈探测                                                                                            |
| `src/composables/useSystemEvents.ts`               | 任务驱动型系统事件流（SSE）与多标签广播（BroadcastChannel）：按需长连接编排、藏书变动多端与本地秒级同步                                                        |
| `src/composables/useIdlePrefetch.ts`               | 闲时意图预热状态机：利用 requestIdleCallback 在主线程空闲时静默预拉取目标路由 chunk                                                                            |
| `src/composables/useIllustrationPool.ts`           | 全站看板角色与加载插画发现池：虚拟模块挂载、按需加载、缓存感知与随机防抖轮换                                                                                   |
| `src/composables/useViewTransition.ts`             | 全局与局域视图过渡门面封装：`Promise.withResolvers` + `Promise.try`、异常自动捕获兜底与抢占自愈                                                                |
| `src/composables/useCoverTransition.ts`            | 书架卡片与详情 Hero 共享封面形变（`comic-cover-active`）动态类名与过渡时机调度                                                                                 |
| `src/composables/useBrandIcon.ts`                  | 品牌与动态多态矢量图标映射与解析器                                                                                                                             |
| `src/pwa.ts`                                       | PWA 与 SSE 系统事件流统一初始化入口                                                                                                                            |
| `src/components/curator/GuestModal.vue`            | 馆长专属访客簿全屏模态：名册检视、设备抽屉、印发表单与凭证展示装配外壳                                                                                         |
| `src/components/curator/guest/`                    | 访客簿模块化组件群：名册卡片、设备抽屉、印发表单、凭据展示与时间格式化                                                                                         |
| `src/components/storage/`                          | 存储管理模块化组件群：头部卡片、PWA 装订、刻度槽与双级清理危险区                                                                                               |
| `src/components/import/`                           | 收录面板模块化组件群：通用远端收录（`ImportRemoteTab`，参数化驱动禁漫/哔咔等）、本地自建（`ImportLocalTab`）与下载并发步进器                                   |
| `src/components/UpdateBanner.vue`                  | 纸间新卷本装订更新提示横幅（水墨胶囊悬浮卡片、沉浸阅读器自动避让）                                                                                             |
| `src/components/GateView.vue`                      | 全屏 Zero-DOM 门禁大门视图：反 DevTools 篡改哨兵与三态表单编排外壳                                                                                             |
| `src/components/gate/`                             | 门禁模块化表单群：初始口令表单、首访认领自设 PIN 表单、已认领 PIN 验证表单                                                                                     |
| `src/components/Modal.vue`                         | 通用顶层模态对话框：基于 HTML5 原生 `<dialog>` Top Layer 与无障碍焦点圈闭，支持声明式关闭指令 (`commandfor`)、焦点记忆自动返还、防穿透微弹反馈与子表单安全防护 |
| `src/components/SegmentedTabs.vue`                 | 典藏分段选项卡：支持泛型 `TabItem<T>`/字符串、左右/Home/End 键导航与多尺寸                                                                                     |
| `src/components/AppButton.vue`                     | 通用典藏按钮：支持 primary / secondary / soft / ghost / danger 多种变体                                                                                        |
| `src/components/AppChip.vue`                       | 通用微件胶囊：多态无障碍渲染（`<span>` ⇄ `<button aria-pressed>`）、标签/筛选/计数/删除单一真理源                                                              |
| `src/components/AppIcon.vue`                       | 零分支矢量图标分发器（基于 `<component :is="ICON_MAP[name]">` 动态渲染）                                                                                       |
| `src/components/icons/`                            | 纸间统一矢量图标集（`BaseIcon.vue` 底座 + 23 个原子 `Icon*.vue` 组件）                                                                                         |
| `src/components/AppTooltip.vue`                    | 现代声明式轻量气泡提示组件（Popover API + CSS Anchor + 悬停安全桥）                                                                                            |
| `src/components/AppTextClamp.vue`                  | 统一文本多行自适应截断微件：行数预算约束、零开销延时挂载与 WCAG 悬停安全桥纸印气泡                                                                             |
| `src/components/AppProgressBar.vue`                | 统一典藏进度条微件：track/line/gauge 三态、GPU transform 驱动与心理学先快后慢拟真未定态                                                                        |
| `src/components/AppPopover.vue`                    | 现代顶层锚定交互浮层（自动碰撞翻转、轻量失焦关闭、Invoker Commands API 声明式触发器与焦点归还）                                                                |
| `src/components/library/SearchCommandChip.vue`     | 朱砂印章式快捷命令胶囊：视觉前缀提示、独立关闭按钮与无障碍状态展示                                                                                             |
| `src/components/library/SearchCommandMenu.vue`     | 斜杠快捷指令选择面板：Combobox 键盘导航、指令描述与分类高亮                                                                                                    |
| `src/components/library/DialogueSearchPopover.vue` | 台词检索结果浮层：分镜卡片、高亮片段安全渲染与直达阅读器锚定                                                                                                   |
| `src/components/StoragePopover.vue`                | 阅览室设备与离线存储管理浮层（3px平直刻度槽/分项账单/双级清理/两步确认）                                                                                       |
| `src/components/ReaderPassPopover.vue`             | 访客借阅证浮层：读者身份印章展开、专属阅读统计与平滑交还凭证退出                                                                                               |
| `src/components/AppDropdown.vue`                   | 现代操作选单与选择器（无依赖 Top Layer + 键盘导航）                                                                                                            |
| `src/components/BackToTop.vue`                     | 正圆暖纸印章回到顶部微件（VueUse `useWindowScroll` 视口监听）                                                                                                  |
| `src/components/CacheProgress.vue`                 | 实时缓存进度条与后台任务状态指示                                                                                                                               |
| `src/components/ToastStack.vue`                    | 全局轻量水墨印章通知堆叠容器（挂载于根视口，自适应多通道 Toast 消息排队）                                                                                      |
| `src/components/detail/EditMetadataModal.vue`      | 典藏资料与标签编排弹窗（实时修改标题、作者、4 张封面展示页码、标签增删）                                                                                       |
| `src/components/detail/AppendPagesModal.vue`       | 本地漫画增量追加弹窗（追加至已有话或新建分话、支持网页上传/服务器路径）                                                                                        |
| `src/components/detail/ReplacePagesModal.vue`      | 全本画页重新装订弹窗：支持网页多图上传与服务器本地目录秒级替换、重新装订保护提示                                                                               |
| `src/components/discovery/DiscoveryCard.vue`       | 榜单漫画卡片：排名徽章、原站外链、分类胶囊与一键收录/在库直达                                                                                                  |
| `src/components/form/TagManager.vue`               | 交互式标签管理器（Chip 展示、Enter/空格添加、SVG 居中删除、热门快选推荐）                                                                                      |
| `src/components/form/CoverIndicesPicker.vue`       | 4 张封面展示页码选定器（4 槽位数值输入、实时越界纠偏与默认值安全回退）                                                                                         |
| `src/components/detail/ChapterIndex.vue`           | 章节目录整段：head + 分批卡片网格（首屏 24 话增量折叠、受控步进展开/收起、展开记忆）                                                                           |
| `src/components/detail/PageIndexGrid.vue`          | 画页索引网格：平铺画页卡片流 + 末尾独立 +余 N 纸签卡，受控步进展开与平滑回滚收整                                                                               |
| `src/components/detail/PageTile.vue`               | 单页索引独立画页瓦片：缩略图渐进呈现、多选/操作插槽与尾格余量徽印解耦                                                                                          |
| `src/components/detail/ChapterCard.vue`            | 目录单卡：第一页封面缩略图（失败回落书脊）+ 序数/标题/页数 + 独立离线缓存操作按钮                                                                              |
| `src/components/detail/ChapterSwitcher.vue`        | 章节切换条（用于 ChapterView 内跳话）：横向 chips + 方向键 + `useScroll` 智能滚卷导航                                                                          |
| `src/components/FavoriteButton.vue`                | 喜欢标记按钮（书架卡片 / 实验卡片 overlay）                                                                                                                    |
| `src/components/ComicPageImage.vue`                | 每页图片 loading / error / retry 兜底                                                                                                                          |
| `src/components/CoverCarousel.vue`                 | 封面轮播：基于物理中心点 JIT 居中计算、直接点击对齐与 Chrome 135+ CSS Carousels (::scroll-marker) 渐进增强                                                     |
| `src/components/reader/ReaderViewport.vue`         | 阅读器画卷视口：三种排版模式（连续/竖翻/横翻）与分屏画页 DOM 渲染                                                                                              |
| `src/components/reader/ReaderChapterBanners.vue`   | 阅读器跨话悬浮横幅：话首「← 上一话」与话末「本话完 · 下一话 →」导航交互胶囊                                                                                    |
| `src/components/reader/ReaderEndCard.vue`          | 阅读器末页结尾卡片：视口真实触达感知（`useIntersectionObserver`）、暗室响应式接卷推荐三联卡与双向离开出口                                                      |
| `src/components/reader/ReaderFloatingPill.vue`     | 阅读器浮动画卷页标：条漫无缝拼接模式下的非侵入式页码浮标，滚动感应淡入淡出与 HUD 互斥避让                                                                      |
| `src/components/reader/ReaderLoadingState.vue`     | 典藏 WebP 呼吸微光加载组件（整本首屏与单页渐进式加载）                                                                                                         |
| `src/styles/tokens.css`                            | 设计 token 与原生 CSS 样式体系                                                                                                                                 |
| `src/stores/library.ts`                            | 书库 Pinia store（SWR 保持、静默回源、后台缓存轮询与自动清理收录提示）                                                                                         |
| `src/stores/settings.ts`                           | 下载并发与运行时设置 store                                                                                                                                     |

## 6.5 页面索引性能策略与全链路图片流水线闭环

### 架构流转图

```
                        ┌──────────────────────────────────────────────┐
                        │              远端 Provider 数据源             │
                        └──────────────────────┬───────────────────────┘
                                               │ (仅首次触发下载 1 次)
                                               ▼
                        ┌──────────────────────────────────────────────┐
                        │        本地磁盘解密持久化 pages/page_0001.webp  │
                        └──────────────┬───────────────────────────────┘
                                       │
                    ┌──────────────────┴──────────────────┐
                    ▼                                     ▼
      ┌───────────────────────────┐         ┌───────────────────────────┐
      │   详情页 / 章节子路由     │         │       沉浸式阅读器        │
      │       页面索引目录        │         │      ComicPageImage       │
      └─────────────┬─────────────┘         └─────────────┬─────────────┘
                    │                                     │
      • 360px WEBP 缩略图（~15KB）          • 本地磁盘原图 0 远端请求秒开
      • useIntersectionObserver             • 缇雅 30s 全长动图装订卡片
        (24 页/批增量懒展开)                  • GPU 硬件加速 opacity 交叉淡显
      • content-visibility: auto            • 视口外页面跳过渲染与 Paint
```

- 详情页页面索引**不要一次渲染全部**：`ComicDetailView` 与 `ChapterView` 默认只渲染前 24 个 tile（`CHAPTER_PAGE_STEP = 24`），
  滚动到 sentinel 自动加载下一批，并显示“已显示 X / Y 页”。
- tile 使用 `/pages/{n}/thumbnail`（360px JPEG，服务端懒生成并缓存），
  不要用 `/pages/{n}/file` 原图做缩略图。
- **分级渲染与隔离准则**：
  - 页面索引 tile、章节卡片与 reader spread 节点众多，使用 `content-visibility: auto`；
  - 书架卡片（`ComicCard`）：3D 扇形副封面采用交互延迟加载（`@pointerenter.once` / `@focusin.once`），初始仅请求主封面（12 本 = 12 个请求，降低 75% 初始并发）；**严禁使用 `content-visibility: auto`**（防 `contain: paint` 剪切 Hover 浮动与柔和阴影），改用 `contain: layout style` + `container-type: inline-size` 配合 **12 本/批增量渲染**。
  - 所有存在文本截断的按钮、下拉框（`select`/`option`）、章节标题与元数据必须 100% 绑定原生 `:title` 属性，确保 a11y 与信息可读性。
- 页面索引虚拟化与渲染：性能优化坚守 thumbnail + 增量 DOM（`CHAPTER_PAGE_STEP = 24` + sentinel 按需加载），禁止为 tile 引入 Canvas 渲染层以防显存暴涨与无法复用原生图片解码缓存。
- **预热机制（Pre-warming）**：后台预缓存任务在拉取原图的同时自动生成 360px 缩略图，详情页访问 100% 命中暖缓存；后端同时配备 `COMIC_SHELF_THUMB_CONCURRENCY` 门禁，防止多用户并发动态生成导致 CPU 击穿。进入阅读器可 100% 本地秒开。禁止在阅读器大图使用 LQIP（模糊马赛克底图）以防破坏纸质质感。
- **意图预热与即时元数据占位（Prefetch on Intent & SWR Hero Placeholder）**：
  - **意图预热（卡片与按钮）**：`ComicCard` 在 `@pointerenter.once` / `@focusin.once` / `@touchstart.passive.once` 时静默预热 `ComicDetailView.vue` 路由 chunk 与 `api.detail` 接口（写入 `useMemoize` 内存）；`DetailActionBar` 在悬停阅读按钮时同步预热 `ReaderView.vue`；
  - **SWR Hero 占位（消灭白屏/闪烁）**：从书架跳入详情页时，初始直接调用 `createPlaceholderDetail(store.byId(source, sourceId))` 渲染 Hero 头部（真实标题、封面轮播与元数据），使浏览器 View Transition 精准捕获到真正的 `comic-cover-active` 并连贯执行共享封面形变（Shared Cover Morph），彻底杜绝捕获纯灰骨架屏导致的二次闪烁。

## 6.6 多来源导航

- AppHeader 的导航不是写死的：启动时请求 `/api/providers`，渲染
  “全部” + 每个 provider 一个来源栏位。
- 目前 `01 禁漫`；以后接入哔咔，只要注册 provider 并提供 `short_label`，
  前端会自动出现 `02 哔咔`，数据目录会自动使用 `library/picacg/...`。
- 来源过滤通过路由 query 实现：`/?source=jm`、`/?source=picacg`。

## 6.7 多章节行为（章节目录 + 章节子路由）

- **模型**：`ComicDetail.meta.chapters[]`（`{id,index,title,page_count,start}`）描述多章节；
  `meta.pages` 永远是**全书拍平的全局页码表**，单章节 `chapters` 为空。
- **详情页（多话）只摆章节目录**：`ComicDetailView` 当 `chapters.length > 1` 时渲染
  `ChapterIndex`（目录卡片：该话第一页封面 + 序数/标题/页数），**不铺开几千页**；
  点某话进入章节子路由。
- **章节子路由**：`/comic/:source/:id/chapter/:chapterId` → `ChapterView.vue`，
  只渲染这一话的 `PageIndexGrid`（复用 48 页增量 + 章节前缀计数），头部带
  上一话/下一话 pager + `ChapterSwitcher` 跳话；目标话不存在/单章节时自动回详情页。
- **单话详情页零变化**：`chapters` 为空时 `ComicDetailView` 直接渲染全部
  `PageIndexGrid`（每页平铺），与旧版一致。
- **锁定章节**：`useChapterNavigation.setChapterById(id)` 从子路由进入时锁到某话；
  详情页单话场景 `activeChapter == null`，切片即全书。
- **页索引 tile 链接全局页号**：`PageTile` 的 `RouterLink` 仍是
  `/read/{全局页}`，因此点任意话的任意页都能进正确的阅读位置。
- **阅读器**：`ReaderView` 用 `currentPage`（全局页）在 `chapters` 里找所属章节，
  顶栏显示“第 X 話 · 标题”（`ReaderTopBar.chapter`）。
- **metadata**：`MetadataPanel` 多章节显示“共 N 话”，单章节显示“单话”。

## 6.8 多章节的跨话阅读与信息（T08/T09/T10）

- **跨话翻页（T08）**：`ReaderView` 读到某话末页时，底部浮现「本话完 · 下一话 →」横幅
  （`reader-chapter-next`，`--reader-*` token）；键盘 `N/n` 下一话、`P/p` 上一话。
  仍走 `goToPage(chapter.start)` 全局页码，跨话不重置任何设置。
- **章节条语义（T09）**：`ChapterSwitcher` chip 按 `data-state`（past/active/upcoming）区分，
  当前话显示「当前」徽标、已翻过的淡化；长标题 `text-overflow: ellipsis` + `title` 完整文案。
- **章节级缓存（T10）**：`ComicDetailView` 按 `meta.pages[].cached` 汇总每话本地页数，
  传 `chapterCache` 给 `ChapterIndex→ChapterCard` 显示「本地 N%」。
- **章节封面（T17）**：`ChapterCard` 封面走 `GET /chapters/{id}/cover` 服务端端点
  （池化在 `covers/chapters/`），不再是每话第一页的 thumbnail 端点。
- **危险操作**：移除本地不再占操作栏大按钮，收进「更多 ⋯」菜单 + `Modal` 强二次确认
  （需勾选「我已了解」），见 `DESIGN_NOTES §12`。
- **⚠️ composable 解构约束**：`useChapterNavigation` 这类带回传 Ref 的 composable，
  在 `ChapterView` 里必须**解构到 setup 顶层**再传给子组件/模板；直接 `nav.xxx` 不会自动
  unwrap，会触发 `ChapterSwitcher.findIndex is not a function` 且图片不显示（`DESIGN_NOTES §13`）。

## 6.9 章节缓存状态同步与缩略图落盘感知（Thumbnail-Implied Page Caching）

- **缩略图落盘即缓存（Thumbnail-Implied Caching）**：
  当用户进入章节子路由或浏览画页网格时，`PageTile.vue` 请求 `/thumbnail` 缩略图。在后端实现中，生成缩略图会按需解密并落盘完整画页，将服务端的 `page.cached` 置为 `true`。前端通过 `PageTile` 的 `@load="onThumbLoad"` 监听，当发现 `!props.cached` 时向上触发 `cached(index)`；`PageIndexGrid` 将其转发为 `@page-cached`，由 `ChapterView` 与 `ComicDetailView` 捕获并就地更新内存中对应 `pages[index].cached = true`，同时累加 `cached_pages` 与校验 `cache_complete`，彻底消除“缩略图已渲染但徽标仍为待缓存”的视觉脱节。
- **单话粒度缓存轮询**：
  `ChapterView.vue` 内触发章节缓存时，轮询端点必须严格请求 `api.chapterCacheProgress(source, sourceId, chapterId)`，严禁调用全书级别的 `api.cacheProgress`，防止进度百分比与单话状态失真。
- **客户端内存缓存穿透（Bypass Cache）**：
  `api.detail` 在底层使用了 `useMemoize` 进行数据复用。在后台缓存任务完成或服务端推送数据变更时，重新拉取详情必须传递 `{ bypassCache: true }`（触发内部 `memoizedDetail.delete` 并回源重新请求），防止前端读到旧的未缓存快照。
- **任务驱动 SSE 与 BroadcastChannel 双轨同步**：
  `ChapterView` 与 `ComicDetailView` 均通过 `useSystemEvents` 监听 `lastLibraryEvent`（服务端 `library_changed` SSE 事件流与同源多标签页 `BroadcastChannel` 本地事件通道）。
  - **按需长连接拉起**：当触发后台缓存或导入时，通过 `beginTask` 动态建立长连接；全部任务完成后延迟 5 秒（`TASK_TEARDOWN_COOLDOWN_MS = 5000`）防抖注销，常态浏览保持 0 pending 请求；
  - **跨标签页零流量直达**：本标签页完成操作时，调用 `broadcastLocalChange` 向其他同源标签页同步，接收端收到匹配当前漫画的事件后自动执行后台静默对账（`load(true, true)`）。

## 7. 阅读器当前行为

阅读设置采用**双轨制架构（Dual-Scope Architecture）**：

- **全局基线（Global Baseline）**：保存在 `localStorage['comic-shelf:reader-settings:v1']`；
- **单本专属偏好（Per-Comic Overrides）**：保存在 `localStorage['comic-shelf:reader-overrides:v1']`（以 `source:source_id` 为键，FIFO 封顶 100 条）；
- **历史脏基线自愈标记**：`localStorage['comic-shelf:baseline-healed:v1']`。

设置面板通过顶部双轨胶囊 `[ 📖 本作偏好 ]` 与 `[ 🌐 全局默认 ]` 透明呈现，支持即改即分离、实时视口联动（Live Sync）与一键「恢复跟随全局」。

```ts
{
  mode: 'vertical-continuous' | 'vertical-paged' | 'horizontal',
  fit: 'width' | 'height',
  pagesPerView: 1 | 2 | 4,
  direction: 'ltr' | 'rtl',   // 横向模式：左→右 或 日漫右→左
  autoTurn: boolean,
  autoTurnInterval: number,   // 1~300 秒，预设 5 | 10 | 15 | 30 秒
  seamless: boolean,          // 仅 vertical-continuous 下有效，条漫无缝拼接
}
```

- `vertical-continuous`：无 snap，连续自然卷轴流（Webtoon / 条漫流）；`fit: 'width'` 下宽度 100% 且高度随图片原生比例自适应伸展，`fit: 'height'` 限制单屏最大高度；彻底解除与 `vertical-paged` 的尺寸耦合。
- `vertical-paged`：`y proximity` + `scroll-snap-stop: always` 单屏吸附，Flexbox 居中且约束 `max-height: 100dvh`；不要改回 `y mandatory` 或容器级 `scroll-behavior: smooth`，快速滚轮会卡在页缝附近。
- `horizontal`：x snap，一屏 1/2/4 页 grid（窄屏只给 1/2），左右滑动切屏。
- 每屏页数按视口开放：`min-width: 681px` 的 PC/平板允许 1/2/4 页，更窄屏幕（<681px）默认收敛为 1 页（可选 1/2 页）；窄屏下 4 页配置自动降级单列渲染。
- 移动端沉浸交互：彻底废除顶部中央悬浮遮挡画面的折叠按钮，统一由画面点击/轻触（Tap/Click-to-Toggle）唤醒与收起顶栏及 HUD；连续滚动模式下滚动不反复弹顶栏，无操作 2.6s 自动淡出。
- 移动端安全区全覆盖：顶栏与底栏 HUD 均计算 `env(safe-area-inset-top/bottom/left/right)`，移动端跨话悬浮横幅自动垫高避让 HUD。
- 点击详情页/章节页进入阅读器后，精准定位到目标页（`useReaderData` 先执行 `loading=false` 确保 DOM 视口挂载，`onLoaded` 在 `await nextTick()` 后执行 `scrollToGroup('instant')` 物理定位；缺省 `:page` 时优先回落至 `lastRead.value` 进度；纵向连续模式下由 `recalibrateTargetOffset` 在图片异步加载时微调位移）。
- `.reader-view` 必须保留 `timeline-scope: --reader-scroll`：进度条是 `.reader-scroll` 的兄弟节点，
  scroll timeline 只有提升作用域后才能跨子树引用；
- **全场景 CSS 滚动驱动双轨架构**：
  - 竖向排版（连续/翻页）绑定 `scroll-timeline-axis: block`，横向排版动态切换 `scroll-timeline-axis: inline`；
  - 横向 RTL（日漫模式）通过 `@keyframes reader-progress-rtl` 镜像翻转（`scaleX(1) → scaleX(0)`）与 `transform-origin: 100% 50%` 确保从右向左阅读时进度条平滑正向生长；
  - 竖向连续模式在非无缝状态下应用 `animation-timeline: view()` 与 `animation-range: entry 0% entry 100%`，提供纸质微显入场动效（`opacity: 0.15 → 1`、`translateY: 6px → 0`），并在 `prefers-reduced-motion: reduce` 下自动静默降级；无缝长卷模式通过 `:not([data-seamless='true'])` 排除进场位移，杜绝滚动接缝抖动；
  - JS 轨通过 `useReaderNavigation` 引入 `requestAnimationFrame` 调度节流，杜绝主线程 Layout Thrashing。
- 竖向连续模式的 `.reader-spread` 不要加 `min-height: 100dvh`，否则移动端每页后会留整屏空白；标准模式下页间间隔由后续 spread 的 `padding-top` 控制，无缝模式下间距归零并施加 `-1px` 亚像素微咬合与浮动页标（`ReaderFloatingPill`）。
- 自动切换按“屏”计时：默认关闭，间隔 5/10/15/30 秒（支持 1~300 秒自定义）。开启后右下角倒计时 HUD 常驻，
  手动翻页/滚动会重置倒计时；设置面板打开或页面切后台时暂停，最后一屏自动停止。
- 倒计时 pill 默认只显示数字，宽度与页码指示器一致；桌面 hover / 键盘 focus 时原位显示“暂停”，
  点击切换暂停/继续。移动端没有 hover，直接点击倒计时小圆暂停，暂停后显示“继续”。
- 移动端和矮视口下 HUD 改为横向：左侧 32px 倒计时小圆，右侧横向页码指示器
  （上一屏 / 页码 / 下一屏，按钮同为 32px），避免右下角 HUD 遮挡漫画画面。
- `onKeydown` 必须在 `settingsOpen` 时提前返回（除 Escape），否则方向键/Space 会翻动面板背后的页面，
  且会劫持 switch 等原生 button 的 Space 激活。
- 自动切换的滚动行为需尊重 `prefers-reduced-motion: reduce`，此时用 `behavior: 'auto'`。

## 7.5 每页 loading 兜底与视觉

- 采用 4 张现代化轻量 WebP 插画（`/loading-1.webp` ~ `/loading-4.webp`）。
- `ReaderView` 每次进入一本漫画时随机选定一个 variant（1~4），并把同一个值传给该本
  所有 `ComicPageImage`；因此整本书 loading 插画一致，不会逐页乱跳。
- `ReaderLoadingState.vue` 封装磨砂框、轻柔斜向光斑（`shimmer-sweep`）、呼吸微动与朱砂色呼吸指示点，
  统一用于整本首屏加载与单页渐进式加载（`compact` 模式）；动效在 `prefers-reduced-motion` 下自动关闭。
- `ComicPageImage.vue` 给普通 `<img>` 页面提供：居中动态 loading、加载后淡入渐显与失败重试。

## 8. 淘汰反模式：HTML-in-Canvas 列表渲染（Deprecated & Rejected）

- **技术评估与实机复盘**：曾探索基于 WICG HTML-in-Canvas 规范（Chromium 155+ 实验特性 `chrome://flags/#canvas-draw-element`，`drawElementImage` 与 `<canvas layoutsubtree>`）将书架卡片绘制进 Canvas。实机验证证实其不适合列表/卡片型 UI，已于主干全量拔除，严禁后续再次引入：
  1. **GPU 显存暴涨与上下文丢失风险**：Retina 屏（2x~~3x DPR）下单张卡片 Canvas 需分配独立 GPU Backing Store 离屏位图，书架 50 本漫画即额外占用 70MB~~120MB 未压缩显存，导致移动端与集成显卡面临 WebGL/Canvas 上下文丢失（Context Loss）风险；
  2. **ResizeObserver 自激震荡（无限增长死循环）**：`<canvas>` 为固有尺寸可替换元素（Replaced Element），在 CSS Grid 下其 `canvas.height` 设置会撑开 Grid 轨道高度，进而再次触发 `ResizeObserver` 回调，形成严重的无限尺寸膨胀恶性循环；
  3. **交互语义与无障碍完全退化**：Canvas 丢失文本可选性、键盘 Tab 导航与原生辅助功能树（Accessibility Tree），必须在上方叠加透明的 DOM Hitbox 遮罩，违背本地优先与轻量化架构初衷；
  4. **规范设计初衷错位**：WICG 设计 `drawElementImage` 主要面向 3D WebGL 游戏 HUD 覆层、Canvas 图表富文本标注与视频位图导出，而非长列表内容承载；
- **书架性能基准定性**：书架坚守原生 DOM + CSS Grid + 48 图增量预算，由合成器线程处理滚动，帧率稳定在 120 FPS+，无需任何 Canvas 代理层。

## 9. View Transitions API 行为规范与边界

- **全屏路由过渡**：在 `router.beforeResolve` 拦截跨级跳转（书架 ⇄ 详情 ⇄ 章节 ⇄ 阅读器），依据 `route.meta.rank` 计算 `forward`/`backward` 并派发 `types`。
- **严禁声明 `@view-transition { navigation: auto; }`**：该规则为 MPA 多页原生跳转专属，在 Vue SPA 中声明会导致 Chrome 性能指标采集器抛出 `Cannot read properties of undefined (reading 'startTime')` 空指针崩溃。
- **阅读器内严禁过渡**：同在阅读器内部翻页、切话或滚动时（`to.name === 'reader' && from.name === 'reader'`），**严格禁止触发路由 View Transition**，防止快速翻页时与阅读器内部虚拟滚动冲突产生 `AbortError`。
- **Promise 全生命周期安全兜底**：任何 `startViewTransition` 调用必须为 `ready`、`finished`、`updateCallbackDone` 绑定 `.catch(() => {})`，防止动画被抢占时向控制台泄漏未捕获异常。
- **共享封面形变（神奇移动）**：由 `useCoverTransition` 管理 `comic-cover-active` 赋名，仅在用户点击卡片进入详情页瞬间赋名，并在 `router.afterEach` 延时 400ms 自动清理，防止书架出现重名冲突。
- **页内筛选与卡片动效解耦（FLIP 单一真理源）**：页内标签筛选、喜欢切换、排序变化全权交由 Vue `<TransitionGroup name="shelf-card">` 的 FLIP 变换（`transform: translate` 在合成器线程执行），**严禁在页内状态变动时调用 `document.startViewTransition`**（避免整屏白闪）。
- **长列表零闲置快照图层（Zero Idle VT Footprint）**：严禁在常驻书架卡片上声明静态 `view-transition-name`，杜绝常驻离屏快照纹理和合成图层在上游容器重排时引发 GPU/CPU 软解雪崩掉帧。
- **异步网络请求防裹入**：严禁在 `withViewTransition` 回调内部发起或等待网络请求（如 API 修改），更新回调必须为纯净的本地状态与 DOM 同步。
- **弹窗动效分工**：弹窗（`Modal.vue` 及内部子弹窗）必须走 Vue 原生 `<Transition>`，利用组件内 Scoped CSS 分离遮罩（沉降）与面板（微弹），严禁将整个弹窗根容器包装进 View Transition 快照，防止全屏遮罩空间畸变与文字亚像素插值模糊。

## 10. VueUse 优先与零 DOM 胶水代码规范

- **查阅门禁**：新增交互组件、修改表单或重构状态逻辑前，必须查阅 `vueuse-functions` skill，严禁重复手写已有 VueUse composable 的样板代码。
- **消除隐藏 DOM**：严禁在模板中放置 `<input type="file" class="visually-hidden">` 并通过 DOM 引用 `.click()` 触发文件选择，必须使用 `useFileDialog({ multiple: true, accept: 'image/*' })`；
- **拖拽响应式化**：拖拽上传与投放区域必须使用 `useDropZone(elRef, { onDrop })`，直接利用其解构出的 `isOverDropZone` 响应式变量驱动高亮样式，杜绝手写 `@dragover.prevent` 与原生 `dataTransfer` 胶水；
- **全局状态与单例**：跨组件持久化配置必须使用 `createGlobalState` 与 `useStorage`；
- **视口与滚动**：交叉监听优先使用 `useIntersectionObserver`，容器滚动优先使用 `useScroll`。

## 11. 前端请求、缓存与生命周期取消规范（SWR & AbortController）

- **集中式强类型请求层**：全站请求统一由 `src/api/client.ts` 导出，所有查询类方法必须支持可选的 `options?: RequestOptions`（透传 `signal?: AbortSignal`）。
- **SWR 静默回源（Stale-While-Revalidate）**：
  - 书架首页与详情页在内存中已有数据时，**绝不重置 `loading = true` 导致骨架屏闪烁**；
  - 必须优先展示已有卡片/元数据，后台静默对齐最新状态，仅在首次无数据或用户显式刷新时呈现骨架屏。
- **生命周期请求取消与防竞态**：
  - 在页面加载（`ComicDetailView`、`ChapterView`、`ReaderView`）及连续触发场景（`useImageSearch` 重新选图、`useDiscovery` 快速切换周/月/总榜）中，使用局部 `AbortController`；
  - 发起新请求前主动中止上一次未完成的请求，并在组件卸载（`tryOnScopeDispose` / `onBeforeUnmount`）时自动 abort，杜绝无效后台流量与异步竞态覆盖。
- **`useMemoize` 失败自清理与类型签名规范**：
  - 所有使用 `@vueuse/core` 的 `useMemoize` 缓存的异步函数，必须在 catch 中调用 `.delete(key)`，防止因 Abort 或临时网络抖动导致 rejected promise 常驻缓存污染后续访问；
  - 在 `api` 导出对象上必须通过包装函数声明包含 `options?: RequestOptions` 的显式类型签名，杜绝 IDE 参数长度推导偏差。

## 12. 来源导航单一真理源与收录工作台解耦架构（Source SSOT Decoupling）

### 12.1 架构原理图

```mermaid
graph TD
  A[顶栏来源导航 AppHeader<br/>全部 / 01 禁漫 / 02 本地 / 03 哔咔] -->|route.query.source| B(路由单一真理源 activeSource)
  B -->|activeSource == '' 全部视图| C[LibraryHero 单栏典藏版式 hero--single]
  C --> C1[书房精神 Lede + 三项统计指标]
  C --> C2[轻量快捷跳转药丸: + 禁漫 / + 哔咔 / + 本地]

  B -->|activeSource == 'jm' / 'picacg' / 'local'| D[LibraryHero 双栏工作台版式]
  D --> D1[专属来源文案与藏书统计]
  D --> D2[逃生通道: 〔 ← 返回全部藏书 〕]
  D --> E[专属收录卡片 ImportPanel :source]
  E --> E1[is-source-locked 紧凑单列流<br/>彻底隐藏内部二级 Tab]
  E --> E2[对应站点输入框: 车号 / 链接 / 本地路径]
  E --> E3[移动端 :inert 键盘防穿透与 visibility 过渡]
```

### 12.2 核心规范与不变量

1. **单一真理源（SSOT）**：
   - 彻底废除 Hero 内部 `ImportPanel` 自主维护的 `.panel-tabs` 与全局 Header 来源导航冲突的“嵌套选项卡”（Tab-in-Tab）反模式；
   - 统一由 `activeSource = computed(() => route.query.source || '')` 驱动全站书架与工作台状态；
2. **全景视图与单源工作台分治**：
   - **「全部」视图（All View, `/?`）**：Hero 回归单栏典藏大片版式（`hero--single`），不常驻收录输入框，消除空间抢夺与视觉焦虑；
   - **「单源」专属视图（Provider View, 如 `/?source=jm`, `/?source=picacg`, `/?source=local`）**：Hero 右侧专精呈现对应站点的收录/扫描面板（`.is-source-locked` 单列紧凑编排），消除中屏视口（961px~1180px iPad 横屏）的双列轨道冲突（664px 刚性下限溢出）；
3. **操作自由度与逃生通道闭环（Escape Hatch）**：
   - 单源模式下在 Hero 左上方显式提供 `〔 ← 返回全部藏书 〕` 面包屑路由锚点；
   - 移动端折叠抽屉严格声明 `:inert="!isDesktop && !isMobileExpanded"` 并配合 `visibility: hidden` 过渡，彻底根除不可见隐藏表单与按钮引发的无障碍幽灵焦点（Ghost Focus）；
   - 移动端快捷药丸严格遵守 WCAG 2.5.5，保底 `min-height: 44px;` 触控物理判定区。
