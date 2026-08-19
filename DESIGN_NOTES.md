# 设计过程记录（frontend-design → critique → polish → adapt）

## 1. frontend-design 脑前区思考

- **给谁用**：自己 / 少数同好，晚上或周末在桌面、平板、手机上翻自己的收藏。
- **需要被记住什么**：不是“又一个动漫站”，而是“私人阅览室 + 图书馆卡片目录”：
  暖纸色、墨色、朱砂色，像纸质卡片与旧书脊。
- **明确禁止**：紫色渐变、玻璃拟态堆叠、霓虹光效、emoji 当图标、
  无节制的圆角胶囊。
- **风格关键词**：Quiet archive / Reading room / Card catalog / Vermilion ink。

## 2. critique（对初版代码的评审）

| 问题               | 结论                                                 |
| ------------------ | ---------------------------------------------------- |
| 紫色渐变诱惑       | 已禁止，强调色固定为朱砂 `oklch(0.59 0.17 38)`       |
| 圆角过大、层次不清 | 限制为 4 档 radius，卡片/面板分层                    |
| 间距靠感觉         | 建立 4pt spacing tokens，页面统一 `--space-*`        |
| 字体层级不稳       | 标题用衬线 display，正文 sans，元数据 mono，职责明确 |
| 按钮对比度         | 主按钮白字配 `#c74c35`，对比度约 4.42:1；正文 14.7:1 |
| 封面加载时跳版     | 固定 `aspect-ratio: 3 / 4.15`，骨架屏兜底            |
| 阅读器进度条兼容性 | CSS scroll-timeline + JS fallback 双轨               |
| 远端压力           | 本地 album.json 命中时完全不发网络请求               |

## 3. polish（对齐设计系统）

- 所有颜色收敛到 `--paper-* / --ink-* / --accent / --line`；
- 所有边距收敛到 4pt 倍数；
- 动效时长只有 `--duration-1/2/3` 三档，缓动只有 `--ease-out / --ease-spring`；
- 封面轮播与阅读器都基于原生 CSS scroll-snap，不引入第三方轮播库。

## 4. adapt（适配）

- 桌面：1200px 容器，双栏 hero / 详情；
- 平板（<=960px）：hero 与详情改单栏；
- 手机（<=640px）：头部隐藏次要信息，卡片单列，操作按钮换行；
- 阅读器：`100dvh`、`env(safe-area-inset-*)`、图片可切“适应宽度 / 适应高度”。

## 5. live-cache（后台缓存实时进度，critique → polish → adapt）

- **需求**：收录/缓存全部已改造成后台任务，书架卡片要实时显示「缓存中 N%」，任务结束回落到准确的「本地 N%」。
- **critique（挑刺）**：
  1. 任务完成后卡片回落到**过期**的静态计数（显示错数字）→ store 在任务集合变化时重新拉取书库快照；
  2. 进度条的「斜纹扫描」用了 `::after` 但 fill 没设 `position:relative` → 扫动覆盖整条轨道而非已缓存段 → 修正；
  3. `aria-valuetext` 漏写冒号，输出字面量 `label` → 修正为 `:aria-valuetext`；
  4. 运行态文字用 `--ink-2` 识别度偏低 → 运行态改 `--accent-strong`，完成态 `--success`。
- **polish（对齐系统）**：新增 `CacheProgress.vue`，全部走 `--paper*/--ink*/--accent/--success/--space-*/--duration-*`；动效只有脉冲 + 一次斜纹，`prefers-reduced-motion` 全关。
- **adapt（适配）**：卡片底行 `>380px` 横向「观看次数 + 进度」，窄屏自动纵排，避免拥挤；全局「后台正在缓存 N 本」提示用胶囊 + 呼吸点，随 `activeCachingCount` 显隐。

## 6. download-concurrency + canvas live-cache（Impeccable：critique → polish → adapt）

- **下载并发设置**：入口放在 ImportPanel「缓存全部」checkbox 正下方（缓存入口所在卡片，符合用户直觉）。
  - 前端：`src/stores/settings.ts`（localStorage `comic-shelf:download-concurrency:v1` + API 同步），UI 用 −/+ 步进器（走 `--paper*/--ink*/--accent-soft`），范围 1–16。
  - 后端：`gate.py` 可运行时调整的并发闸门（`threading.Condition`），`COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS` 显式设置则锁定；否则持久化 `data/settings.json`；未锁定时 env 只是默认值。
  - critique：环境变量锁定态要在 UI 明示（只读值 + 提示文案），步进器 min/max 要禁用，避免与后端不一致。
- **Canvas 卡片实时进度**：`HtmlCanvasSurface` 新增 `redrawKey`，缓存进度变化时触发重绘；`HtmlCanvasCard` 与 `ComicCard` 共用 `CacheProgress`，UI 完全一致。
  - critique：重构前 canvas 只画一次、进度是静态快照；现在 `redrawKey` 变化才重绘（80ms 防抖），避免无谓重绘。

## 7. Tooltip（CSS Anchor Positioning）+ 导入设置卡片瘦身

- 新增 `src/components/Tooltip.vue`：CSS Anchor Positioning 实现（`anchor-name` / `position-anchor` / `position-area` + `position-try-fallback: flip-block`），hover / focus 显示，走 tokens；方位支持 top/right/bottom/left（默认 top），不支持时 `@supports not (anchor-name:…)` 降级绝对定位。
- ImportPanel：删掉面板外那行臃长的 `cache-all-option`，「缓存全部」勾选并入 `download-settings`；括号说明与「下载并发」提示一并收进 Tooltip（卡片变矮、不再被拉宽）。
  - 长文案全部隐藏为 ℹ 图标（SVG，非 emoji），hover/聚焦才出 Tooltip。

## 8. 多章节支持（grill-with-docs 确认 → critique → polish → adapt）

- **需求**：禁漫“一本”可能是多话合集（`album.episode_list` 多个 photo），详见
  `docs/specs/0002-multi-chapter.md`。旧实现只拉 `/photo/{album_id}`，多话合集取不到。
- **grill-with-docs（先查证再动手）**：通读 `docs/agents/*`、`CONTEXT.md`、既有 spec，
  确认现状只有“单章 + 扁平 pages/”，决定采用**全局页码拍平 + 章节 id 切片**的增量方案，
  保证单章节零回归、旧缓存零迁移。
- **grill-with-docs（组件拆分复核）**：多章节初版把章节切片/增量渲染逻辑堆在
  `ComicDetailView` 里，违反 spec 0001「视图只编排、逻辑收敛 composable」→ 抽出
  `src/composables/useChapterNavigation.ts`，视图瘦身、单一职责恢复。
- **critique（挑刺）**：
  1. 章节 chip 用了 `role=tablist` 却没有 tabpanel，且键盘无法左右移动 → 改 `role=group + aria-pressed`，
     加左右方向键（VueUse `useEventListener`）；
  2. 多章节下“已显示 X / Y 页”丢章节上下文 → 计数行前缀当前章节文案；
  3. `chapter-count` 角标 `--ink-2` 对比弱 → 升 `--ink-1`，选中态叠朱砂浅底。
- **polish（对齐系统）**：新增章节条全部复用既有 token（`--space-*`/`--text-caption`/`--control-md`/
  `--accent-soft`/mono 页数），无新增 token、无紫色渐变/第三方轮播。
- **adapt（适配）**：桌面横向铺开；<=640px 变成可横向滚动胶囊条，选中 chip 用 `useScroll`
  平滑居中；阅读器顶栏章节标注窄屏 `text-overflow: ellipsis`；chip 触控整块 44px。

## 9. 多章节按「章节目录 + 子路由」摆放（grill-with-docs 复盘 → critique → polish → adapt）

- **grill-with-docs 复盘**：用户指出“有章节不该几千页一排，要按章节摆放、加子路由”。
  原实现（章节 chips + 详情页内切片）虽不一次渲染几千页，但仍是“一个超长详情页”，
  缺“目录 → 话”的层级。改为：**详情页只摆章节目录，点某话进章节子路由看该话页面**；
  单章节继续直接平铺每页。
- **critique（挑刺）**：
  1. 结构层级缺失 → 改成“目录 + 子路由”两级导航（`/comic/:src/:id/chapter/:cid`）；
  2. 章节卡片封面 = 每话第一页缩略图，超长合集几百次懒下载 → 保留 `loading=lazy` +
     失败回落书脊占位，池化/服务端封面端点列入 P2 ticket；
  3. 单章/错误 id 兜底 → 子路由加载后若目标话不存在自动回详情页。
- **polish（对齐系统）**：目录卡片、章节头、pager 全部走既有 token；封面占位用
  `--paper-1→paper-2` 斜向渐变 + 朱砂书脊色带，延续“书脊”隐喻。
- **adapt（适配）**：桌面目录网格多列、≤640px 单列；chips 可横向滚动居中；
  pager 窄屏占满一行、触控 ≥44px；小屏封面列收窄保证标题可读。

## 10. 多章节 P2/P3 一次补齐（T08/T09/T10/T11/T12/T17）

- **跨话阅读（T08）**：阅读器读到某话末页浮现「本话完 · 下一话 →」横幅，`N/P` 键盘跨话；
  只做全局页码跳转，不重置任何阅读设置。
- **章节条语义（T09）**：`ChapterSwitcher` 加 `data-state`（past/active/upcoming），
  当前话「当前」徽标 + 已翻过淡化 + 长标题省略号（原生 `title` 兜底全文）。
- **章节级缓存（T10）**：详情页用 `meta.pages[].cached` 直接算每话本地 %，目录卡片显示。
- **多章节搜索（T11）**：书库摘要带 `chapter_titles`，`/api/library?q=` 命中章节标题。
- **刷新增量（T12）**：`refresh=true` 传旧 bundle，章节集合未变则跳过逐话 photo HTML。
- **章节封面池化（T17）**：新增 `GET /chapters/{id}/cover` 服务端封面，池化于
  `covers/chapters/`，`ChapterCard` 改走它；`_save_cover` 复用 ensure_cover 生成逻辑。
- **评审**：全部沿用既有 token / `--reader-*`；`vp check`/`vp test`/`vp build` 全绿，
  并用临时 FastAPI 实例验证了 T11 搜索命中、T17 端点路由（404/502 行为正确）与 T12 复用不拉 photo。
