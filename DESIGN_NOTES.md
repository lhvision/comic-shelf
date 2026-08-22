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

## 11. 旧多章节缓存自动回填（518074 单章模式的根因修复）

- **根因**：`518074` 是在“页面已按章拆、但 `ComicMeta.chapters` 还没注入”的 bug 窗口导入的，
  于是 `pages[].chapter` 有值、`meta.chapters=[]`，前端按 `chapters` 判定 → 显示成单章。
- **修复**：`ComicStore.load_meta` 加本地回填——若 `chapters` 为空但 `pages` 存在非空
  `chapter` 且 `raw.chapters` 有数据，就用 `raw.chapters` 重建章节表（压平标题空白）并
  **原位修复 album.json，不重新下载**（与 v1→v2 迁移同一哲学）。
- **验证**：修复后 `518074` = 152 话、7227 页、`is_multi=True`，API 详情返回 `chapters`，
  前端自动切到「章节目录 + 子路由」；其余单话缓存仍为单章，零回归。

## 12. 危险操作“移除本地”重设计（Impeccable：critique → polish → adapt）

- **critique**：移除本来是高风险动作，却一直摆在操作栏里一颗明显的大按钮；本地缓存删了要重新
  下载，误删代价高。→ 把入口**收进「更多 ⋯」菜单**，危险动作弱化；点开后用**弹窗做二次确认**，
  且必须勾选「我已了解」才能点「确认移除」。
- **新增 `src/components/Modal.vue`**（通用可复用）：Teleport 到 body、遮罩点击/Esc/× 关闭、
  `role=dialog` + `aria-modal` + 自动标题 id、焦点自动落入面板并 Tab 焦点圈闭、打开时锁 body 滚动、
  窄屏底部抽屉式圆角。全部走 `--reader-scrim-*`/`--paper-*`/`--shadow-3`/`--duration-*` token。
- **polish**：danger 按钮只用朱砂 tokens（`--accent-strong` / `--accent-soft`）；勾选确认区用
  `--paper-1` 底 + `accent-color` 勾选框；取消/确认主次分明。
- **adapt**：菜单窄屏不右漂（`margin-left:0`）；弹窗 ≤480px 变成底部 `92dvh` 抽屉，触控友好。

## 13. 踩坑记录：composable 返回的 Ref 在模板里不会自动 unwrap

- `ChapterSwitcher "props.chapters.findIndex is not a function"` + 子路由图片不显示，根因是
  `ChapterView` 直接 `:chapters="nav.chapters"`、`:pages="nav.visiblePages"`——`nav` 是普通对象，
  **嵌套属性里的 Ref 不参与模板自动解包**，子组件收到的是 Ref 对象。
- 修复：composable 一律**解构到 setup 顶层**再喂模板/子组件（`ChapterView` 已改；
  `ChapterSwitcher` 另加 `Array.isArray` 防御，防未来再传错）。
- 这是给后续维护者的硬约束：**使用自定义 composable 时，返回值里的 Ref 要 top-level 解构使用。**

## 14. 多章节「上一话/下一话 + 中间话选择」中间页（Impeccable：critique → polish → adapt）

- **grill 确认**：多章节所有入口最终收敛到**章节维度渲染**——父详情页只出章节目录（不塞 7000 页），
  点话进 `ChapterView` 只渲染该话页索引；中间页（上一话/中间话/下一话）只在多话时渲染。
- **critique（38/40）**：P1 = 152 话时“我在第几话/共几话”的定位锚点不足 → 条首加非交互计数
  chip「第 X 話 / 共 N 話」（`role=status`）+ 头部 meta 补「X / N 话」；`Home/End` 直达首/末话。
- **polish（对齐 token）**：序数圆直径收敛为 `calc(var(--control-md) - var(--space-4))`（不再裸写
  1.75rem）；计数 chip、滚动条、圆角、间距、动效全部走 `--space-*/--radius-*/--duration-*`/朱砂系。
- **adapt**：桌面 `[上一话][中间选择条][下一话]` 一行；≤720px 按钮换行上一行、中间条整行下一行；
  chip/按钮触控高恒 `--control-md`（≥44px），滚动条 6px 细条 + hover 强调。
- 报告落 `.impeccable/critique/2026-08-20T16-24-51Z__src-chapter-forward-back-pager.md`。

## 15. 阅读器「分章作用域」+ 去掉子详情页 tabs 前的「共多少章节」chip

- **回访确认**：多章节 7227 页的合集，从章节子路由或父详情「开始阅读」点进阅读器时，旧实现
  `ReaderView` 仍按整本 7227 页铺 DOM（`content-visibility` 只省绘制、DOM 节点仍在），
  UI 上表现为「点进去还是全量的、没有分章节」。
- **修复——`ReaderView` 章节作用域**：读取 `route.query.chapter`，若有则把 `scopedPages`
  收敛到 `[chapter.start, chapter.start + page_count)`，`pageGroups/groupIndex/goToPage/页码/页脚`
  全部随作用域换算（章内本地页码）；跨话 `N/P`、底部「本话完 · 下一话 →」仍可跳，跳时
  `setScope(id)` 同步切 `?chapter=` 并重定位。无 `?chapter=`（单章作品/整本直达）保持整本跨话阅读。
- **父详情直入也分章节**：`ComicDetailView.startReading` 对多章节带 `?chapter=`（按全局页定位所属
  话），让「开始阅读/继续阅读/从第 1 页开始」同样进章节维度，绝不一次铺 7227 页。
- **去掉冗余 chip**：子详情页 ChapterSwitcher tabs 最前头那枚「第 X 話 / 共 N 話」计数 chip
  与头部 meta（`X / N 话`）重复且占位，删除（组件不再渲染，pager 更干净）。
- **阅读器加「上一话」悬浮钮**：分章作用域下，停在当前话第一页且存在上一话时，在底部浮现
  `← 上一话`（文案空标题回落「第 N 話」，与`本话完 · 下一话 →`同一套材质）；跨话后 URL 的
  page 参数同步对齐到目标页（`read/8?chapter=518074`），避免地址栏页码与实际页不一致。
- **顺手修掉既有类型债**：`ReaderView` `currentChapter.value` 可能为 null（改用局部变量收窄）；
  `ChapterSwitcher` 适配 @vueuse 14.x——`useScroll` 不再返回 `scrollTo`，改给响应式 `x` 赋值；
  `:ref` 回调补 `HTMLElement` 断言。`vue-tsc --build --force` 全绿（0 error）。
- **验证**：152 话 / 7227 页书 `jm/518074`——父详情只出 152 张章节卡片；第 2 话子路由 37 tiles +
  上一话/中间 tabs/下一话中间页；从父详情进入阅读器 8 页（第 1 话）、从章节进入 37 页（第 2 话）；
  第 2 话首页显示「← 上一话：第 1 話」、末页显示「本话完 · 下一话：2 →」，跨话 URL 页码对齐；
  单章书 `jm/1242163` 父详情整本网格 + 阅读器 39 页，零回归。`vp check` / `vp test` / `vue-tsc` 全绿。

## 16. 全局组件与 UI 质感系统性升级（纸质典藏物理感，拒绝 8-bit 割裂）

- **风格决策**：明确不走 8-bit 复古街机游戏风（防 CJK 汉字可读性崩塌、防抢夺高保真漫画原画焦点、防与“纸间”暖纸墨色品牌隐喻脱节），而是收敛并升华为「实体印刷与档案室物理质感（Physical Print & Archival Craft）」。
- **组件与交互打磨**：
  1. `TagFilterBar`：删除 unicode `♥` emoji 字符，改用矢量 SVG 心形图标；合并两个孤立的 cluster 容器为一体化筛选工具栏，加入典藏细分隔线。
  2. `ToastStack`：下沉全局样式至组件内部，引入印章风格指示徽标（`✕`/`✓` 圆形印戳），支持 error / info / success 多色调微质感。
  3. `LibraryHero`：统计数字卡片增加左侧朱砂标尺线与暖纸色底衬，强化图书馆卡片目录索引感。
  4. `ComicCard`：将视口 media query 升级为 CSS 容器查询（`@container (max-width: 380px)`），使卡片在网格自适应缩放时按自身宽度换行；空封面提供典藏书脊占位带；车号印章增加微磨砂与典藏边框。
- **验证**：全部沿用既有 tokens 与 VueUse；`vp check` 与 `vp test` 全绿。

## 17. 前端组件与 Hook 深度解耦（视图编排化 + 状态下沉 Composable）

- **痛点治理**：`ReaderView.vue` 曾膨胀至 1050 行，混杂自动翻页、分页切片与顶栏延时三大状态机；`LibraryView.vue` 混杂多字段检索与排序。
- **解耦重构**：
  1. `useLibraryFilter.ts`：从 `LibraryView` 抽离模糊搜索、标签频率统计、4 种排序与喜欢过滤；
  2. `useAutoTurn.ts`：从 `ReaderView` 抽离自动翻页倒计时、节拍器、页面可见性与暂停切换状态机；
  3. `useReaderPaging.ts`：从 `ReaderView` 抽离分页分组、作用域映射（`toLocalPage`）、前后话跨章探测与边界计算；
  4. `useReaderChrome.ts`：从 `ReaderView` 抽离顶栏与 HUD 延时隐显控制。
- **规则沉淀**：
  - 视图只做纯编排（View Thinness），单文件 `<script setup>` 原则上不超过 150 行；
  - 严格遵守 `DESIGN_NOTES §13` 顶层解构约束；
  - 规则已同步固化至 [`AGENTS.md`](file:///home/miku/dsh/comic-shelf/AGENTS.md) 与 [`docs/agents/frontend.md`](file:///home/miku/dsh/comic-shelf/docs/agents/frontend.md)。
- **验证**：`vp check`（58 文件 0 error）、`vp test` 单元测试全部通过。

## 18. 阅读器 Loading 界面重构（WebP 插画 + 纸间呼吸微光质感）

- **需求**：废弃旧的 `page-loading-1/2.gif`，使用新引入的 4 张 WebP 插画（`/loading-1.webp` ~ `/loading-4.webp`）；降低图片强烈色彩感、但要保留明确的加载进行态与每次进入随机选图规则。
- **Impeccable 设计决策**：
  1. **插画资产现代化**：将原 JPG 转换为高质量轻量 WebP（平均体积 ~430KB），废弃体积臃肿且帧率受限的旧 GIF 动图。
  2. **色彩温和降噪（Quiet Palette）**：插画应用 `filter: saturate(0.68) contrast(0.92) brightness(0.88)`，避免高饱和二次元原图在黑暗阅读器环境下刺眼或抢夺视觉焦点。
  3. **实体装订加载感（Active Craft）**：
     - 插画上方覆盖轻柔斜向光斑掠过动效（`shimmer-sweep` 2.4s 无限循环）；
     - 整体卡片包裹磨砂纸色框与柔和投影，辅以极轻微的物理呼吸微动（`loading-breathe`）；
     - 底部搭配 mono 字体「正在装订书页…」与朱砂色脉冲呼吸指示点。
  4. **组件封装与复用**：沉淀 `src/components/reader/ReaderLoadingState.vue`，无缝复用于阅读器首屏整本加载与单页渐进式加载（`compact` 模式）；支持 `prefers-reduced-motion` 优雅降级。
- **验证**：`vp check`（64 文件 0 error）、`vp test`（5 套测试 10 用例通过）。

## 19. 阅览室门禁与通行口令设计（Auth Modal & Security Indicators）

- **设计诉求**：公网部署与内网穿透时需要访问门禁与防盗链，但绝不应给用户带来复杂的“传统登录注册系统”的认知负担，需延续「私人阅览室 / 卡片目录」典藏质感。
- **Impeccable 决策**：
  1. **视觉一致性**：`AuthModal.vue` 废弃单字红章，改用官方 `brand-icon.webp` 圆角徽标徽章，搭配双语眉标 `纸间 · PAPER ROOM` 与衬线主标题 `阅览室通行口令`；
  2. **交互体验（Zero-Friction Unlock）**：
     - 自动聚焦密码框，支持 Enter 提交、密码显隐切换；
     - 401 拦截静默接管，不触发刺眼的全局红色报错 Toast；
     - 解锁成功后通过 `onAuthSuccess` 全自动重新拉取书架与来源导航，无需用户手动刷新；
  3. **顶栏安全状态指示**：
     - `AppHeader.vue` 右侧仅在开启 `COMIC_SHELF_SECRET` 时呈现极简状态徽章（`🔒 已通行` / `🔒 未解锁`），支持点击一键重新锁定；
     - 未配置密码时保持极简留白，不增加任何多余视觉干扰。
- **验证**：`vp check`（67 文件 0 error）、`vp test` 单测全绿。

## 20. 环境暗印水印、全幅漫画加载与动态插画资产池（grill-with-docs 确认 → Impeccable: shape → critique → polish → adapt）

- **需求背景**：用户喜爱 loading 看板角色插画，期望将其作为弹窗与各界面背景图（要求极浅、绝不影响看图与文字），同时指出阅读器单页 loading 尺寸太小，并要求后续新增 loading 角色插画能够自动感知和自适应。
- **Impeccable 设计决策**：
  1. **插画资产池零配置自适应（Dynamic Illustration Pool）**：
     - 新增 `src/composables/useIllustrationPool.ts`，利用 Vite `import.meta.glob('/public/loading-*.{webp,png,jpg,jpeg}')` 动态扫描并管理插画；
     - 提供 `getRandomIllustration()` 与 `getIllustration(variant)`，后续只需放入 `loading-5.webp` 等新图即可全站自动扩容轮换，彻底废除写死的 `1 | 2 | 3 | 4` 联合类型。
  2. **典藏环境暗印水印（Ambient Watermark）**：
     - 新增 `src/components/AmbientWatermark.vue`，作为纯背景层（`pointer-events: none`、`z-index: 0`、`isolation: isolate`）；
     - 极低不透明度与纸张墨色融合：亮色模式 `opacity: 0.042` + `mix-blend-mode: multiply` + 灰度降噪；暗色模式 `opacity: 0.06` + `mix-blend-mode: screen`；
     - 采用径向羽化遮罩（`-webkit-mask-image: radial-gradient(...)`），文字与卡片浮于上层，仅留白处隐约呈现角色剪影水印；
     - 范围精确定位：在书架（`LibraryView`）、详情页（`ComicDetailView`）、章节页（`ChapterView`）及弹窗（`Modal` / `AuthModal`）启用；阅读器（`ReaderView`）正文严格避让，保护纯黑暗室读图纯净度。
  3. **等比全幅漫画加载占位（Full-frame Comic Loading）**：
     - 重构 `ReaderLoadingState.vue` 支持 `fullFrame` 模式，并升级 `ComicPageImage.vue` 与 `ReaderView.vue`；
     - 尺寸撑满视口/槽位（`min-height: clamp(18rem, 60vh, 52rem)`），消除图片就绪时的突兀跳版（Layout Shift）；
     - 大画幅呈现看板插画、典藏装订纸纹微光与呼吸脉冲，让加载进行态饱满沉浸。
- **验证**：`vp check`（71 文件 0 error）、`vp test`（8 套测试 22 用例全绿）、`vp build` 生产构建通过。
