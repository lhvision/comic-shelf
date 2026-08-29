# 前端规则与阅读器行为（详细规则）

## 6. 前端文件地图

| 文件                                           | 职责                                                                       |
| ---------------------------------------------- | -------------------------------------------------------------------------- |
| `src/views/LibraryView.vue`                    | 书架视图编排：Hero / 导入 / 筛选工具栏 / 卡片网格                          |
| `src/views/DiscoveryView.vue`                  | 发现页视图编排：分段榜单切换、分类筛选、榜单卡片网格与一键收录             |
| `src/views/ComicDetailView.vue`                | 详情视图编排：封面流 / 元数据 / 操作栏 / 章节目录 / 页面索引               |
| `src/views/ChapterView.vue`                    | 章节子路由：某话章节头（本话缓存进度/重命名/删除管理）+ 该话 PageIndexGrid |
| `src/views/CreateComicView.vue`                | 自建图集工坊：单话/多章节多图拖拽暂存、服务器路径导入、元数据与封面编排    |
| `src/views/ReaderView.vue`                     | 阅读器视图编排：模式切换、DOM 分屏挂载、HUD / 顶栏 / 设置面板接线          |
| `src/composables/useAuth.ts`                   | 访问鉴权与门禁状态机：Cookie/Token 会话、状态探测、401 拦截联动            |
| `src/composables/useDiscovery.ts`              | 发现页排行榜状态机：周榜/月榜/日榜/总榜拉取、分类过滤与收录状态追踪        |
| `src/composables/useUploadQueue.ts`            | 受限并发批量上传队列控制器（3 路 Worker 并发、细粒度进度与取消支持）       |
| `src/composables/useLibraryFilter.ts`          | 书架检索与筛选：模糊搜索、标签频率统计、多模式排序与喜欢过滤               |
| `src/composables/useImageSearch.ts`            | 以图搜图状态机：文件上传、剪贴板粘贴、拖拽、置信度与状态管理               |
| `src/composables/useReaderPaging.ts`           | 阅读器分页与作用域：分组切片、全局/本地页码映射、跨话首尾探测与边界计算    |
| `src/composables/useAutoTurn.ts`               | 阅读器自动翻页：倒计时状态机、节拍器、页面可见性联动与暂停/继续            |
| `src/composables/useReaderChrome.ts`           | 阅读器顶栏/HUD 延时隐藏与交互唤醒控制                                      |
| `src/composables/useChapterNavigation.ts`      | 详情/子路由章节导航：锁定章节、章节切片、48 增量渲染、「继续阅读」文案     |
| `src/composables/useReaderSettings.ts`         | 阅读器设置全局状态单例持久化（VueUse `createGlobalState`）                 |
| `src/composables/useLastRead.ts`               | 每部作品继续阅读页码持久化读写                                             |
| `src/composables/useToast.ts`                  | 全局轻量印章通知 Toast 状态机（支持 info / error / success 三态提示）      |
| `src/composables/useHtmlCanvas.ts`             | HTML-in-Canvas 实验特性检测与支持度判定                                    |
| `src/composables/useOfflineStorage.ts`         | 端侧离线物理存储探测与分级清理状态机（StorageManager + CacheStorage 统计） |
| `src/composables/usePwaInstall.ts`             | PWA 安装与独立应用视口检测状态机（`beforeinstallprompt` + Standalone）     |
| `src/pwa.ts`                                   | PWA Service Worker 注册与每小时周期性静默更新检查调度器                    |
| `src/components/AuthModal.vue`                 | 访问口令门禁弹窗：输入密钥、品牌 Logo、双语眉标与错误反馈                  |
| `src/components/Modal.vue`                     | 通用无障碍二次确认弹窗：焦点圈闭、锁卷与抽屉自适应（用于删除危险操作）     |
| `src/components/SegmentedTabs.vue`             | 典藏分段选项卡：支持泛型 `TabItem<T>`/字符串、左右/Home/End 键导航与多尺寸 |
| `src/components/AppButton.vue`                 | 通用典藏按钮：支持 primary / secondary / soft / ghost / danger 多种变体    |
| `src/components/AppIcon.vue`                   | 零分支矢量图标分发器（基于 `<component :is="ICON_MAP[name]">` 动态渲染）   |
| `src/components/icons/`                        | 纸间统一矢量图标集（`BaseIcon.vue` 底座 + 23 个原子 `Icon*.vue` 组件）     |
| `src/components/AppTooltip.vue`                | 现代声明式轻量气泡提示组件（Popover API + CSS Anchor + 悬停安全桥）        |
| `src/components/AppPopover.vue`                | 现代顶层锚定交互浮层（自动碰撞翻转、轻量失焦关闭）                         |
| `src/components/StoragePopover.vue`            | 阅览室设备与离线存储管理浮层（3px平直刻度槽/分项账单/双级清理/两步确认）   |
| `src/components/AppDropdown.vue`               | 现代操作选单与选择器（无依赖 Top Layer + 键盘导航）                        |
| `src/components/BackToTop.vue`                 | 正圆暖纸印章回到顶部微件（VueUse `useWindowScroll` 视口监听）              |
| `src/components/CacheProgress.vue`             | 实时缓存进度条与后台任务状态指示                                           |
| `src/components/detail/EditMetadataModal.vue`  | 典藏资料与标签编排弹窗（实时修改标题、作者、4 张封面展示页码、标签增删）   |
| `src/components/detail/AppendPagesModal.vue`   | 本地漫画增量追加弹窗（追加至已有话或新建分话、支持网页上传/服务器路径）    |
| `src/components/discovery/DiscoveryCard.vue`   | 榜单漫画卡片：排名徽章、原站外链、分类胶囊与一键收录/在库直达              |
| `src/components/form/TagManager.vue`           | 交互式标签管理器（Chip 展示、Enter/空格添加、SVG 居中删除、热门快选推荐）  |
| `src/components/form/CoverIndicesPicker.vue`   | 4 张封面展示页码选定器（4 槽位数值输入、实时越界纠偏与默认值安全回退）     |
| `src/components/detail/ChapterIndex.vue`       | 章节目录整段：head + 卡片网格（多话作品详情页主视图，代替几千页平铺）      |
| `src/components/detail/ChapterCard.vue`        | 目录单卡：该话第一页封面缩略图（失败回落书脊占位）+ 序数/标题/页数         |
| `src/components/detail/ChapterSwitcher.vue`    | 章节切换条（用于 ChapterView 内跳话）：横向 chips + 方向键 + `useScroll`   |
| `src/components/FavoriteButton.vue`            | 喜欢标记按钮（书架卡片 / 实验卡片 overlay）                                |
| `src/components/ComicPageImage.vue`            | 每页图片 loading / error / retry 兜底                                      |
| `src/components/CoverCarousel.vue`             | scroll-snap + view-timeline 封面流                                         |
| `src/components/HtmlCanvasSurface.vue`         | 实验性 DOM→canvas 绘制原语，default slot 是完整 DOM 子树                   |
| `src/components/HtmlCanvasCard.vue`            | 实验性书架卡片：整卡 DOM（封面+标题+标签+进度）合成 canvas                 |
| `src/components/reader/ReaderLoadingState.vue` | 典藏 WebP 呼吸微光加载组件（整本首屏与单页渐进式加载）                     |
| `src/styles/tokens.css`                        | 设计 token 与原生 CSS 样式体系                                             |
| `src/stores/library.ts`                        | 书库 Pinia store（SWR 保持、静默回源、后台缓存轮询与自动清理收录提示）     |
| `src/stores/settings.ts`                       | 下载并发与运行时设置 store                                                 |
| `src/stores/experiments.ts`                    | 实验开关：HTML-in-Canvas 卡片                                              |

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
      • 360px JPEG 缩略图（~15KB）          • 本地磁盘原图 0 远端请求秒开
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
- HTML-in-Canvas 不适合做页面索引虚拟化：为每个 tile 建 canvas 会比图片更耗内存。
  它只用于 DOM 合成（封面卡），性能优化仍以 thumbnail + 增量 DOM 为主。
- **预热机制（Pre-warming）**：后台预缓存任务在拉取原图的同时自动生成 360px 缩略图，详情页访问 100% 命中暖缓存；后端同时配备 `COMIC_SHELF_THUMB_CONCURRENCY` 门禁，防止多用户并发动态生成导致 CPU 击穿。进入阅读器可 100% 本地秒开。禁止在阅读器大图使用 LQIP（模糊马赛克底图）以防破坏纸质质感。
- **意图预热与即时元数据占位（Prefetch on Intent & SWR Hero Placeholder）**：
  - **意图预热（卡片与按钮）**：`ComicCard` 与 `HtmlCanvasCard` 在 `@pointerenter.once` / `@focusin.once` / `@touchstart.passive.once` 时静默预热 `ComicDetailView.vue` 路由 chunk 与 `api.detail` 接口（写入 `useMemoize` 内存）；`DetailActionBar` 在悬停阅读按钮时同步预热 `ReaderView.vue`；
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

## 7. 阅读器当前行为

设置保存在 `localStorage['comic-shelf:reader-settings:v1']`。

```ts
{
  mode: 'vertical-continuous' | 'vertical-paged' | 'horizontal',
  fit: 'width' | 'height',
  pagesPerView: 1 | 2 | 4,
  direction: 'ltr' | 'rtl',   // 横向模式：左→右 或 日漫右→左
  autoTurn: boolean,
  autoTurnInterval: 5 | 10 | 15 | 30   // 单位：秒
}
```

- `vertical-continuous`：无 snap，连续滚动；PC 端页面尺寸与 `vertical-paged` 一致。
- `vertical-paged`：`y proximity` + `scroll-snap-stop: always`；不要改回 `y mandatory` 或容器级 `scroll-behavior: smooth`，快速滚轮会卡在页缝附近。
- `horizontal`：x snap，一屏 1/2/4 页 grid（窄屏只给 1/2），左右滑动切屏。
- 每屏页数按视口开放：`min-width: 681px` 的 PC/平板允许 1/2/4 页，更窄屏幕只允许 1/2 页；窄屏下旧的 4 页配置会临时按 2 页渲染。
- 点击详情页任意页码进入阅读器后，会定位到该页所在屏（`loading=false` 渲染完成后 `await nextTick()` 再 scroll）。
- 阅读器 DOM 使用 `data-group-index` 标记每一屏；页码定位依赖这个属性。
- `.reader-view` 必须保留 `timeline-scope: --reader-scroll`：进度条是 `.reader-scroll` 的兄弟节点，
  scroll timeline 只有提升作用域后才能跨子树引用；删掉它会导致竖向进度条失去 scroll-driven 动画。
- 竖向连续模式的 `.reader-spread` 不要加 `min-height: 100dvh`，否则移动端每页后会留整屏空白；页间间隔由后续 spread 的 `padding-top` 控制。
- 自动切换按“屏”计时：默认关闭，间隔 5/10/15/30 秒。开启后右下角倒计时 HUD 常驻，
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

## 8. HTML-in-Canvas 实验

- Chrome 148–150 Origin Trial；本地可用 Canary 149+ 打开 `chrome://flags/#canvas-draw-element` 测试。
- 生产域名需在 Origin Trials 控制台申请 token 并在 `index.html` 填入：
  `<meta http-equiv="origin-trial" content="TOKEN">`。
- 实验开关位于 `localStorage['comic-shelf:experiments:v1']`：`{ htmlCanvasCards: true }`。
- `HtmlCanvasSurface.vue` 只在 `canvas.getContext('html')` 可用且实验开启时启用；
  否则 default slot 作为普通 DOM 渲染，保留 fallback 路径。
- 它绘制的是**完整卡片 DOM 子树**（封面 + 标题 + 作者 + 标签 + 缓存进度），
  交互由透明 overlay slot 保留；控制台可通过 `window.__COMIC_SHELF_HTML_CANVAS__` 调试。

## 9. View Transitions API 行为规范与边界

- **全屏路由过渡**：在 `router.beforeResolve` 拦截跨级跳转（书架 ⇄ 详情 ⇄ 章节 ⇄ 阅读器），依据 `route.meta.rank` 计算 `forward`/`backward` 并派发 `types`。
- **严禁声明 `@view-transition { navigation: auto; }`**：该规则为 MPA 多页原生跳转专属，在 Vue SPA 中声明会导致 Chrome 性能指标采集器抛出 `Cannot read properties of undefined (reading 'startTime')` 空指针崩溃。
- **阅读器内严禁过渡**：同在阅读器内部翻页、切话或滚动时（`to.name === 'reader' && from.name === 'reader'`），**严格禁止触发路由 View Transition**，防止快速翻页时与阅读器内部虚拟滚动冲突产生 `AbortError`。
- **Promise 全生命周期安全兜底**：任何 `startViewTransition` 调用必须为 `ready`、`finished`、`updateCallbackDone` 绑定 `.catch(() => {})`，防止动画被抢占时向控制台泄漏未捕获异常。
- **共享封面形变（神奇移动）**：由 `useCoverTransition` 管理 `comic-cover-active` 赋名，在 `router.afterEach` 延时 400ms 自动清理，防止书架出现重名冲突。
- **弹窗动效分工**：弹窗（`Modal.vue` / `AuthModal.vue`）必须走 Vue 原生 `<Transition>`，利用组件内 Scoped CSS 分离遮罩（沉降）与面板（微弹），严禁将整个弹窗根容器包装进 View Transition 快照，防止全屏遮罩空间畸变与文字亚像素插值模糊。

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
