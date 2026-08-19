# Tickets — 多章节支持 follow-up（paper-room-multi-chapter）

> 由 `docs/specs/0002-multi-chapter.md` 派生。标注 **[done]** 的为本轮已落地。
> 全部 P2/P3 已在本轮（T08–T12、T17）一次做完并验证。

## DONE — 多章节基础

- **[done] T01 后端模型：多章节结构**
  - `PageRecord.chapter`、`Chapter{id,index,title,page_count,start}`、
    `ComicMeta.chapters` / `is_multi_chapter`、`RemotePage.chapter`（均带默认值，旧数据零迁移）。
- **[done] T02 Provider：按 album.episode_list 逐话拉取并展平为全局页码**
  - 单话走旧路径且不产生 `chapters`；多话生成章节表（含 `ComicMeta.chapters` 注入）。
- **[done] T03 存储布局：pages/<chapter> 分章子目录**
  - `page_path` / `page_thumb_path` / `cached_page_count` / v1→v2 迁移全部感知章节；单章节保持扁平。
- **[done] T04 详情页多章节 UI（切片 + 章节条，开发史）**
  - 初版用 `ChapterSwitcher` + 详情页内切片；⚠️ 该形态已被 T13/T14 的「目录 + 子路由」取代，保留开发史。
- **[done] T05 阅读器章节标注**
  - ReaderView 按全局页定位章节，顶栏显示“第 X 話 · 标题”；DetailActionBar“继续阅读”带章节文案。
- **[done] T06 无障碍 + token 打磨（critique P1 落地）**
  - 章节条 `role=group + aria-pressed` + 左右方向键；`useScroll` 平滑居中；
    PageIndexGrid 计数前缀章节；`chapter-count` 对比度提升到 `--ink-1`。
- **[done] T07 文档**
  - README / AGENTS / CONTEXT / docs/agents/{architecture,frontend} / DESIGN_NOTES / spec / tickets 全部同步。

## DONE — 章节摆放重构（章节目录 + 子路由）

- **[done] T13 章节目录（多话详情页不再铺开几千页）**
  - 新增 `detail/ChapterIndex` / `detail/ChapterCard`；多话 `ComicDetailView` 只渲染目录，
    单话直接渲染整本 `PageIndexGrid`（零变化）。
- **[done] T14 章节子路由**
  - 路由 `/comic/:source/:id/chapter/:chapterId` → `ChapterView`：章节头（标题/页数/
    全局页区间/上一话/下一话）+ 该话 `PageIndexGrid` + `ChapterSwitcher` 跳话；
    目标话不存在/单话自动回详情页；`useChapterNavigation.setChapterById` 锁定章节。
- **[done] T15 目录封面 + 失败占位**
  - `ChapterCard` 用该话第一页当封面（T17 端点），`loading=lazy`；失败回落书脊占位。
- **[done] T16 章节摆放重设计评审 + 文档同步**
  - critique **37/40** 落 `.impeccable/critique/2026-08-19T19-33-06Z__src-chapter-directory.md`。

## DONE — P2/P3 全部落地（本轮一次性做完）

- **[done] T08 阅读器内“跳下一话”快捷键 / 本章结尾直达下一话**
  - `ReaderView`：读到某话末页时底部浮现「本话完 · 下一话 →」横幅一键跳转；
    键盘 `N/n` 下一话、`P/p` 上一话（全局页码直达对应话首/末页）。
- **[done] T09 章节条的“此节第几话”语义增强**
  - `ChapterSwitcher`：chip 带 `data-state`（past/active/upcoming），当前话加「当前」徽标、
    已翻过的话淡化；长标题溢出省略号 + 原生 `title` 完整标题。
- **[done] T10 章节级缓存进度**
  - 详情页按 `meta.pages[].cached` 计算每话本地缓存页数，`ChapterCard` 显示「本地 N%」。
- **[done] T11 多章节搜索/索引**
  - 后端 `LibrarySummary.chapter_titles` 随书库返回，`/api/library?q=` 也能命中章节标题
    （如搜「初见」/「第 5 话」）。
- **[done] T12 刷新资料时按章节增量更新**
  - `refresh=true` 时把旧 bundle 传给 provider；章节 id 集合（及单章总页数）没变则整书复用
    旧 remote_pages，只更新元数据、不重复拉每一话的 photo HTML；章节增删/顺序变则安全整书重拉。
- **[done] T17 章节目录封面池化 / 服务端章节封面端点**
  - 新增 `GET /api/library/{source}/{id}/chapters/{chapterId}/cover`：后端按章节 id 定位、
    用该话第一页生成 JPEG 封面并池化在 `covers/chapters/` 下；`ChapterCard` 改走此端点。
    失败回到书脊占位；`_save_cover` 复用 ensure_cover 生成逻辑。

## 后续（可选增强，非必需）

- **[P3] T18 章节目录封面的前台池化/无限滚动**
  - 超长合集目录一次性渲染 N 张卡片时，可把 `ChapterIndex` 改成前面的「虚拟化/增量目录」，
    复用 `useIntersectionObserver` 按批渲染（当前先靠 `loading=lazy` + 封面池化兜底）。
- **[P3] T19 章节级「缓存全部本章/本章下一批」**
  - 子路由内加「缓存本章全部」动作（复用 `cache` 端点但不整书），优先级低。

## 验收注意（防止回归）

1. 单章节（含旧缓存）详情页不出现章节目录、metadata 显示“单话”、页索引与阅读行为与旧版一致。
2. 多章节作品：详情页只显示章节目录（含每话本地 %）；点某话 → 子路由只看该话页索引；
   `N/P` 与章末横幅可跨话；阅读器从全局页进入、顶栏显示该话；书架能按“话”搜索。
3. `vp check` + 既有单测全绿；构建产物可正常 `vp build`。
