# Spec — 多章节（章节内多话）支持（paper-room-multi-chapter）

> 领域词汇遵循根目录 `CONTEXT.md`；本 spec 不含具体文件路径/代码片段，
> 只描述本子、章节、页码、缓存等领域行为与已确证的结构决策（对应 README 的实现说明）。
> 配套票据见 `docs/tickets/0002-multi-chapter-tickets.md`。

## Problem Statement

禁漫等来源里“一本”作品可能只有一个 photo（单话），也可能是一整个合集/系列
（`album.episode_list` 含多个章节，每个章节是独立的 photo）。旧实现只按
`/photo/{album_id}` 拉取，多话合集只能取到第一话甚至取不到，页面索引、阅读器、
“继续阅读”都只有一维“全书页码”，无法表达“第 2 話 第 3 页”。

本轮目标：**从后端到前端完整支持多章节**，同时保证**单章节体验完全不变**。
示例：https://comic18j-rita.cc/album/518074/迷宮干-던전-속-사정（多话合集）。

## Solution

核心结构决策 = **“全局页码拍平 + 章节 id 切片”**：

- 一部多章作品在模型里仍是一张**全局页码表**（`meta.pages`，页码 1..全书总页数）。
  阅读器页数、封面、缓存进度、“继续阅读”全部沿用全局页码，心智零变化。
- 每个章节用 `Chapter{id, index, title, page_count, start}` 描述，`start` 是该章节
  在全局页码里的起始页（1-based）。详情页“页面索引”只按当前章节切片显示；
  每张缩略图仍链接到**全局页码**，因此点了任意页就进入正确的阅读位置。
- 存储布局：单章节沿用旧的扁平 `pages/<file>`；多章节按 `pages/<chapter_id>/<file>`
  （缩略图同理 `thumbs/<chapter_id>/`）。新版字段都带默认值，旧 `album.json` 零迁移。

## User Stories

1. 作为使用者，我收录一本多话合集后，能在详情页看到“第 N 話 · 标题 · XX 页”的章节条，
   并在章节间切换来看对应页索引，这样我能按话翻阅。
2. 作为使用者，我在详情页点任意章节的某页，阅读器能直接从那一话的指定页开始读，
   不用自己数页码。
3. 作为使用者，我上次读到“第 3 話 第 12 页”，回到详情页时“继续阅读”会显示带章节的
   直达按钮，并默认停在那一话的页面索引。
4. 作为阅读者，多章节作品在阅读器顶栏能实时看到“第 X 話 · 标题”，跨章连续翻页不迷路。
5. 作为使用者，单章节作品（或旧的已收录数据）详情页、阅读器、缓存进度与以前完全一致。
6. 作为维护者，后端模型、存储、provider 的改动是纯增量（新字段带默认值），
   旧缓存无需迁移，也不会破坏书库扫描。

## Implementation Decisions

- **模型层（后端）**
  - `PageRecord.chapter`（默认 `""`）：页面所属章节 id；单章节为空串。
  - `Chapter{id,index,title,page_count,start}`：章节描述，`start` 为全局起始页。
  - `ComicMeta.chapters`（默认 `[]`）+ `is_multi_chapter` 只读属性。
  - `RemotePage.chapter`（默认 `""`）：随 `remote.json` 持久化，便于 v1→v2 迁移与下载路由。
- **Provider（禁漫）**
  - 读 `album.episode_list`：单话时与旧逻辑一致（只拉自己的 photo）；多话时逐话
    `/photo/{pid}` 拉取，按章节序数展平为全局页码，并生成 `chapters`。
  - 单章节不写 `chapters`、页面 `chapter` 置空 → 存储仍走扁平 `pages/`，布局不变。
- **存储层**
  - `page_path`/`page_thumb_path`：有 `chapter` 走 `pages/<chapter>/`，否则走扁平。
  - `cached_page_count`、`load_meta` 的校验、v1→v2 迁移路径都按同一规则解析文件位置。
  - 封面仍然从第一章前几页（全局 1..cover_count）生成，`cover_paths` 不变。
- **API**
  - 继续用**全局页码**：`GET /pages/{index}/file|thumbnail` 等旧端点无需改签名；
    多章只是页面文件落在分章子目录，前端地址不变。
- **前端（章节摆放 = 章节目录 + 章节子路由）**
  - `useChapterNavigation(detail, lastRead)` composable 收纳章节导航编排：锁定章节
    （`setChapterById`）、章节切片、48 页增量渲染、「继续阅读 · 第 X 話」文案。
  - `ComicDetailView`：多话（`chapters.length>1`）时详情页只渲染 `ChapterIndex`
    （目录卡片 = 该话第一页封面缩略图 + 序数/标题/页数），**不铺开几千页**；
    单话直接渲染整本 `PageIndexGrid`（旧样，零变化）。
  - `ChapterView`（新子路由 `/comic/:source/:id/chapter/:chapterId`）：只渲染该话
    `PageIndexGrid`（复用 48 增量 + 章节前缀），头部带上一话/下一话 pager +
    `ChapterSwitcher` 跳话；目标话不存在/单话自动回详情页。
  - `ChapterCard` 封面失败回落“书脊占位”，仍然显示章节信息；`loading=lazy` 懒加载。
  - `PageIndexGrid` 计数行前缀当前章节文案，解决长书“丢位置”的问题。
  - `MetadataPanel` 多章节时显示“共 N 话”；单章节显示“单话”。
  - `ReaderView` 顶栏按全局页定位章节并显示“第 X 話 · 标题”。
  - `DetailActionBar` 的“继续阅读”由父级传入带章节的文案（缺省回落旧文案）。
- **VueUse 约定**：新增逻辑只用 `useScroll` / `useEventListener` / 既有的
  `useIntervalFn`/`useIntersectionObserver`，不新增手写浏览器样板。

## Testing Decisions

- 后端：用临时目录写入多章节 `album.json` + 分章 `pages/` 文件，验证
  `save_fetched → load_meta → page_path / cached_page_count / cover_paths` 闭环。
- 前端：`vp check`（fmt + lint + type-check）全绿；既有 `App.spec.ts` + `smoke.test.ts` 通过，
  保证单章节渲染与全局回归不出问题。多章节 UI 是数据驱动切片，不新增独立测试文件
  （符合 AGENTS“不为新增功能而拆测”的约定）。
- 结构回归：`noUncheckedIndexedAccess` 下新增的 `chs[0]`/`chs[1]` 均带空值兜底。

## Out of Scope

- 阅读器内“下一话 / 跳到下一话结尾”的专项快捷翻页（列入 P2/P3 ticket，不做于此）。
- 把多章节拆成书目（每章节独立条目）的“子书架”化——当前保持“一本 = 一个条目”。
- 批量缓存/批量移除的章节级粒度（沿用现有的全书粒度）。
- 章节目录封面的“池化/服务端章节封面端点”（当前用每话第一页缩略图 + lazy + 失败占位，见 ticket）。
- 对新导入的多章节自动预热各章节封面。

## Further Notes

- 评审基线：两轮评审均落在 `.impeccable/critique/`——初版多章节增量 **35/40**
  （章节组键盘 + 计数无上下文已修）；「章节目录 + 子路由」重设计 **37/40**（P1 封面懒加载对策见 ticket）。
- **grill-with-docs（组件拆分复核）**：章节导航逻辑收敛到 `useChapterNavigation`
  composable，视图只编排；文件地图同步到 `docs/agents/frontend.md §6` 与 tickets。
- **grill-with-docs（章节摆放复盘）**：用户要求“有章节按章节摆放，无章节直接每页”，
  原“章节 chips + 详情页内切片”仍是单页体验 → 重构为**目录 + 子路由**两级导航，
  多话详情页不再铺开几千页。
- 设计令牌完全复用，无新增 token；`--space-0-5`/`--text-caption`/`--control-md` 直接沿用。
