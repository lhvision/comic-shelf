# Spec — 书架 / 详情 / 阅读器组件拆分（paper-room-component-split）

> 领域词汇遵循根目录 `CONTEXT.md`；本 spec 不含具体文件路径/代码片段，
> 只描述本子、收录、本地化、阅读器等领域行为与已确证的结构决策。

## Problem Statement

纸间目前书架、详情、阅读器三个页面把**编排逻辑 + 展示结构 + 状态持久化**全部
堆在三个巨型视图文件里：阅读器视图仅脚本层就近 500 行且承载十余种职责
（设置、自动切换、滚动定位、键盘、全屏、预载、进度）；三个页面共享的设置与
"上次读到哪里"用原始 `localStorage` + 手写 `setInterval`/`matchMedia` 样板完成。
任何一处小改动都会牵扯整段逻辑，UI 打磨也无从下手——设计评审暴露的问题
（硬编码微值漂移、隐藏控件仍可聚焦、触控命中过小）难以定位到单一组件。

## Solution

把三个页面按下述职责边界拆成一系列带注释的小组件，并用 VueUse 组合式函数
替代手写浏览器样板：阅读器设置与"继续阅读"位置收敛到两个共享 composable，
页面只保留"编排"这一种职责；随后对拆分结果跑专业设计评审，把评审出的
P1 问题（隐藏态可聚焦、移动端触控命中 <44px、若干 hardcode 微值脱离 token）
一次性修掉。

## User Stories

1. 作为浏览器端使用者，我想在打开阅读器时上次的设置（模式/每屏页数/自动切换/方向/适配）仍然生效，
   这样我不必每次重设。
2. 作为浏览器端使用者，我想在详情页看到"继续阅读 · 第 N 页"直达上次位置，
   这样我能从上次中断处无缝续读。
3. 作为浏览器端使用者，我想阅读器的工具栏和底部 HUD 在闲置时自动隐藏、
   且隐藏后不会被误聚焦/误点击，这样既沉浸又不会误触。
4. 作为移动端使用者，我想阅读器底部翻页按钮与倒计时的触控区不小于 44px，
   这样用拇指也能可靠命中。
5. 作为手机使用者，我想阅读器顶栏/设置面板在窄屏下不溢出、可完整操作。
6. 作为视觉敏感用户，我希望能看到书架/详情/阅读器三处的角标字号、间距遵循同一套 token，
   这样整体更规整、不像"各写各的"。
7. 作为维护者，我想页面视图只做数据加载与流程编排，展示块拆成独立组件并可注释，
   这样定位与修改单一职责更快。
8. 作为维护者，我想设置持久化走 `createGlobalState` + `useLocalStorage` 的单例，
   面板与主视图天然共享同一份设置，不再手写 raw JSON 读写。
9. 作为维护者，我想"上次读到第几页"由 `useLastRead(source, sourceId)` 统一提供读写，
   这样详情页与阅读器不会各写各的 key。

## Implementation Decisions

- **阅读器设置模型**：`useReaderSettings` 组合式函数，`createGlobalState` 提升为模块级
  单例；`useLocalStorage` 持久化，**key 固定为 `comic-shelf:reader-settings:v1`**（兼容
  已存用户设置，永不悄悄改名）；`useMediaQuery('(min-width: 681px)')` 判定窄屏；
  读取时归一化（枚举合法值回溯默认、窄屏把 `pagesPerView 4 → 2`）。已落
  `docs/adr/0001-reader-settings-global-state.md`。
- **上次读到位置**：`useLastRead`，key 形如 `comic-shelf:last-read:<source>/<sourceId>`，
  由 source/sourceId 动态生成，详情页读、阅读器写。
- **组件目录约定**：页面级分区 `reader/`、`detail/`、`library/` 子目录存放页面专属
  展示件；复用型控件（卡片、封面轮播、元数据面板、导入面板、选择器）保留在
  `src/components/` 根目录。
- **阅读器拆分点**：顶栏（返回/书名/设置/全屏）、设置面板（模式/页数/自动切换/方向/
  适配，直接读取全局设置单例）、底部 HUD（倒计时 + 页码指示器）、进度条（父级喂
  `progress`/`invert` 数值，组件内部写 transform 并保留 scroll-timeline 增强）、结尾卡。
  滚动定位的 math、吸附、横向滚轮映射**保留在 ReaderView**（不映射现成 composable）。
- **自动切换计时**：`useIntervalFn`（1000ms，非 immediate）承载秒级 tick，
  `useTimeoutFn`（2600ms）承载工具栏自动隐藏，`useDocumentVisibility` 驱动前后台暂停，
  `usePreferredReducedMotion` 决定自动翻页是否平滑滚动。
- **详情拆分点**：操作栏（阅读/缓存/刷新/移除 + 缓存进度条）、页码索引整段（标题 +
  计数 + 缩略图网格 + `useIntersectionObserver` 哨兵增量加载，步长 48）。
- **书架拆分点**：hero（品牌文案 + 三项统计 + 收录面板 slot）、标签筛选条（只看喜欢 +
  标签 chips + 当前筛选提示）、卡片网格（骨架屏 / DOM 或 Canvas 卡片 / 空态）。
  HTML-in-Canvas 实验路径**原样保留**，ComicGrid 通过 `useCanvas` 条件渲染两条路径。
- **筛选状态归属**：书架搜索/标签/排序/只看喜欢仍由 LibraryView 持有，子组件 props +
  emits 双向；不新增 Pinia store。
- **设计 token 增补（polish）**：加入 `--text-caption`（角标/徽章专用极小字阶）与
  `--space-0-5`，把 ComicCard/PageTile/CoverCarousel/AppHeader/HtmlCanvasCard 等处
  分散的 `0.55rem`/`0.62rem`/`1.04rem` 等 hardcode 全部收敛到 token。
- **阅读器无障碍（adapt 产物）**：Chrome/HUD 隐藏时加 `inert` + `visibility:hidden`
  （保留渐隐），移动端 HUD 触控区统一 44px（`--control-md`）。

## Testing Decisions

- **好的测试判据**：只测外部可见行为（能渲染、能在设置面板改模式并持久化、
  隐藏态不可聚焦），不测内部实现细节（不断言 composable 内部字段）。
- **测试的缝（seam）**：现有缝优先——`src/__tests__/App.spec.ts` 挂载整 App；
  组件级 `@vue/test-utils` 是项目已有模式。本轮拆分未新增测试文件
  （符合 AGENTS「不为拆而拆测」约定），跑 `App.spec.ts` + `vp check` 兜底。
- **结构回归**：`vp type-check` 覆盖所有 `.vue`，`noUncheckedIndexedAccess`
  捕获越界索引（拆分后新增组件均通过）。

## Out of Scope

- **新建/修改测试文件**：本次以拆分为主，不新增测试；改动不涉及测试文件则不再跑测试。
- **批量缓存/批量移除**、详情/书架快捷键（评审的 P2/P3 建议，转 ticket，不在此实现）。
- **"移除本地"从原生 `window.confirm` 升级为产品内确认框**：属于 harden，不在 split 范围，
  已列入将来票据。
- **标签筛选墙折叠 / hero 缓存全部可取消**：设计评审给出的 P2 建议，不在本次拆分范围。
- **HTML-in-Canvas 实验**：保留现状，不做清理或增强。

## Further Notes

- 评审基线：拆分后全组件 critique **29/40**（Good），较旧阅读器报告
  （31 → 32）回落是**口径差异**（本轮覆盖三页全部组件而非单页新增功能），
  非回归；趋势已持久化至 `.impeccable/critique/`。
- 本轮落地即打磨：critique 的 P1（隐藏态可聚焦、移动端触控 <44px）与 token 漂移
  已在 polish/adapt 一并修复。剩余 P2/P3（操作栏 5 按钮层级、标签墙、原生 confirm、
  部分成功 toast 误标 error）列入后续票据。
