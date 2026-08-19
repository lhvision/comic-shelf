# Tickets — 多章节支持 follow-up（paper-room-multi-chapter）

> 由 `docs/specs/0002-multi-chapter.md` 派生。标注 **[done]** 的为本轮已落地，
> 其余为评审（critique）给出的 P2/P3 增强，按优先级排期。
> 最新一轮「章节目录 + 章节子路由」重构见下方 T13–T16 与 P2 T17。

## DONE（多章节基础）

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
    单话直接渲染整本 `PageIndexGrid`（零变化）。grill-with-docs 复盘后落地。
- **[done] T14 章节子路由**
  - 路由 `/comic/:source/:id/chapter/:chapterId` → `ChapterView`：章节头（标题/页数/
    全局页区间/上一话/下一话）+ 该话 `PageIndexGrid` + `ChapterSwitcher` 跳话；
    目标话不存在/单话自动回详情页；`useChapterNavigation.setChapterById` 锁定章节。
- **[done] T15 目录封面 + 失败占位**
  - `ChapterCard` 用该话第一页缩略图当封面，`loading=lazy`；加载失败回落“书脊占位”仍显示章节信息。
- **[done] T16 章节摆放重设计评审 + 文档同步**
  - critique **37/40** 落 `.impeccable/critique/2026-08-19T19-33-06Z__src-chapter-directory.md`；
    DESIGN_NOTES §9 / spec 0002 / `docs/agents/frontend.md §6.7` 同步。

## P2 / P3（后续票据）

- **[P2] T08 阅读器内“跳下一话”快捷键 / 结尾卡直达下一话**
  - 在多章节阅读器中，到某话末屏后提示“下一话：{标题}”，回车或点击直达下一话首页；
    键盘可给一个“N = 下一话 / P = 上一话”。
- **[P2] T09 章节条的“此书第几话”语义增强**
  - 章节 chip 右侧加下划线式的“未完待续/当前话”提示；长标题超出时 `text-overflow: ellipsis`
    并复用 Tooltip 显示完整标题（复用既有 `Tooltip.vue`）。
- **[P2] T17 章节目录封面池化 / 服务端章节封面端点**
  - critique P1：超长合集目录会为每话第一页触发一次缩略图下载。改为服务端按章节生成一张
    定尺寸封面（复用 `ensure_cover` 逻辑按 `chapter.start` 全局页生成），前端目录走新端点，
    避免 N 次原图下载 + 缩略图生成；失败仍回落书脊占位。
- **[P3] T10 章节级缓存进度**
  - 详情页缓存条目前是全书粒度；可在章节卡片上叠加每话的“本地 N%”小进度点，
    仍复用 `cache_progress` 之外的书架级 JobInfo 作为启发信号（不新增轮询端点）。
- **[P3] T11 多章节搜索/索引**
  - 书架搜索目前按整本书标题/作者/标签命中；可把每话标题纳入检索，便于“我找第 5 话”。
- **[P3] T12 刷新资料时按章节增量更新**
  - `refresh=true` 会整书重建；对多章节可只对新话做内容级 diff，减少远端请求。

## 验收注意（防止回归）

1. 单章节（含旧缓存）详情页不出现章节目录、metadata 显示“单话”、页索引与阅读行为与旧版一致。
2. 多章节作品：详情页只显示章节目录；点某话 → 子路由只显示该话页面索引；点页 → 阅读器从全局页
   进入、顶栏显示该话、继续阅读带章节；上一话/下一话与章节 chips 可跳话。
3. `vp check` + 既有单测全绿；构建产物可正常 `vp build`。
