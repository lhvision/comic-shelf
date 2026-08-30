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
  `docs/agents/architecture.md`。旧实现只拉 `/photo/{album_id}`，多话合集取不到。
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
  - 规则已同步固化至 `AGENTS.md` 与 [`docs/agents/frontend.md`](./docs/agents/frontend.md)。
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

## 21. 全局 View Transitions API 系统化改造（grill-with-docs 确认 → Impeccable: shape → critique → polish → adapt）

- **需求背景**：参考张鑫旭文章与 W3C / MDN 最新规范，引入 View Transitions API 与 Element-scoped View Transitions，对全站页面跳转、封面形变、弹窗显隐、图片加载就绪及核心按钮状态演进进行系统化物理质感升级。
- **Impeccable 设计决策**：
  1. **场景化路由层级过渡（Directional SPA Transitions）**：
     - `src/router/index.ts` 接入 `beforeResolve` 与 `document.startViewTransition({ update, types })`；
     - 依据路由等级（书架 1 < 详情 2 < 章节 3 < 阅读器 4）自动计算 `forward`（前进推入）与 `backward`（后退带回）方向；
     - 结合 CSS `:active-view-transition-type(forward/backward)` 实现微视差位移（`-12%` 至 `+100%`），严控动效节奏（`--duration-2` 260ms + `--ease-out`），杜绝全幅跳跃。
  2. **书架到详情「共享封面形变」（Shared Cover Morph）**：
     - 新增 `src/composables/useCoverTransition.ts` 动态管理激活卡片；
     - 点击卡片时赋予封面 `view-transition-name: comic-cover-active`，与详情页 Hero 封面无缝对齐，实现如实体书取阅般的平滑尺寸与位置连续插值（神奇移动）；
     - `router.afterEach` 自动延时清理过渡名称，确保书架无重名冲突与内存泄露。
  3. **局域视图过渡门面（Element-Scoped View Transitions）**：
     - 新增 `src/composables/useViewTransition.ts`，优先尝试现代 `element.startViewTransition()`，降级全局 `document.startViewTransition()` 与同步执行；
     - `ComicPageImage.vue`：图片 `@load` 时驱动画卷装订插画平滑交叉溶解为高保真漫画页，消除突兀跳版；
     - `FavoriteButton.vue`：红心点赞在局部子树内平滑形变与变色；
     - `ImportPanel.vue`：收录按钮与并发步进器文字平滑流转；
     - `Modal.vue` / `AuthModal.vue`：采用 Vue 原生 `<Transition>` 实现分层进退场动效（遮罩暗室沉降 + 面板弹簧微弹/退场微降），避免 View Transition 快照带来的亚像素位图模糊与遮罩空间畸变，保持 100% 高保真矢量排版。
  4. **书架网格重排与筛选过渡（Shelf Grid Rearrange & Filtering）**：
     - 为书架每张卡片分配唯一识别 `view-transition-name: card-<source>-<source_id>`；
     - 标签筛选（`selectTag`）、只看喜欢（`toggleFavorites`）、排序切换（`onSortChange`）及以图搜图清除均由 `withViewTransition` 驱动；
     - 触发变更时，留存卡片平滑滑行重排至新槽位，被剔除卡片柔和淡出，新匹配卡片淡入，完全还原张鑫旭文章经典的“列表倒序与元素增删神奇移动”。
  5. **错误防御与生命周期兜底（Error Handling & Pitfall Learnings）**：
     - **严禁在 SPA 声明 `@view-transition { navigation: auto; }`**：该 CSS 规则为 W3C MPA 多页跳转专属；在 Vue Router 单页应用中声明会导致 Chrome PerformanceObserver 在路由切换时误采集空指标，抛出 `Cannot read properties of undefined (reading 'startTime')`。SPA 必须且仅能通过 JS 编程式调用 `document.startViewTransition()`；
     - **阅读器切页隔离**：阅读器内同路由翻页/切话（`to.name === 'reader' && from.name === 'reader'`）严禁触发全屏 View Transition，杜绝快速翻页时与虚拟滚动并发冲突产生的 `AbortError`；
     - **Promise 全流程绑定 catch**：所有 `startViewTransition` 的 `ready` / `finished` / `updateCallbackDone` 统一绑定 `.catch(() => {})`，防止动画被抢占时向控制台溢出未捕获异常；
     - **单页图片性能收敛**：单页漫画加载使用原生 CSS `opacity` GPU 硬件加速，不使用 `startViewTransition` 避免 50+ 页并发阻塞；
     - **弹窗动效分工**：弹窗通过 Vue `<Transition>` 驱动进退场，彻底避免 View Transition 位图快照在全屏遮罩上产生的空间拉伸畸变与字体亚像素模糊。
  6. **无障碍与优雅降级（Accessibility & Resilience）**：
     - 严格支持 `@media (prefers-reduced-motion: reduce)`，系统偏好开启时关闭全部视图动画并直接同步更新；
     - 绝不在模板内产生多重 transition 命名冲突，所有动效统一收敛至 `tokens.css`。
- **验证**：`vp check` 0 warning / 0 lint / 0 type error，单测全部通过。

## 22. 图片全链路流转体系与视口渲染性能闭环（Architecture & Pipeline）

- **背景**：随着书库规模扩大及 30 秒全长角色动画接入，需严格明确「页面索引与阅读器的资源复用逻辑」及「渐进式渲染规范」，防止后续重复讨论或误引入劣化体验的低清模糊占位（LQIP）。
- **架构流转图**：
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
          (48 页/批增量懒展开)                  • GPU 硬件加速 opacity 交叉淡显
        • content-visibility: auto            • 视口外页面跳过渲染与 Paint
  ```
- **核心工程与视觉决策**：
  1. **零重复下载与天然预热（Natural Pre-warming）**：
     - 用户在详情页或章节页浏览 48 页/批的页面索引时，后端 `ensure_page_thumb` 在生成 360px JPEG 缩略图的同时已完成原图的本地磁盘落盘与解密；
     - 随后点击进入阅读器时，大图直接从本地磁盘/浏览器内存缓存秒级直出，**0 远端网络开销**。
  2. **拒绝 LQIP 模糊马赛克占位**：
     - 漫画属于高对比度黑白线条与细腻网点，强行拉伸 20px 模糊缩略图会造成脏乱马赛克噪点，严重破坏私人阅览室的纸质克制感；
     - 采用 **「全幅磨砂装订卡片 + 30s Live2D 缇雅动画（`loading-tiya.webp`）」+「`opacity` 交叉淡入」**，视觉清爽、仪式感强且 0 额外 DOM / 显存开销。
  3. **离屏视口虚拟化全覆盖**：
     - `ComicCard.vue`（书架卡片）、`ChapterCard.vue`（章节卡片）、`PageTile.vue`（页面索引瓦片）及 `.reader-spread`（阅读器双联页）全量配置 `content-visibility: auto`，万级列表与超长条漫离屏自动跳过 Layout & Paint。

## 23. 双口令安全门禁与动态看板头像轮换体系（Dual-Secret Gate & Randomized Brand Avatars）

- **需求背景**：NAS 与公网部署环境下，需要防范恶意扫描器探测与图片代理肉鸡风险，同时支持小圈子好友分享（纯只读）与馆长全权管理的权限分层；同时用户喜爱高精看板立绘，期望在保留黄金比例裁切的同时支持每次刷新随机轮换看板头像。
- **核心设计与工程决策**：
  1. **双口令安全门禁体系（Dual-Secret Gate）**：
     - `COMIC_SHELF_SECRET`（馆长全权口令）与 `COMIC_SHELF_GUEST_SECRET`（访客阅览口令，可选）；
     - 单输入框智能分流，根据口令内容自动鉴权为「馆长」或「访客」，未提供有效口令者最外层中间件 100% 拦截（HTTP 401），零元数据与图片字节泄露；
     - 访客模式下彻底裁切写操作 UI（收录栏、删除菜单、全量缓存、并发配置），已收藏本子以只读红心印章展示。
  2. **访客就地无感升级为馆长（In-place Elevation）**：
     - `AppHeader.vue` 呈现 `〔 馆长已入座 〕`（朱砂浅底）与 `〔 访客阅览 〕`（墨印浅底）双态微印；
     - 访客点击右上角徽标即可原地弹窗输入馆长密钥升级管理权限，无需登出重进。
  3. **动态看板头像轮换（`useBrandIcon`）**：
     - 黄金比例裁切 4 款 512×512 超清 WebP 头像收录于 `public/brand-icons/`；
     - `useBrandIcon` Composable 在每次页面初始化时随机抽选 1 款，并同步联动浏览器 Favicon（`<link rel="icon">`）、网页顶栏 Logo 与通行口令弹窗微印，兼具灵动趣味感（Delight）与视觉统一性。
- **验证**：`vp check`（76 文件 0 error）、`vp test` 单测全绿、`detect.mjs` 0 反模式。

## 24. 本地自建图集与全站元数据/标签管理系统（Local Comics, Tag Management & Upload Queue）

- **需求背景**：用户期望收录本地图片集合与视频拆帧（如 `public/tiya-frames`）作为自建漫画，要求界面元数据与禁漫保持 100% 视觉一致；支持单话/多章节编排与增量追加；开放全站标签打标签与删除功能，并严格收敛至馆长权限；同时限制上传并发以保护服务器。
- **Impeccable 设计决策**：
  1. **自建工坊大画幅二级路由（`/create`）与书架快速通道**：
     - `ImportPanel.vue`：引入 `〔 禁漫车号 〕` 与 `〔 本地自建 / 拆帧 〕` 标签页，支持直接填入服务端本地路径（如 `public/tiya-frames`）秒级扫描收录（0 网络传输）；
     - `CreateComicView.vue`：开辟 1200px 典藏自建工坊，左栏编排多章节与拖拽上传，右栏编排卡片目录与元数据（车号 Slug、标题、原作、创作者、人物、标签与叙述），桌面双栏 / 移动端单栏自适应；
     - **微交互与标签药丸（Tab Pills）排版**：统一 `ImportPanel.vue`、`CreateComicView.vue` 与 `AppendPagesModal.vue` 模式切换 Pill 的内边距（`0.35rem 0.85rem`）与容器下边距，彻底杜绝激活态文字紧贴边框与挤压排版的问题。
  2. **典藏资料、封面展示页码与标签编排弹窗（`EditMetadataModal.vue`）**：
     - 详情页开放「编辑资料」弹窗（馆长专享），提供实时修改标题、作者、叙述及标签管理；
     - **封面自定义展示页码（`cover_indices`）**：开放 4 个封面槽位序号输入（默认 1..4），支持自由指定任意全局页码（如 `[1, 10, 25, 50]`）作为书架卡片与详情页轮播的展示封面；
     - 标签管理区：支持当前标签 Chip 文本与删除按钮（SVG 细线 `×`）精确垂直居中对齐，热门快选采用独立换行弹性流（`popular-chips`）与清晰垂直行距（`row-gap: var(--space-2)`），输入框支持 `Enter` / `空格` / 逗号快捷新增，并自动推荐全书库热门标签。
  3. **单话/多章节增量追加弹窗（`AppendPagesModal.vue`）**：
     - 本地漫画详情页提供「增量追加…」入口，支持追加至指定已有话末尾或创建新章节，支持网页多图上传与服务器目录扫描双模式。
  4. **并发受限上传队列（`useUploadQueue`）**：
     - 客户端采用 3 路受限并发分批上传，细粒度响应式追踪整体与当前文件进度，支持主动取消，杜绝瞬间击穿服务器 IO 与连接池。
  5. **严格的馆长权限收敛（Curator-Gated）**：
     - 前端所有编辑/追加/自建入口仅在 `canWrite`（馆长态）可见；
     - 后端 `auth_and_security_middleware` 与 API 端点全面校验馆长身份，访客直接 403 拦截。
  6. **表单组件拆分与 VueUse 极致精简（Component Decoupling & VueUse Integration）**：
     - 提取通用表单组件 `TagManager.vue`（支持 `v-model` 双向绑定、分词添加、SVG 居中删除、全库热门快选）与 `CoverIndicesPicker.vue`（4 槽位页码输入、实时越界与负数纠偏、默认槽位安全回退），`EditMetadataModal.vue` 与 `CreateComicView.vue` 各精简 ~150 行代码；
     - 全面接入 VueUse `useFileDialog` 与 `useDropZone`，彻底剔除隐藏 DOM `<input type="file">` 与原生拖拽事件胶水代码，获得天然响应式的 `isOverDropZone` 拖拽视觉反馈。
  7. **弹窗固定头尾与滚动锁闭安全闭环（Modal Fixed Layout & Scroll-Lock Invariant）**：
     - **固定头尾与局部滚动**：`Modal.vue` 重构为 Flex 布局，标题栏（`modal-head`）与操作底栏（`modal-foot`）吸顶/吸底固定，超长表单与图片仅在 `modal-body` 区域平滑滚动；
     - **VueUse `useScrollLock` 安全闭环**：使用 `useScrollLock(document.body)` 并在 `onUnmounted` 严格释放；`ComicDetailView` 在弹窗保存后使用静默刷新（`load(silent = true)`），杜绝因页面重新挂载骨架屏而导致弹窗销毁时残留 `overflow: hidden` 锁死页面滚动的问题；
     - **封面即时热刷新缓存穿透（Cache Busting Tag）**：`cover_paths()` 自动附加基于 `updated_at` 的版本摘要参数（`?v=hash`），彻底解决浏览器 `Cache-Control: immutable` 导致封面修改后沿用旧缓存不刷新的问题。
- **验证**：`vp check`（85 文件 0 error）、`vp test` 单测全绿（`TagManager.spec.ts`、`CoverIndicesPicker.spec.ts`、`useUploadQueue.spec.ts`）、`vp build` 生产构建成功；成功完成 `public/tiya-frames`（917 帧）秒级全量收录测试与自定义封面序号热更新测试。

## 25. 书架卡片渲染隔离与 48 图预算增量加载（grill-with-docs 确认 → Impeccable: shape → critique → polish → adapt）

- **需求与根因定位**：
  1. 书架卡片在 Hover 时出现「上面边框不见了 + 底下留黑」的渲染 bug；
  2. 根因为之前在 `ComicCard.vue` 引入的 `content-visibility: auto`。W3C 规范中该属性自动开启 `contain: paint`，使得卡片 Hover 向上浮动（`-0.35rem`）与柔和弥散阴影（`--shadow-2`）超出父容器 padding-box 时被浏览器 Compositing 硬件图层生硬裁剪截断。
- **Impeccable 设计决策与重构**：
  1. **属性解耦与精准隔离（Precise Containment）**：
     - `ComicCard.vue` 移除 `content-visibility: auto`（及其强制的 `contain: paint`）；
     - 切换为 `contain: layout style` + `container-type: inline-size`，既获得组件级布局/样式计算隔离，又 100% 保留 Hover 浮动、叠牌封面旋转与柔和投影的自由溢出渲染。
  2. **48 图预算增量呈现（48-Image Budget Shelf Chunking）**：
     - 针对海量藏书书架，由于每本漫画展示 4 张封面图（1 主封面 + 3 叠牌封面），将详情页成熟的 48 图预算移植至书架，确立 **12 本/批（12 × 4 = 48 张封面图）** 的增量呈现步长；
     - `ComicGrid.vue` 接入 VueUse `useIntersectionObserver` 监听底部哨兵（`rootMargin: '600px 0px'`），用户滚动至底部时平滑自动展开下一批；筛选/检索/排序切换时即时重置为初始批次，保持 View Transitions 极速响应。
- **验证**：`vp check`（0 error）、`ComicGrid.spec.ts`（4/4 测试通过）、`e2e/tests/example.spec.ts` E2E 校验通过。

## 26. 全量代码审查与架构可维护性治理（Full-Repo Code Review & Architectural Hardening）

- **背景**：针对全仓代码（130+ 文件，~13,300 行）进行全量 Code Review，排查多章节页码连续性、后台并发任务生命周期、路径安全沙箱、主事件循环调度及前端视图规范。
- **架构与安全决策**：
  1. **多章节页码单调连续性不变量**：`storage.py` 中 `append_pages` 往指定章节增量追加页面时，统一按章节顺序单调重排所有后续章节的 `start` 起始页号与全书 `meta.pages` 的 `index`，保证全局页码严格连续单调递增；
  2. **后台任务生命周期与并发安全**：`jobs.py` 为全局任务字典引入 30 分钟 TTL 过期淘汰与 100 条容量上限，并在 `_locker` 互斥保护下同步更新任务状态与异常信息，杜绝长期运行下的内存膨胀与数据竞争；
  3. **服务器路径导入沙箱防护**：`storage.py` 引入 `_is_path_allowed` 校验，强制限制本地导入路径必须位于数据目录或受信任的 `COMIC_SHELF_ALLOWED_DIRS` 白名单内，防御任意宿主机目录扫描；
  4. **FastAPI 主事件循环解耦**：`main.py` 将阻塞式的局部特征识图（`search_imsearch`）与本地磁盘写入（`store.append_pages`）通过 `asyncio.to_thread` 调度到后台线程池，消除异步路由中的同步阻塞 I/O；
  5. **前端视图轻量化（View Thinness）与 Composable 下沉**：新增 `src/composables/useLocalWorkshop.ts`，将 `CreateComicView.vue` 脚本从 224 行下沉至 45 行；以图搜图 Composable 统一接入 `src/api/client.ts` 保证 Token 鉴权与 401 拦截，并增加服务就绪状态自动轮询；
  6. **冗余文件与单测闭环**：清理历史备份文件，修复 `test_imsearch.py` 模块导入路径与传参，补齐多章节页码重排单测。
- **验证**：`vp check`（131 文件 0 error / 0 warning）、后端全量单测全绿、前端精准单测全绿。

## 27. 全量审查后收录崩溃复盘与错题本体系建设（Post-Mortem & Pitfalls Ledger）

- **事故背景与根因复盘**：
  1. **事故现象**：在全量 Code Review 后，前端执行「收录到纸间」或本地自建/追加操作时立即报错崩溃（HTTP 500）；
  2. **代码根因**：`backend/app/main.py` 在清理依赖时误删除了 `is_admin` 导入，而 `auth_and_security_middleware` 的写操作校验仍在使用 `if not is_admin(request):`，直接引发运行时 `NameError: name 'is_admin' is not defined`；
  3. **测试漏网根因**：`backend/test_auth.py` 原先仅单独测试了 `auth.py` 内部函数，绕过了挂载在 FastAPI 顶层的 `auth_and_security_middleware` 真实 HTTP 请求链路；且后端缺乏静态符号检查。
- **治理与防退化方案**：
  1. **鉴权术语彻底收敛**：`auth.py` 与 `main.py` 统一收敛使用标准术语 `is_curator`，彻底废弃易混淆的 `is_admin` 别名；
  2. **异常拦截与友好提示（404 容错）**：`JMProvider.fetch` 增加对下架/不存在车号（如 `1188845`）的 `album_missing` 前置探测，`import_comic` 转换为标准 HTTP 404 响应，消除晦涩的正则解析 500 崩溃；
  3. **中间件全链路测试集成**：在 `backend/test_auth.py` 中新增 `test_auth_and_security_middleware`，对馆长、访客、未授权各态下的写操作（POST /api/library/import）、读操作及公网端点进行端到端全覆盖；
  4. **零依赖 Python 静态 AST 检查器（`backend/check_backend.py`）**：引入基于 Python 标准库 AST 的作用域检查器，实时校验语法错误、模块导入完整性及未定义变量；
  5. **错题本体系落地（`docs/PITFALLS.md`）**：建立常态化错题本索引，按后端/前端/过渡/安全分类固化 7 大核心避坑红线，并写入 `AGENTS.md` 与 `CONTEXT.md` 强制防退化门禁。
- **验证**：`pnpm test:py` 全绿（静态 AST 检查 + 中间件全链路测试 + 增量更新 + 权限 + 识图单测）、`vp check`（0 error）、JM 下架车号 `1188845` 404 容错测试通过、正常车号 `523607` 本地与远端收录测试通过。

## 28. 高并发冷热加载优化 + 多章节缓存 UI 体系化 + 文本截断与 Hover 提示（grill-with-docs 确认 → Impeccable 2345 规范）

- **背景与痛点**：
  1. 首页 12 本书每张卡片默认渲染 4 张封面（1 前景 + 3 扇形副封面），首页一次触发 48 个图片请求，20 人并发达 960 个请求；
  2. 详情页 48 个页面缩略图在冷缓存（首次加载）时触发高并发远端下载与 Pillow LANCZOS 缩放，易导致 CPU/GIL 争抢及上游 429 封禁；
  3. 多章节详情与子路由缺少直观的章节级缓存进度，自主上传的多章节作品需要统一的视觉体验；
  4. 超长按钮与原生下拉控件在文字截断时缺少 hover 提示。
- **方案决策与落地**：
  1. **首页卡牌副封面交互延迟加载（Hover/Focus-Triggered Deck）**：
     - `ComicCard.vue` 引入 `isDeckActive` 响应式状态，在 `@pointerenter.once` 与 `@focusin.once` 时才加载背景 3 张扇形封面；
     - 初始首屏请求量直降 75%（12 本仅 12 个请求），100% 保留纸质卡牌层叠结构与 Hover 扇形展开动效。
  2. **详情页切片步长收敛与后端并发门禁（Thumbnail Concurrency Gate & Prefetch Warming）**：
     - `useChapterNavigation.ts` 将 `CHAPTER_PAGE_STEP` 步长从 48 收敛为 **24**，首屏瞬时缩略图请求减半，触底平滑增量；
     - `storage.py` 引入 `_thumb_semaphore` 信号量门禁（默认最多 4 个并发 worker 进行 Pillow LANCZOS 转换，通过 `COMIC_SHELF_THUMB_CONCURRENCY` 调节）；
     - `storage.prefetch` 预缓存流程同步生成各页 360px 缩略图，将冷流量前置转换为 100% 命中磁盘的热缓存。
  3. **多章节/子章节缓存 UI 体系化（Multi-Chapter Cache Progress UI）**：
     - `ChapterCard.vue` 集成标准 `CacheProgress.vue`，底部呈现 3px 物理进度轨；
     - `ChapterView.vue` 顶部导航栏右侧嵌入本话专属 `CacheProgress`，支持后台任务呼吸光点与成功绿实时联动；
     - 自主上传（`CreateComicView` / `AppendPagesModal`）章节天然为 `cached: true`，UI 自动呈现为「本地 100%」，零特殊代码分支。
  4. **文本超长与下拉框 Native Title 全面覆盖**：
     - 针对 `ChapterCard`、`ChapterSwitcher`、`AppendPagesModal`（`select`/`option`）、`ThemeSelect`、`DetailActionBar`、`ReaderTopBar`、`MetadataPanel` 全量补齐动态原生 `:title` 属性，符合 a11y 且 0 额外 DOM 开销。
- **验证**：`vp check`（134 文件 0 error / 0 warning）、`vp test src/__tests__/ComicGrid.spec.ts` 4/4 通过、`pnpm test:py` 全量通过。

## 29. 单章升阶为多章节体系 + 子章节就地重命名与删除管理（grill-with-docs 确认 → Impeccable 2345 规范）

- **背景与痛点**：
  1. 用户在创建/导入单章节漫画（`chapters == []`）后，通过「增量追加」添加「第 2 话」时，原旧页面未被封装为「第 1 话」，导致 `meta.chapters` 仅有 1 话（且 `start` 为旧页数+1），前端仍视作单章节且页码错位（如 `LOC_loc_20260825_023256`）；
  2. 多章节子路由（`ChapterView.vue`）缺少对当前单话名称的重命名与单话物理删除入口。
- **架构决策与落地**：
  1. **单章节向多章节平滑自动升阶（Flat → Multi-Chapter Promotion）**：
     - `storage.append_pages` 判定 `is_new_chapter` 时，若作品原无章节（`not meta.chapters`），自动将已有 1~N 页封包为「第 1 话」（`id="c1"`, `start=1`, `page_count=N`），自动迁移平铺文件至 `pages/c1/` 并生成封面；
     - 追加的页面作为「第 2 话」（`id="c2"`, `start=N+1`），`meta.chapters` 生成长度为 2 的完备章节表，详情页无缝切换为多章节目录与子路由。
  2. **历史损坏数据自动自愈（Auto-Healing）**：
     - `storage.load_meta` 增加自愈校验：若首个章节 `start > 1`（存在未编入章节的孤儿页面），自动合成「第 1 话」并迁移文件重构章节索引；
     - 现存 `LOC_loc_20260825_023256` 已即时自愈为标准的 2 话多章节作品（第 1 话 121P，第 2 话 1P）。
  3. **子章节名称修改与物理删除管理（Chapter In-Place Renaming & Deletion）**：
     - 新增 `PATCH /api/library/{source}/{source_id}/chapters/{chapter_id}` 与 `DELETE /api/library/{source}/{source_id}/chapters/{chapter_id}` 端点；
     - 删除单话时，后端物理销毁该话 `pages/<chap>` 与缩略图，并对全书后续章节 `start`、`index` 与 `meta.pages` 执行单调连续重排；
     - `ChapterView.vue` 头部集成「编辑章节」Modal 与「⋯ 更多」下拉菜单（内含「删除本话…」危险操作及防误触二次确认弹窗），删除成功后平滑路由回退至父详情页并弹出 Toast。
- **验证**：`pnpm test:py` 全量通过（新增 3 组针对升阶、CRUD 与自愈的自动化单测）、`vp check` 0 error / 0 warning、`LOC_loc_20260825_023256` 线上状态验证通过。

## 30. 现代 CSS text-fit 调研与弹性字阶底线（Typography Floor & Progressive Enhancement）

- **背景与调研**：
  - 针对张鑫旭《卧靠，这是好东西，CSS text-fit属性简介》中提及的现代 CSS `text-fit` 属性（`text-fit: <fit-type> <fit-target>`，Chrome 150+ / CSS Text Module 提案），评估其在纸间排版系统中的适用性；
  - 传统方案（`clamp(...)` + `cqw` 估算、JS 动态测算 `fitty`/Canvas `measureText`、SVG `<text textLength>`）各有精度脆弱、强引起重排或打断文本流的缺点。
- **设计评审与决策（grilling & domain-modeling）**：
  1. **禁止在网格卡片（`ComicCard` / `DiscoveryCard`）全局滥用 `grow` / `shrink`**：
     - 书架首页以 12 本/批呈现，卡片阵列依赖一致的字阶（`--text-md`）与多行截断（`line-clamp-2`）来维持严整的视觉节奏与装订感；
     - 若卡片 A 因字短被放大到 24px、卡片 B 因字长缩小到 10px，会导致卡片网格韵律坍塌。
  2. **聚焦紧凑单行容器（ReaderTopBar / Meta ID Badge）**：
     - 在空间极度紧凑的单行场景（如阅读器顶栏 `.reader-title strong` / `span`、详情页元数据 `.meta-id` 紧凑徽章），长文本若能自动受限缩小，可有效减少因省略号产生的信息截断。
  3. **设立「字阶底线（Typography Floor）」防线**：
     - 缩放必须有底线（不低于 `--text-xs` / 12px），杜绝超长副标题缩成无法辨识的“蚂蚁字”；超限仍然遵循省略号截断。
  4. **零封装胶水、纯 CSS `@supports` 渐进增强**：
     - 拒绝封装多余的 Vue `<TextFit>` 组件或 JS 轮子，避免单一 CSS 属性带来的抽象泄漏与虚拟 DOM 开销；
     - 在 `src/styles/main.css` 沉淀 `.text-fit-shrink` 工具类，基线浏览器原生走 `text-overflow: ellipsis`，现代浏览器平滑享受 `text-fit: shrink consistent` 的自适应体验。
- **验证**：`vp check`（0 error / 0 warning）、单测全绿。

## 31. 纸间统一矢量图标集与组件分层架构（Impeccable 12345 规范落地）

- **背景与痛点**：
  1. 过去项目中混杂使用 Unicode 伪图标字符（如 `ToastStack` 的 `'✕'`/`'✓'`、`Modal` 的 `'×'`、`ReaderSettingsPanel` 的 `'关闭 ✕'`、`DetailActionBar` 与 `ChapterView` 的 `'⋯'`、`CoverCarousel` 的 `'←'`/`'→'`），在跨操作系统（Windows/macOS/iOS）渲染时存在字重撕裂、基线偏心及屏幕阅读器误读乘号等 a11y 缺陷；
  2. 多处组件手写重复的内联 `<svg>`（如 `FavoriteButton` 与 `TagFilterBar` 的心形、`ThemeSelect` 与 `AuthModal` 的勾选、`TagManager` 与 `ImageSearchChip` 的清除叉号、`ImportPanel` 的 info 提示），维护成本高且缺少统一规范。
- **Impeccable 12345 决策与分层架构**：
  1. **规划与发现（Shape）**：全面盘点全站 19 处散落 SVG 与 6 处字符伪图标；
  2. **方案与基调（Craft）**：拒绝引入外部大图标包，采用**三层组件化架构**（`src/components/icons/`）：
     - **底座 `BaseIcon.vue`**：封装 SVG 骨架（24px 视口网格、`size` 预设/自定义计算、1.8px 细线条描边、`aria-hidden="true"`、`currentColor` 继承）；
     - **原子层 `Icon*.vue`**：21 个纯净原子组件（`IconClose`, `IconHeart`, `IconSearch`, `IconCheck` 等，各 5~10 行），实现精准 Tree-shaking 与直观的 Vue DevTools 节点名称；
     - **动态分发层 `AppIcon.vue`**：彻底消灭模板内 20+ 个 `v-if/v-else-if` 分支，基于 `<component :is="ICON_MAP[name]" />` 达成 0 分支动态渲染，兼顾动态切换场景（如 Toast 与鉴权状态）；
     - **导出层 `index.ts` & `types.ts`**：强类型 `IconName` 与 `IconSize` 约束，支持按需解构导出。
  3. **评审与挑刺（Critique）**：彻底清除全站字符图标，消除字体回退导致的偏心抖动；
  4. **系统打磨（Polish）**：全站 18 个组件/视图 100% 收敛至 `<AppIcon>` 与原子图标，全站业务组件内联 SVG 完全归零；
  5. **适配与安全（Adapt）**：全仓 160 文件 `vp check` 零 warning/error，补齐 `AppIcon.spec.ts` 完整单测。
- **验证**：`vp check`（0 error / 0 warning）、单测全绿。

## 32. 现代浮层体系升级（HTML Popover + CSS Anchor + 容器回退检测与滑动动效）

- **背景与痛点**：
  1. 过去前端弹出交互缺乏统一基建：`Modal.vue` 独占一处，`ThemeSelect.vue` 与 `DetailActionBar.vue` 操作栏分别手写绝对定位与 `document.addEventListener('click')` 外部点击监听胶水；
  2. `Tooltip.vue` 虽有基础 Anchor Positioning，但未利用 Top-layer `popover="hint"`，且缺乏边界翻转时的箭头自适应；
  3. `SegmentedTabs.vue` 缺乏物理滑动指示质感，选项卡切换生硬。
- **Impeccable 12345 规范推进与落地**：
  1. **规划与发现（Shape）**：
     - 基于张鑫旭 5 篇前沿技术文章与 MDN 最新标准，确认三层正交原子浮层体系：`AppTooltip`（轻量提示）+ `AppPopover`（通用富浮层）+ `AppDropdown`（操作选单/选择器）；
     - 确立「渐进增强（Progressive Enhancement）」原则：优先拥抱 W3C 现代规范，不支持时利用 VueUse 与 CSS `@supports not` 平滑降级，坚决不引入重型第三方定位库；
     - 沉淀 [ADR 0004](./docs/adr/0004-modern-floating-system.md) 并更新 `CONTEXT.md` 领域术语表。
  2. **方案与基调（Craft）**：
     - **`AppTooltip.vue`**：结合 `popover="hint"` 与 CSS Anchor Positioning，引入 `container-type: anchored` + `@container anchored(fallback: flip-block)` 纯 CSS 感知视口边缘翻转自动对调指示小三角；
     - **`AppPopover.vue`**：基于 `popover="auto"` 原生 Top Layer（杜绝 `z-index` 竞争与父级 `overflow` 裁剪），结合 `anchor-name` / `position-anchor` / `position-try-fallbacks`，原生支持 Light Dismiss；
     - **`AppDropdown.vue`**：基于 `AppPopover` 封装完整键盘导航（上下箭头、Home、End、Enter、Esc、Tab 焦点流）、单选勾选标记、危险操作警示与分隔线；
     - **`SegmentedTabs.vue` 滑动跟随**：通过 `:style="{ anchorName: activeAnchorName }"` 动态为活动 Tab 绑定锚点名，外层伪元素借助 `position-anchor` 与 `transition: var(--duration-2) var(--ease-spring)` 达成纯 CSS 物理滑动胶囊动效。
  3. **评审与挑刺（Critique & Audit）**：
     - 审查 a11y 无障碍：补充 `role="tooltip"`、`role="listbox"`、`role="option"`、`aria-expanded`、`aria-controls` 与 `aria-describedby` 映射；
     - 防御 JSDOM 单测环境下 `scrollIntoView` 兼容性，采用安全链式调用 `activeEl?.scrollIntoView?.(...)`；
     - 审查 `popover="hint"` 与 `popover="auto"` 的层级互斥行为，确保轻提示展示绝不意外关闭已展开的下拉菜单。
  4. **系统打磨（Polish）**：
     - 全站浮层与气泡 100% 收敛到 `--paper-0`、`--line-strong`、`--shadow-2`、`--radius-2`，配合 `<AppIcon>` 矢量单源图标；
     - 消除 `ThemeSelect.vue` 中 420 行手写定位与事件监听，精简为基于 `AppDropdown` 的 60 行薄包装；
     - 重构 `DetailActionBar.vue` 中的「更多 ⋯」菜单，彻底删除分散的 `.more-pop` CSS 规则与 `onClickOutside` 监听。
  5. **响应式与无障碍（Adapt）**：
     - 移动端小屏下，操作项保持触控舒适度（`min-height: var(--control-sm/md)`，触控目标 ≥ 44px）；
     - `@media (prefers-reduced-motion: reduce)` 全面关闭位移与形变动画。
- **验证**：`vp check`（125 文件 0 error / 0 warning）、`ModernFloatingSystem.spec.ts` 与 `SegmentedTabs.spec.ts` 11 项精准单元测试全绿。

## 33. Tooltip 幽灵滚动条根除与 WCAG 1.4.13 悬停安全桥（Hover Bridge）

- **背景与痛点**：
  1. **幽灵滚动条（Phantom Scrollbar）**：HTML `popover="hint"` 在 Chromium 内核中默认继承 User-Agent 样式的 `overflow: auto`。当 CSS Anchor Positioning 与 `width: max-content` / `max-width` 结合折行时，行高微弱浮点误差（0.1px）会触发垂直滚动条，在短文本气泡右侧挤占空间并出现粗灰滑块；
  2. **指针脱靶无法移入气泡**：气泡写死了 `pointer-events: none` 阻断指针命中，且触发图标与气泡之间存在物理间距（`margin-bottom/top: var(--space-1-5)`），光标穿过空白间隙时触发了 `@mouseleave` 导致气泡瞬时销毁，违背了 WCAG 2.1 准则 1.4.13（Content on Hover or Focus - Hoverable 可悬停标准），用户无法划词选读。
- **架构决策与落地（Grilling & Domain Modeling）**：
  1. **彻底根治幽灵滚动条**：
     - 重置 UA 默认样式，显式声明 `overflow: visible; box-sizing: border-box;`；
     - 保留气泡尖角指示器（`::before` 负偏移外露），并补充 `overflow-wrap: anywhere; word-break: break-word;` 兜底超长字符。
  2. **WCAG 2.1 悬停安全桥（Hover Bridge）**：
     - 将 `pointer-events: none` 调整为 `auto`，允许气泡接受指针事件并支持划词复制；
     - 引入纯 CSS 悬停安全桥：利用 `.tooltip__tip::after` 透明伪元素向下/上/左/右延展 `var(--space-2)` 触控区，无缝填补物理间隙，配合 `@container anchored(fallback: flip-block)` 在视口翻转时自适应反向；
     - 状态平滑连通：气泡绑定 `@mouseenter="onTipEnter"` 与 `@mouseleave="onTipLeave"`，关闭缓冲延时由 60ms 提升至 150ms，光标从触发源滑入气泡时主动取消销毁定时器。
  3. **小三角指示器（Arrow）与对齐动态联动（Align Targeting）**：
     - 将箭头的位置与 `align` 参数解耦联动：`align="center"` 时居中（`left: 50%`），`align="end"` 时贴右（`right: 0.85rem; left: auto;`），`align="start"` 时贴左（`left: 0.85rem; right: auto;`）；
     - 彻底修复了过去因死锁 `left: 50%` 导致气泡大跨度偏移时箭头“指空”脱靶的视觉割裂 Bug；
     - 清理 `ImportPanel.vue` 中充裕空间下误用的 `align="end"`，恢复以 `(i)` 图标为视觉中心的优雅对称居中。
  4. **领域概念边界固化**：
     - 明确 Tooltip 专注于只读辅助说明与选词复制，复杂表单与交互面板严格由 `AppPopover` 承载，更新 `CONTEXT.md` 术语表。
- **验证**：`vp check` 0 error / 0 warning、`ModernFloatingSystem.spec.ts` 新增 WCAG 1.4.13 与箭头联动自动化单测 12/12 全绿。

## 34. 长页面通用回到顶部（Back to Top）与无障碍/视觉系统闭环

- **背景与痛点**：
  1. **深层浏览回顶成本高**：用户在书架首页或包含几十话章节的长详情页向下滚动数屏后，若想重新搜索、筛选或收录新本子，必须长时间连续滑动滚轮或触控上滑，缺乏秒级回到顶部的快捷通路；
  2. **过度工程化警惕**：曾探讨是否将搜索框和收录入口吸顶或做成复杂悬浮岛，经双轮 Grilling 审视，确认吸顶会严重挤占移动端阅览高度并破坏书架 Hero 统计与排版仪式感；轻量、纯粹的物理纸印「回到顶部」浮动按钮（FAB）是最小必要且心智成本最低的解决方案。
- **架构决策与落地（Impeccable & Grilling 决策）**：
  1. **状态驱动与性能**：
     - 采用 VueUse `useWindowScroll()` 响应式监听视口位置，设立 400px 阈值（略大于 Hero 统计区高度）；
     - 仅在滚过首屏操作区进入瀑布流卡片时，通过 Vue 原生 `<Transition name="back-to-top">` 触发微位移弹簧上浮淡入（`translateY(8px)` -> `0`，`--duration-2` + `--ease-spring`）。
  2. **物理装订与纸印美学**：
     - 44×44px 正圆形印章造型（`border-radius: 50%`），遵循 WCAG 2.1 触控底线；
     - 暖纸色基底（`var(--paper-1)`）配合墨线边框与微投影，Hover 触发朱砂色（`var(--accent)`）点缀与轻微上浮（`-2px`）；
     - 扩展 `src/components/icons/` 矢量单源字典，新增符合 24px 网格与细线描边的 `IconArrowUp.vue` 原子组件。
  3. **无障碍深度打磨（A 轨独立设计总监审查自愈）**：
     - **前庭障碍保护**：动态嗅探 `window.matchMedia('(prefers-reduced-motion: reduce)')`，在用户开启减弱动效偏好时自适应切换为瞬间回顶（`behavior: 'auto'`），避免长距离平滑滚动引发眩晕；
     - **键盘焦点平滑转移（Focus Dump 预防）**：当组件因滚回顶部 `v-if` 销毁前，主动将焦点转移至 `<main class="app-main" tabindex="-1">`，防止视障与键盘导航用户焦点坠入 `document.body` 迷航；
     - **Landmark 纯净化**：外层去除 `role="region"`，消除屏幕阅读器地标噪音，由内部 `<button aria-label="回到顶部">` 与 `AppTooltip` 声明式承载提示；
     - **移动端安全区避让**：使用 `calc(var(--space-6) + env(safe-area-inset-bottom, 0px))` 累加边距，并在小屏断点自适应缩紧，杜绝贴死手势条导致的误触。
  4. **全站布局挂载与排他**：
     - 挂载于 `App.vue`，作为全局长页面基础设施；
     - 通过 `route.name !== 'reader'` 在沉浸阅读器中天然隐藏，互不干扰；
     - 与 `ToastStack`（z-index 60）天然物理分层（BackToTop 采用 z-index 30），零多余响应式几何胶水。
- **验证**：`vp check`（130 文件 0 error / 0 warning）、`BackToTop.spec.ts` 6/6 全面单测通过（覆盖显隐阈值、默认平滑滚动、减弱动效 auto 降级、键盘焦点安全转移）、`detect:slop` 静态规约扫描 0 finding。

## 35. PWA 渐进式集成与设备离线存储面板（Grilling & Impeccable 闭环落地）

- **背景与诉求**：
  1. **渐进式离线能力（PWA）**：纸间定位于个人私有收藏夹，读者常在手机/平板/桌面离线翻阅。需要引入 Service Worker 离线预缓存与 PWA 独立安装能力；
  2. **离线膨胀与安全清理痛点**：高频看漫会导致客户端 CacheStorage 空间占用迅速增长（可能占几百 MB 到数 GB），用户需要清晰获知当前设备占用的真实体积，并能一键安全释放空间；
  3. **领域概念混淆风险**：必须严格区隔「客户端浏览器离线缓存（PWA CacheStorage）」与「服务端本地化磁盘数据（`backend/data/library/`）」，绝不允许清理操作误删服务器漫画资产。
- **架构决策与实现（Grilling Q1~Q5 拍板）**：
  1. **分级离线策略（Tiered Offline Caching）**：
     - 利用 `vite-plugin-pwa`（Workbox）构建统一离线流；
     - 静态资产（HTML/JS/CSS/WebP）预缓存（Stale-While-Revalidate）；
     - API 动态数据（书库列表、详情、发现）走 Network-First 避免脏数据；
     - 漫画原图与缩略图（`/pages/.../file`、`/thumbnail`）走 Cache-First，配置 `maxEntries: 1000, maxAgeSeconds: 30天` 进行 LRU 自动淘汰。
  2. **双层存储隔离与精密探测**：
     - 基于 `navigator.storage.estimate()` 毫秒级直接读取本 Origin 真实物理占用；
     - 细分探测 CacheStorage 中的漫画图片缓存张数与体积，清晰区分「纸间核心资产」与「漫画阅览缓存」；
     - 提供「清理阅览图片缓存」（保留核心 App Shell，释放设备存储）与「重置全部离线环境」两档操作。
  3. **顶栏独立印章微件 + 纸卷账单 Popover**：
     - 在 `AppHeader.vue` 右侧设置 `<StoragePopover />`，采用暖纸色、墨线细边框与朱砂强调；
     - 扩展 `src/components/icons/` 原子字典（`IconArchive.vue`, `IconTrash.vue`）；
     - 移动端自适应（小屏隐藏文字，保持 ≥ 44px 舒适触控区）。
- **A 轨独立设计总监 Critique 与 Polish 闭环**：
  1. **P1 缺陷修复（Toast 数值竞态）**：直接透传 `clearImageCache()` 返回的 `freedBytes` 格式化展示，彻底根治清理后读到 0 的 Bug；
  2. **P1 缺陷修复（高危破坏操作两步防线）**：为「重置全部离线环境」引入两步确认防线（`isConfirmingReset` + 5秒自动回滚 + 独立取消按钮），并将点击热区提升至 38px；
  3. **P1 缺陷修复（浮层指示箭头脱靶）**：在 `AppPopover.vue` 补齐 `.align-end::before` 与 `.align-center::before` 相对偏移规则，解决右对齐时箭头指空的问题；
  4. **P2 优化（顶栏语义防歧义）**：Badge 标识由混淆的「离线 12.4 MB」优化为具有明确设备边界的「设备 12.4 MB」（0 占用时为「设备就绪」），消除与「本地优先」的心智冲突；
  5. **P2 优化（消除小红点通知焦虑）**：剔除触发按钮常驻朱砂红点，保持阅览室静谧典雅；
  6. **P2 优化（3px 平直装订规范）**：刻度槽对齐全站 3px 纸印规范，修正规则文案为真实的「保留最新 1000 页面」。
- **B 轨机器扫描与代码审查专家（Code Review Expert）深度闭环**：
  - `pnpm detect:slop` 检出并消除进度条 `transition: width` 引起的布局重排（改为 GPU 硬件加速的 `transform: scaleX(...)` 与 `transform-origin: left`），复扫 0 缺陷；
  - **P1 逻辑修复（零页面缓存归零）**：修复在读者未缓存任何漫画页面时，因预缓存整体体量而错误扣除魔法数值计算出虚假缓存体积的缺陷，建立 `count === 0` 优先归零防线；
  - **P2 请求级穿透**：修复 Fetch API `cache: 'no-store'` 误置于 `headers` 导致请求级缓存穿透失效的问题，移至顶级 `RequestInit`；
  - **P2 防重入防护**：Composable 底层 `clearImageCache` 与 `resetAllStorage` 增加 `clearing.value` 防重入守卫；
  - **P3 极简精简与定时器闭环**：安全清除无消费者的 `lastCleanedTime` 冗余状态；在 Popover 重新打开时清除未完成的重置定时器。
- **PWA 规范与部署防线全量达标**：
  - 入口补齐 `<meta name="description">`，替换 WebP 为标准的 PNG 192px `apple-touch-icon` 与 Favicon 兼容降级；
  - 引入 `workbox-window` 与 `src/pwa.ts` 托管 SW 生命周期，开启每小时周期性静默更新探测与弱网安全容错；
  - 服务端 `SPAStaticFiles` 显式注册 `application/manifest+json` MIME 映射，并对关键入口（`/`、`index.html`、`sw.js`、`manifest.webmanifest`）施加严格 `Cache-Control: no-cache, no-store, must-revalidate` 防死锁防线；
- **全链路测试验收**：
  - `useOfflineStorage.spec.ts` 与 `StoragePopover.spec.ts` 12 项精准单测全绿（含防重入断言）；
  - `backend/test_spa_fallback.py` 增补针对 Cache-Control 标头与 MIME 类型的自动化断言，`pnpm test:py` 全链路通过；
  - `vp check` 全站 138 文件 0 warning / 0 error，`vp build` 生产打包成功产出包含 86 项预缓存清单、`sw.js` 与独立 `workbox-window` chunk。

## 36. 页面流转卡顿消除：意图预热与即时元数据占位（Grilling 决策落地）

- **背景与现象**：
  - 读者反馈从书架首页点击进入详情页有明显卡顿与僵直，从详情页点击进入阅读页也有类似延迟，但二次进入或阅读器内部翻页却极其丝滑；
  - 经 E2E 自动化性能测试精确度量：首次点击卡片至 URL 变更耗时达 706ms~900ms，详情页就绪耗时超 1000ms；
  - 接口排查排除后端慢（`GET /api/library/{source}/{source_id}` 耗时仅 13ms~17ms）；
  - 真实根因：
    1. **异步 Chunk 懒加载无预取**：Vue Router 必须先等几十个 JS 模块网络请求完成后才推进路由，UI 无反馈延迟 300ms；
    2. **View Transition 捕获纯灰骨架屏错位**：`startViewTransition` 捕获到新页面全灰骨架屏快照，接口数十毫秒返回后真实 DOM 暴力销毁骨架屏，造成视觉二次抽搐与掉帧；
    3. **为什么后面变好**：模块已在内存，`api.detail` 命中 `useMemoize` 缓存，阅读器内部翻页豁免了全屏 View Transition。
- **架构决策与极简落地（0 冗余抽象）**：
  1. **意图预热（Prefetch on Intent）**：
     - `ComicCard.vue` 与 `HtmlCanvasCard.vue` 在 `@pointerenter.once`、`@focusin.once` 与 `@touchstart.passive.once` 时静默并发预热 `ComicDetailView.vue` chunk 与 `api.detail` 接口（预填 `useMemoize` 内存）；
     - `DetailActionBar.vue` 在读者把光标移向「开始阅读」按钮时即时预热 `ReaderView.vue`；
     - `ComicDetailView.vue` 挂载完成后在后台静默预热目标阅读页的原图文件（`new Image().src = pageFileUrl(...)`）。
  2. **即时元数据占位（SWR Hero Placeholder）**：
     - `src/stores/library.ts` 导出 `createPlaceholderDetail(summary)` 纯函数，进入详情页时若已有书架 `LibrarySummary`，直接初始化 `detail` 并在首帧渲染真实 Hero 头部；
     - 浏览器 View Transition 精准捕获到真实标题与带有 `viewTransitionName: 'comic-cover-active'` 的封面，使 Shared Cover Morph 连贯平滑放大，彻底消灭纯灰骨架屏的突兀闪跳。
  3. **生产环境 E2E 防退化闭环**：
     - `playwright.config.ts` 增强支持 `process.env.E2E_BASE_URL`；
     - 沉淀 `e2e/tests/nav-perf.spec.ts` 性能防退化测试；打包产物（`http://localhost:8000`）实测：首次点击卡片 URL 变更耗时从 900ms 降至 318ms~415ms（降幅超 54%），详情页首帧呈现提速 44%~57%，无骨架屏闪跳。
- **验证**：
  - `vp check` 全站 181 文件格式校验通过、139 文件 0 error / 0 warning；
  - `vp test src/__tests__/ComicGrid.spec.ts src/__tests__/useCoverTransition.spec.ts` 5/5 全绿；
  - `vp build` 生产打包 1.77s 正常完成；
  - `E2E_BASE_URL=http://localhost:8000 pnpm ai-e2e:test e2e/tests/nav-perf.spec.ts` 生产链路 1/1 通过。

## 37. 画页重新装订（Re-binding）与重订保护（纸间主体语境收敛）

- **背景与主体语境对齐**：
  1. **远端源切片与瑕疵**：部分远端作品（如 JM616255）在来源站上传时即被物理截断或存在脏数据，无论如何重拉远端依然是切碎的图片；
  2. **馆长案头重订隐喻**：摒弃冷冰冰的 CMS 后台技术术语「手动替换页面图片」，统一收敛为契合纸间私人阅览室与案头书卷物理质感的**「重新装订…」**（与「自建工坊」、「增量追加」保持一致的典藏动作句式）；
  3. **双模操作体验对齐（对标自建工坊与增量追加）**：支持「网页多图上传」与「服务器本地路径扫描」，既可直接拖拽上传无损图，也可直接指向服务器上的拆帧/外接卷宗目录就地重订。
- **架构决策与极简落地（0 冗余抽象）**：
  1. **纯图片事务性原子交替（Staging & Atomic Swap）**：
     - 前端仅允许图片格式（JPG、PNG、WebP、AVIF 等），严禁 ZIP；
     - 后端将文件或服务器扫描图片写入 `.tmp_replace` 暂存区，逐一经由 PIL `Image.open().verify()` 进行完整性检验；只有全数合法时才原子切换至 `pages/` 目录，单张出错即刻清空暂存，原漫画数据 100% 毫发无损；
     - 自动按文件名自然升序重新映射为 `00001.webp` ~ `0000N.webp`，同步重算 `page_count` 并重建全套封面与缩略图。
  2. **重新装订保护（Re-bound Pages Protection）**：
     - 在 `album.json` 中标记 `custom_pages: true`；
     - 保留原始来源、车号、作者与标签，但在 `cache_all` 与 `_prefetch_worker` 中拦截远端下载覆盖；
     - `DetailActionBar.vue` 操作栏中将「缓存全部」置灰显示为「已保护（重新装订）」，提供明确安全感。
  3. **多章节动态感知**：
     - 单章节漫画直接整本全量重订；
     - 多章节漫画在弹窗内支持选择“仅重订指定章节（自动保持全局页码单调递增并重算后续章节偏移）”或“整部重新装订（抹除多话合并为单卷）”。
  4. **详情页极简交互收敛**：
     - 在 `DetailActionBar.vue` 的「更多 ⋯」菜单中提供「重新装订…」，唤起 `ReplacePagesModal.vue`（弹窗标题：重新装订画页）；
     - 采用 VueUse `useFileDialog` + `useDropZone` 零胶水实现；经 `pnpm detect:slop` 扫描排除边条等 AI 模板痕迹。
- **Impeccable UI 双轨审查与打磨（A/B 双轨 SOP 闭环）**：
  1. **A 轨（独立设计总监子代理评审）**：
     - 调用 `invoke_subagent` 独立审查，产出可用性评分 **20/40**（快照落盘至 `.impeccable/critique/2026-08-29T17-35-19Z__replace-pages.md`）；
     - 逼出 3 项关键 P1 缺陷：
       - **[P1] 假想 CSS Token 污染**：初版捏造了 7 个未定义变量（`--border-color`, `--text-color` 等），暗色模式边框与对比度劣化；
       - **[P1] Dropzone 键盘 a11y 断路**：纯 `div` 无 `role="button"` / `tabindex` 与 Enter/Space 响应，全键盘用户完全无法触发；
       - **[P1] 盲盒式黑盒覆盖与重复追加**：重复选择文件时发生静默追加堆叠，且缺少新旧页数直观对比；
     - 逼出 3 项 P2 缺陷：破坏性操作主按钮语义混淆、上传中表单未锁定、触控热区低于 44px。
  2. **B 轨（机器确定性规则扫描）**：
     - `pnpm detect:slop` 扫描拦截并消除了 side-tab 强调色边框反模式。
  3. **Polish 打磨落地**：
     - 彻底消除假想 Token，全量收敛到 `tokens.css` 原生语义变量（`--ink-0/1/2`, `--line`, `--paper-1/2`, `--radius-1/2`, `--duration-1`）；
     - 为 Dropzone 补齐 `role="button"`、`tabindex="0"`、`aria-label` 与回车/空格触发，图标换用物理装订典藏隐喻 `archive`；
     - 增加文件名与大小组合 Deduplicate 去重机制，并增补鲜明的 `原有 X 页 ➔ 新选 Y 页（增减比对）` 物理指示牌，首尾长文件名做单行文本截断；
     - 上传激活时对 Dropzone、Radio、Select、Cancel 加锁（`is-submitting`），多章节全量重置模式下操作按钮升级为 `danger` 警示态；
     - 勾选框 `.replace-ack` 增加 ≥44px 触控垫高，断点收敛至全站统一的 `681px`。
- **验证**：
  - `pnpm test:py`（`backend/test_replace_pages.py`）单章节、多章节与事务回滚单测全绿；
  - `vp test src/__tests__/ReplacePages.spec.ts` 3/3 单元测试全绿；
  - `pnpm detect:slop src/components/detail/ReplacePagesModal.vue` 0 finding（100% 洁净）；
  - `pnpm critique write replace-pages ...` 成功落盘评审快照；
  - `vp check` 全站 183 文件代码格式通过、141 文件 0 error / 0 warning。

## 38. 访客通行证派发与个性化数据隔离（访客簿模态框）

- **背景与主体语境对齐**：
  1. **废除单一静态访客码**：原 `COMIC_SHELF_GUEST_SECRET` 缺乏健壮性与生命周期管理，无法对单人进行准入控制与续期；
  2. **从抽屉到模态框的形态收敛（消灭系统割裂）**：
     - 初始尝试的右侧滑出抽屉带有浓烈的中后台 SaaS / 云控制台既视感，与全站典藏书房居中弹层的视觉心智严重割裂；
     - 依据用户决策，统一收敛至全站标准 `Modal.vue`（居中暖纸弹层 + 沉静暗室沉降 `var(--reader-scrim-strong)` + 水印），彻底达成设计语言单源闭环；
     - 结合 `SegmentedTabs.vue` 提供「现存名册 (N)」与「登记印发」分段选项卡，维持开阔专注的视界。
  3. **数据隔离与全局隐藏双轨并存**：
     - **个性化隔离（User-Isolated State）**：收藏红心（`favorite`）与跨端阅读进度（`reading_progress`）完全按用户隔离，馆长与各访客互不影响；
     - **全景隐藏（Hidden from Guest）**：馆长标记隐藏的本子对所有访客统一 404 不可见。
- **架构决策与极简落地（0 冗余抽象）**：
  1. **存储分层（SQLite WAL 驱动轻量动态状态）**：
     - 引入内置 `sqlite3` + WAL 模式（`backend/data/comic_shelf.db`），管理 `guest_passes`、`user_favorites`、`user_reading_progress`；
     - 漫画核心元数据与图包继续维持自包含 `album.json` + 目录结构，不破坏纸间「本地优先」不变量；
     - 启动时自动初始化表结构并平滑迁移既有 `album.json` 的馆长收藏数据至 `user_favorites`（`user_id = 'curator'`）。
  2. **阅读进度多端同步与防抖上报**：
     - 前端 `useLastRead.ts` 升级为「本地 LocalStorage 瞬时响应」+「服务端 SQLite 隔离存储」双轨；
     - 初始化时静默向后端获取服务端进度对齐；翻页时由 VueUse `useDebounceFn` 800ms 防抖静默上报服务端。
  3. **统一图标系统原子收敛**：
     - 基于 `BaseIcon.vue` 扩充 `IconUsers.vue`（访客名册）与 `IconCopy.vue`（口令/链接复制）；
     - 严禁模板内联 SVG 或假字符，注册至 `AppIcon`。
- **Impeccable UI 双轨审查与打磨（A/B 双轨 SOP 闭环）**：
  1. **A 轨（独立设计总监子代理评审）**：
     - 调用 `invoke_subagent` 针对 `GuestModal.vue` 独立审查，产出可用性评分 **24/40**（快照落盘至 `.impeccable/critique/2026-08-29T19-21-10Z__guest-modal.md`）；
     - 逼出 3 项关键 P1 缺陷：
       - **[P1] 双重滚动死锁陷阱**：列表内部曾硬编码 `max-height: 420px; overflow-y: auto;` 与 `Modal.vue` 的 `.modal-body` 产生双层嵌套滚动死锁；
       - **[P1] 触控人机工效与移动端折行挤压**：底栏按钮仅 32~36px，全量跌破 WCAG 2.5.5 与 Craft Floor 44px 底线，展开确认时底栏剧烈横向拉伸折断；
       - **[P1] 印发流心流阻断与状态孤岛**：登记印发成功后粗暴切回名册，打断立即复制链接发给朋友的直觉心流，也阻碍连续派发；
     - 逼出 2 项 P2 缺陷：异步防重入缺失与未校验假性复制反馈、WAI-ARIA `tabpanel` 语义断链。
  2. **B 轨（确定性规则扫描）**：
     - `pnpm detect:slop src/components/curator/GuestModal.vue` 扫描结果 0 缺陷。
  3. **Polish 打磨落地**：
     - **消灭嵌套滚动死锁**：彻底剔除 `.pass-card-list` 的 `max-height` 与 `overflow`，卡片列表在 `Modal.vue` 单源滚动画卷中自然流动；
     - **印发成功实体凭据卡（Issued Voucher）**：登记印发成功后不切页，原位升格为「印发成功凭据卡」，展示醒目的「一键复制免密直达链接」主按钮与口令，并提供「继续登记下一张」与「查看现存名册」双通道；
     - **触控热区与移动端适配**：增补 `@media (max-width: 640px)` 断点，所有触控目标拉升至 ≥40~44px，移动端将有效期与管理工具分两行网格化编排；
     - **防重入与剪贴板容错**：在 `useGuestPasses.ts` 引入 `operatingId` 锁，捕获复制异常并降级提示；
     - **典藏暗室沉降与印章语义纠偏**：统一继承 `Modal.vue` 的静谧暗室沉降（`var(--reader-scrim-strong)`）；生效期采用朱砂方印微质感（`〔 准入 · 剩 N 天 〕`），停用/过期采用沉静墨印（`var(--ink-2)`）；
     - **WAI-ARIA 规范对齐**：面板添加 `role="tabpanel"` 与 `aria-label`；清除硬编码 `#fff` 与字面量；
     - **分段选项卡吸顶（Sticky Tabs）**：`.tabs-nav-bar` 采用 `position: sticky; top: calc(-1 * var(--space-5))` 结合负边距与背景融合，在长名册滚动时持久固定在标题栏下方，无需回滚即可随时切换视窗；
     - **全域圆角严格收敛**：根除未定义变量，说明条（`.modal-notice`）、借书卡（`.pass-card`）、凭据卡（`.issued-voucher-card`）及表单（`.issue-form`）全面统一采用 `var(--radius-2)`（0.625rem），按钮与输入框统一采用 `var(--radius-1)`（0.375rem），达成 100% 视觉和谐一致；
     - **说明条蒸馏至标题栏 Tooltip 气泡**：`Modal.vue` 标题栏开放 `<slot name="title">`，彻底移除弹窗内部常驻占高 52px 的浅色说明框，将“派发专属通行证，进度与收藏隔离”收敛为标题旁典雅的 `info` 圆形触发点 + 现代轻量 `Tooltip`，彻底还给名册最纯净开阔的竖向视界；
     - **复制反馈典雅沉静微状态（Success Tone & Smooth Decay）**：复制口令或专属链接成功时，按钮就地切换至竹绿印泥质感（`color-mix(in oklab, var(--success) 45%, transparent)` 边框 + `8% var(--success)` 纸底色 + 墨绿字），并伴随图标切换为 `check`；经由 `var(--duration-2)` 缓动曲线在 1.5 秒后优雅平滑地淡出恢复，给用户精准确信感而无任何跳跃感；
     - **专家代码评审闭环加固（Code Review Expert Hardening）**：
       1. **多租户阅读进度强隔离**：`useLastRead.ts` 本地存储键引入 `userId` 命名空间（`comic-shelf:last-read:${uid}:${source}/${sourceId}`），且在拉取服务端进度时无条件对齐，彻底根治公用设备同浏览器跨用户阅读进度污染；
       2. **SQLite 连接安全释放**：`db.py` 中 `get_db()` 改造为 `@contextmanager`并在 `finally` 显式调用 `conn.close()`，彻底杜绝文件句柄累积与 WAL 库锁冲突；
       3. **口令冲突防御**：拦截 `sqlite3.IntegrityError` 并转换为 400 Bad Request（“该通行口令已存在，请更换口令”），对过期天数校验 `gt=0`，直达免密链接失效时由 `useToast` 给出明确引导。
- **验证**：
  - `pnpm test:py`（含 `test_db_and_passes.py`）后端全链路单元测试 100% 全绿；
  - `vp test src/__tests__/GuestPasses.spec.ts` 4/4 单元测试全绿；
  - `vp test src/__tests__/useAuth.spec.ts` 10/10 单元测试全绿（含免密直达自动登录与异常测试）；
  - `pnpm detect:slop src/components/curator/GuestModal.vue` 0 finding；
  - `pnpm critique write guest-modal ...` 评审快照已归档至 `.impeccable/critique/2026-08-29T19-21-10Z__guest-modal.md`；
  - `vp check` 全站 191 个文件代码格式通过、146 个文件 0 warning / 0 error；
  - `vp build` 生产打包 1.21s 成功完成。

## 39. 顶栏控件统一收敛、紧凑首屏与移动端即时渲染优化（Grilling 确认落地）

- **问题复盘**：
  1. **按钮高度撕裂**：顶栏右侧由「离线存储（`StoragePopover`）」、「访客簿（`guest-roster-btn`）」与「身份通行证（`auth-badge-btn`）」构成。此前在移动端分别写死 44px、36px 与自适应内容高（~28px），造成极其突兀的三级台阶撕裂；
  2. **移动端占位过大**：`LibraryHero` 在 `≤960px` 折叠为单列后保留全量宣传长文（`hero-lede`）、眉标与大字号标题，加上馆长收录面板（`ImportPanel`），在手机第一屏占据 >500px 高度，完全挤压了书架列表和检索区；
  3. **DevTools 切换机型样式延迟 / 需滚动才刷新**：
     - `AppHeader` 的横向滚动渐变羽化遮罩 `useScroll(navScrollEl)` 仅监听滚动事件，视口或容器尺寸变化时 `arrivedState` 未及时计算；
     - 顶栏毛玻璃合成层在 Chromium 部分版本下切换 Device Metrics 时未主动失效重绘脏矩形。
- **治理与设计落地**：
  1. **顶栏操作群（Header Control Group）高度与无障碍双标对齐**：
     - 桌面端：保留原本轻量典雅的徽章微尺寸（`padding: var(--space-1) var(--space-2)` + `line-height: 1.2`），高度维持在 ~26px 的轻巧纸签质感，杜绝粗笨高按键；
     - 移动端（`≤640px`）：三按钮统一步调收敛为 36px 正方形纯图标（`storage-label`、`guest-roster-label`、`auth-label` 无感隐退），利用 CSS `::before` 伪元素扩展至 44px 隐形触控热区（兼顾 WCAG 2.5.5 / iOS HIG 触控门禁与手机顶栏紧凑美感）；
  2. **紧凑首屏标语（Compact Hero Banner）**：
     - 在 `≤640px` 下隐藏眉标 `eyebrow` 与长句 `hero-lede`，标题字号收拢为单行 `1.25rem`；
     - 三项统计（藏书、已本地化、总藏量）平直内联为单行流动点缀，将 Hero 区域纵向占位由 >350px 压缩至 ~75px，首屏直达书库；
  3. **移动端收录折叠卡片（Collapsible Import Panel）**：
     - 馆长模式下的 `ImportPanel` 在移动端（`≤640px`）默认折叠为单行轻量条（`+ 收录新作品 / 本地图集` + 展开图标），点击顺滑展开完整输入与并发调节，平时绝不霸占第一屏；
  4. **视口尺寸动态重算与合成层防停滞**：
     - 在 `AppHeader.vue` 补充 VueUse `useResizeObserver` 与 `useEventListener('resize')`，视口/机型切换瞬间主动触发 `measure()` 同步滚动到达态，遮罩无需滚动即时呈现；
     - 显式声明 `@property --mask-left` 与 `@property --mask-right`，规范平滑插值；
     - 顶栏补充 `transform: translateZ(0)`，消除 Chromium DevTools 模拟机型切换时的图层光栅化延迟。
- **验证**：
  - `vp check` 0 lint error / 0 type error，代码格式 100% 通过；
  - `vp test src/__tests__/StoragePopover.spec.ts`、`App.spec.ts`、`GuestPasses.spec.ts`、`useAuth.spec.ts` 全部精准单测通过。

## 40. 访客通行证唯一使用、LRU 多设备漫游与防重发放预警（Impeccable & ADR 0007）

- **背景与问题**：
  1. **通行证无限制共享**：原访客码一旦泄露或群发，任何人均可无限制登入，缺少设备绑定与名额约束；
  2. **合法访客多端与漫游诉求**：访客日常需在手机、平板与电脑间流转，且通勤中频繁在 4G/5G 蜂窝与 Wi-Fi 间切换 IP，粗暴锁死 IP 会导致误杀踢出；
  3. **馆长重复发放困惑**：馆长难以分辨某张通行证是否已被朋友实际激活使用，复制时缺乏直观警示，容易造成同一张卡片误发多人引发设备互挤。
- **架构决策与领域建模（ADR 0007 & CONTEXT.md）**：
  1. **两层凭据流转机制**：
     - 口令凭据（Pass Token）：由馆长派发，仅在初次登入或打开专属直达链接时使用；
     - 设备凭据（Device Session Token）：服务端校验后，为当前物理端颁发专属持久化凭据（存储于 `guest_devices` 表并以 `comic_shelf_device` HttpOnly Cookie 返回）；
  2. **LRU 设备滑动窗口淘汰**：
     - 每张通行证配置设备席位配额（默认 2 台，支持 1~5 台微调）；
     - 当新设备登入且超过配额时，系统自动淘汰踢出最久未活跃（`last_active_at` 最小）的旧设备；合法号主换新机自愈无需沟通，非法群发扩散则导致号主自身设备被挤下线，形成内在自律制约；
  3. **IP 彻底解耦脱敏**：IP 变动 100% 无感放行，仅记录为审计字段供馆长名册排查。
- **UI 评审与工程落地（Impeccable 双轨闭环）**：
  1. **状态筛选胶囊（Filter Pills）**：
     - 名册顶部新增快速分类胶囊（全部 · 待激活 · 使用中 · 已满额 · 已失效），附带数量徽章；
     - 采用 WAI-ARIA `role="radiogroup"` 与 `role="radio"` 语义，馆长可一秒筛选出所有待激活卡片，杜绝重复赠予；
     - 头部新增轻量即时模糊搜索框，大名单秒级过滤；
  2. **典藏印章四态流转与语义纠偏**：
     - 待激活（`pending`）：淡雅草木灰印 `〔 待激活 · 0台占用 〕`；
     - 活跃中（`active`）：墨绿印 `〔 活跃 · N/M台 〕`（`--success` 纸本混色）；
     - 已满额（`full`）：琥珀古铜印 `〔 满额 · M/M台 〕`（`--warning`），彻底解除原先误用朱砂红导致的警报恐慌感；
     - 已失效（`disabled/expired`）：沉静墨印 `〔 已停用 〕` / `〔 已过期 〕`，移除现代删除线回归古籍质感；
  3. **物理设备抽屉与防误触踢除**：
     - 每张借书卡配备独立设备托盘，呈现每台设备的名称（根据 UA 解析系统与浏览器）、最后活跃相对时间与 IP；
     - 踢除动作（`device-kick-btn`）引入内联防误触微交互（点击后在芯片内部展开“下线？”、“踢出”与“取消”），辅以 `::before` 伪元素扩展至 40px 触控区，并声明完整 `aria-label`；
  4. **席位配额微调器（Quota Stepper）与零伪字符合规**：
     - 新增原子图标组件 `IconMinus.vue` 并纳入 `src/components/icons/` 单源字典；
     - 席位加减全面使用 `<AppIcon name="minus" size="xs" />` 与 `<AppIcon name="plus" size="xs" />`，彻底消灭硬编码 Unicode 伪字符；
     - 容器声明 `role="group"` 与 `aria-label="设备席位调整"`，内部由步进按钮承担明确的无障碍语义；
     - 优化 `updateMaxDevices` 消除冗余全量拉取，实现就地响应式更新；
  5. **防重发放轻量告警 Toast**：
     - 复制已有设备绑定的通行证口令或链接时，弹出琥珀色微提示 `⚠️ 口令已复制。该通行证已有 X 台设备在使用中，谨防设备互挤`；若为未激活卡片则提示 `可安心发放给新朋友`；
  6. **移动端响应式与暗室阴影收敛**：
     - 移动端（`≤640px`）底栏采用弹性自适应折行排版，彻底解决二次确认展开时宽度暴增撑破卡片的问题；
     - 硬编码 `rgba(0,0,0,0.04/0.05)` 阴影全量收敛至 `var(--shadow-1)`。
- **验证**：
  - `pnpm test:py` 后端单元测试全链路 100% 通过（含设备注册、LRU 自动淘汰、多态流转与单设备踢除测试）；
  - `vp test src/__tests__/GuestPasses.spec.ts` 前端单测 6/6 全绿；
  - `pnpm detect:slop src/components/curator/GuestModal.vue` 0 finding；
  - `pnpm critique write guest-modal-devices ...` 评审快照已归档至 `.impeccable/critique/2026-08-30T09-27-48Z__guest-modal-devices.md`；
  - `vp check` 全站 193 个文件代码格式校验通过、147 个文件 0 warning / 0 error。

## 41. 访客防滥用加固：置换熔断冷却锁、令牌桶限流与默认隐私隐藏（ADR 0008）

- **背景与威胁模型**：
  1. **恶性互挤攻击（DoS by LRU Thrashing）**：攻击者利用 LRU“后到者优先”置换逻辑，编写脚本伪造随机 UA 频繁触发登录，导致合法号主看书时秒级掉线并陷入死循环；
  2. **Token 泄露全库爬取（Bulk Scraping）**：单张通票被群发或截获后，爬虫携带有效 Cookie 并发抓取整站所有漫画图片，拉满 NAS 上行带宽与 CPU 并发；
  3. **私人藏书误暴露（Private Collection Leakage）**：馆长新导入私人藏书若未手动打上 `hidden_from_guest`，访客即可在书架直接看到。
- **架构决策与落地实现（ADR 0008 & backend/app/abuse.py）**：
  1. **置换频次熔断冷却锁（Eviction Cooling Lock）**：
     - 在纯内存滑动窗口记录每个 Pass 的置换事件（5 分钟 = 300 秒）；
     - 若 5 分钟内发生超过 3 次新设备置换，自动激活 10 分钟置换冷却锁；
     - 锁定期间：当前已在线合法设备 100% 正常阅读，新接入置换请求返回 HTTP `429 Too Many Requests`；
     - 馆长在名册点击「重置密钥」时，自动全量注销旧设备并清空冷却锁；
  2. **访客令牌桶正文阅读限流（120P/min + 45P 突发）**：
     - 在全局中间件中针对 `guest` 角色拦截正文二进制图片端点（`/file`, `/thumbnail`；书架封面 `/cover` 独立解耦免除限流，防止多书卡片并发渲染误伤）；
     - 限制单 Pass 速率为 120 页/分钟（2.0 tokens/s），提供 45 页瞬时突发桶（完美覆盖画集打开瞬时预取与急速滑屏寻页）；
     - 超额触发 HTTP 429（“阅读翻页速率异常（超过 120 页/分钟），请稍憩数秒”）；
  3. **新入库藏书默认隐身策略（Default Hide for New Imports）**：
     - 全局配置 `guest_hide_new_comics: bool` 持久化于 `data/settings.json`；
     - 在前端收录面板（`ImportPanel.vue`）提供轻量设置选项；
     - 开启后，远端收录与本地扫描导入的本子初始状态自动打上 `hidden_from_guest: true`，须由馆长核验满意后主动公开借阅，消除疏漏隐患；
  4. **馆长态势感知与一键熔断**：
     - 名册卡片支持呈现赤红色警示印章 `〔 ⚠️ 争抢锁定 〕` 或 `〔 ⚠️ 速率受限 〕`；
     - 设备抽屉顶部呈现异常说明条，提示馆长一键重置密钥强制踢出所有端。
- **验证**：
  - `pnpm test:py` 后端测试 100% 通过（包含 14: 熔断冷却锁、15: 令牌桶限流与 16: 隐私设置完整断言）；
  - `vp test src/__tests__/GuestPasses.spec.ts src/__tests__/useAuth.spec.ts` 16/16 单测全绿；
  - `pnpm detect:slop src/components/curator/GuestModal.vue src/components/ImportPanel.vue` 全部 0 finding；
  - `vp check` 195 个文件格式校验通过、147 个文件 0 warning / 0 error。

## 42. 访客借阅凭证卡（ReaderPassPopover）与特权入口去污染

- **背景与痛点**：
  在访客模式下，右上方徽章显示 `〔 访客阅览 〕`，悬停为“访客阅览中（点击解锁馆长权限）”，点击弹出解锁馆长口令的弹窗。这打破了“私人阅览室”的借阅隐喻，将管理特权入口直接暴露给读者，且读者在离开时缺乏主动交还借书卡释放当前设备席位的入口。
- **架构决策与落地实现（Impeccable 5 步 SOP）**：
  1. **特权入口去污染与纯净读者视角**：
     - 彻底从访客 UI 中抹除“解锁馆长权限”与“输入馆长密钥”字样，门禁口令弹窗（`AuthModal.vue`）收敛为单纯的“阅览室通行口令 / 请输入通行口令以进入”；
  2. **读者专属借阅印章（Reader Badge）**：
     - 顶栏为持证读者展示古典墨印风格 `〔 读者 · Alice 〕`，无用户名时自适应为 `〔 阅览室读者 〕`；
     - 严格遵守 `≤640px` 顶栏移动端规约，小屏下平滑收折文字，尺寸保持 `var(--control-sm)`（36px），通过 `::before` 垫高至 44px 触控标准；
  3. **借阅凭证卡浮层（ReaderPassPopover.vue）**：
     - 采用原生规范 `AppPopover`（`bottom-end` 带指示箭头）；
     - 呈现持证读者姓名、`〔 持证阅览 〕` 状态印章，以及专属书架就绪的定心提示；
  4. **防误触双列交还操作与设备席位释放**：
     - 常态按钮采用温雅的 `variant="secondary"` 纸本质感配 `IconLogOut.vue` 矢量图标，杜绝刺眼报警红底噪；
     - 点击就地展开纵向确认框，提示“交还后将释放本设备席位，后续仍可凭原口令随时入座”；
     - 确认操作区采用双列大按钮（高度 36px，间距 8px），消除小屏幕误触；
     - 严格 WAI-ARIA 无障碍与焦点管理：触发按钮声明 `:aria-expanded` 与 `aria-haspopup="dialog"`，展开确认时通过 `nextTick` 自动聚焦至「暂不交还」，取消时平滑还回焦点，彻底移除硬编码无提示的 5 秒超时计时器；
     - 点击确认后调用 `useAuth.logout()`，后端清理 Cookie 并自动在数据库中释放本台物理设备席位，弹出 Toast `已交还借阅凭证，设备席位已释放`，优雅回到封底门禁。
- **验证**：
  - `vp check` 198 个文件格式化通过、150 个源码文件 0 warning / 0 error；
  - `pnpm detect:slop src/components/ReaderPassPopover.vue` 0 finding；
  - `invoke_subagent` 独立设计总监完成可用性审计并落盘至 `.impeccable/critique/`；
  - `vp test src/__tests__/ReaderPassPopover.spec.ts src/__tests__/useAuth.spec.ts` 14/14 单测全绿。
