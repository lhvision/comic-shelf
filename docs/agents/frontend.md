# 前端规则与阅读器行为（详细规则）

## 6. 前端文件地图

| 文件                                        | 职责                                                                       |
| ------------------------------------------- | -------------------------------------------------------------------------- |
| `src/views/LibraryView.vue`                 | 书架、导入、搜索、标签过滤                                                 |
| `src/views/ComicDetailView.vue`             | 封面轮播、元数据、操作栏、章节目录（多话）/ 页面索引（单话）、缓存操作     |
| `src/views/ChapterView.vue`                 | 章节子路由：某话的章节头（标题/页数/上一话/下一话）+ 该话 PageIndexGrid    |
| `src/views/ReaderView.vue`                  | 阅读器：模式、grid 分页、进度、设置面板、横向滚轮映射、章节标注            |
| `src/components/detail/ChapterIndex.vue`    | 章节目录整段：head + 卡片网格（多话作品详情页主视图，代替几千页平铺）      |
| `src/components/detail/ChapterCard.vue`     | 目录单卡：该话第一页封面缩略图（失败回落书脊占位）+ 序数/标题/页数         |
| `src/components/detail/ChapterSwitcher.vue` | 章节切换条（现用于 ChapterView 内跳话）：横向 chips + 方向键 + `useScroll` |
| `src/composables/useChapterNavigation.ts`   | 章节导航编排：锁定章节、章节切片、48 增量渲染、「继续阅读 · 第 X 話」文案  |
| `src/components/FavoriteButton.vue`         | 喜欢标记按钮（书架卡片 / 实验卡片 overlay）                                |
| `src/components/ComicPageImage.vue`         | 每页图片 loading / error / retry 兜底                                      |
| `src/components/CoverCarousel.vue`          | scroll-snap + view-timeline 封面流                                         |
| `src/components/HtmlCanvasSurface.vue`      | 实验性 DOM→canvas 绘制原语，default slot 是完整 DOM 子树                   |
| `src/components/HtmlCanvasCard.vue`         | 实验性书架卡片：整卡 DOM（封面+标题+标签+进度）合成 canvas                 |
| `src/styles/tokens.css`                     | 设计 token 与原生 `@function` 演示                                         |
| `src/stores/library.ts`                     | 书库 Pinia store                                                           |
| `src/stores/experiments.ts`                 | 实验开关：HTML-in-Canvas 卡片                                              |

## 6.5 页面索引性能策略

- 详情页页面索引**不要一次渲染全部**：`ComicDetailView` 默认只渲染前 48 个 tile，
  滚动到 sentinel 自动加载下一批，并显示“已显示 X / Y 页”。
- tile 使用 `/pages/{n}/thumbnail`（360px JPEG，服务端懒生成并缓存），
  不要用 `/pages/{n}/file` 原图做缩略图。
- tile 和 reader spread 都使用 `content-visibility: auto`，离屏跳过渲染。
- HTML-in-Canvas 不适合做页面索引虚拟化：为每个 tile 建 canvas 会比图片更耗内存。
  它只用于 DOM 合成（封面卡），性能优化仍以 thumbnail + 增量 DOM + content-visibility 为主。

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
- 点击详情页任意页码进入阅读器后，会定位到该页所在屏（此前 bug 已修复：
  必须在 `loading=false` 渲染完成后 `await nextTick()` 再 scroll）。
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

## 7.5 每页 loading 兜底

- `public/page-loading-1.gif` / `page-loading-2.gif` 是两个动态 loading 图标。
- `ReaderView` 每次进入一本漫画时随机选定一个 variant，并把同一个值传给该本
  所有 `ComicPageImage`；因此整本书 loading 图标一致，不会逐页乱跳。
- `ComicPageImage.vue` 给普通 `<img>` 页面提供：居中动态 loading、失败重试。
- `HtmlCanvasSurface.vue` / `HtmlCanvasCard.vue` 的 loading 同样使用 GIF；
  canvas / DOM fallback 两条路径都覆盖。
- 调试 HTML-in-Canvas：
  - 书架开启“实验：HTML-in-Canvas 卡片”后，卡片左下角显示 `CANVAS` 或 `DOM`；
  - 控制台可查 `window.__COMIC_SHELF_HTML_CANVAS__`：
    `{ supported, rendered, fallback, drawsDomSubtree, surface }`。
