---
target: 拆分后的书架/详情/阅读器组件拆分评审
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 3
timestamp: 2026-08-18T18-17-57Z
slug: src-views-readerview-vue
---

---

target: 拆分后的书架/详情/阅读器组件
total_score: 29
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 3
timestamp: 2026-08-18T02-30-00Z
slug: src-views-readerview-vue
---

# Impeccable Critique — 纸间组件拆分后的全组件评审（拆分 → critique 基线）

Method: dual-agent (A: af746b68 · B: 92e771df)

Target: 拆分后的 ReaderView(reader/_) + ComicDetailView(detail/_) + LibraryView(library/*) + 相关既有组件
Live URL: http://127.0.0.1:5173 （拆分布局，未做浏览器注入）

## Design Health Score

| #         | Heuristic                       | Score     | Key Issue                                                                                                 |
| --------- | ------------------------------- | --------- | --------------------------------------------------------------------------------------------------------- |
| 1         | Visibility of System Status     | 3         | 缓存 %/轮询/骨架屏/阅读进度都有反馈；但 cacheAll 部分成功被标成 error toast，导入进度缺失                 |
| 2         | Match System / Real World       | 4         | 禁漫车/车号/本子等中文领域词自然，无 jargon                                                               |
| 3         | User Control and Freedom        | 3         | 到处可返回、Esc 可关、可恢复默认；移除本地无撤销、缓存无取消                                              |
| 4         | Consistency and Standards       | 3         | token 体系强，但 0.62rem/0.55rem/0.4rem/1.04rem 等硬编码漂移 + reader 子组件间重复 .reader-btn/.segmented |
| 5         | Error Prevention                | 2         | 导入有校验；但移除本地用原生 window.confirm，无内联危险确认/无撤销，缓存全部无护栏                        |
| 6         | Recognition Rather Than Recall  | 3         | 标签齐全、继续阅读第 N 页明确；阅读器 chrome 自动隐藏需要回忆 + 孤立 ☰ 开关                              |
| 7         | Flexibility and Efficiency      | 3         | 阅读器键盘完整（方向键/Home/End/f/Esc）；书架/详情无快捷键、无批量缓存/移除                               |
| 8         | Aesthetic and Minimalist Design | 3         | 干净且个性鲜明，但 5 个等权按钮、~20 个标签 chip、~17 个设置控件违反 ≤4 规则                              |
| 9         | Error Recovery                  | 3         | 图片重试、平实 toast、详情错误回书架；部分缓存误报 error、移除不可恢复                                    |
| 10        | Help and Documentation          | 2         | 空态与提示到位；阅读器方向键快捷键与自动切换语义无上下文说明                                              |
| **Total** |                                 | **29/40** | **Good**                                                                                                  |

## Design Specificity Verdict

**LLM assessment**: 高度"为这个产品而作"。英雄区文案、The stacks / Catalog card / End of book 的 eyebrow、deck-of-covers 3D 悬停、朱砂微强调 + 暖纸底、独立的"阅览室暗室"（--reader-* 深色环境、100dvh、safe-area、滚动裁切 chrome）——交互也具体：RTL 日漫流、每本一组的封面 deck、缓存比例是一等公民、"继续阅读 第 N 页"。无法换皮成通用相册/购物站。失分在微标签（0.62rem mono 角标）与少数通用按钮。

**Deterministic scan**: `detect.mjs --json` 对 10 个目标（views + library/detail/reader 目录 + ComicCard/CoverCarousel/MetadataPanel/ImportPanel/ThemeSelect + composables）返回 2 条 warning：`ComicCard.vue:221` `layout-transition`（cache-track 进度条 width 动画）、`ImportPanel.vue:147` `side-tab`（成功消息左绿边）。两处均为**有意为之的合理样式**，判定为 false positive；未发现硬编码色/token 违例等真实缺陷。

**Visual overlays**: 无浏览器注入，未投放 overlay。

## Overall Impression

拆分后结构干净、可维护性显著提升，设计特异性极强。最大机会：把"移除本地"从原生 confirm 升级为产品内的危险确认，并收敛多处硬编码微值——这两件事同时解决最刺眼的 craft 问题。

## What's Working

- **作者化的声音贯穿始终**：Read · Keep · Revisit / The stacks / catalog-card 元数据表 / deck 悬停 / 阅览室暗室，整体极具辨识度。
- **阅读器是真功夫**：键盘优先、scroll-timeline+JS 兜底、RTL、100dvh+safe-area、reduced-motion、content-visibility；自动隐藏 + 常驻进度 HUD 的阅读室交互成立。
- **token 纪律在组件层很强**：间距/颜色/圆角/动效基本全走 token；骨架屏 + aspect-ratio 防跳版；useReaderSettings 单一来源 localStorage 与 useLastRead 让拆分后 IA 干净。

## Priority Issues

- **[P1] "移除本地"用原生 window.confirm（ComicDetailView / DetailActionBar）**
  - Why: 最高风险动作没有任何产品内确认、无撤销、无后果强调；收藏者可能失去难以重新获取的本地缓存。
  - Fix: 在详情页内做内联危险确认（纸面 + 朱砂危险色 + 明确"不可撤销"文案），把移除列为独立危险动作。
  - Suggested command: $impeccable harden

- **[P1] token 漂移：多处硬编码微值破坏 4pt/字号体系（ComicCard 1.04rem/0.62rem/0.55rem、PageTile 0.62rem/0.4rem/0.12rem、CoverCarousel 0.62rem/0.55rem、AppHeader 1.05rem/0.65rem）**
  - Why: score-badge 配方（0.62rem mono 角标 @ 0.55rem 偏移）在至少 4 个组件里手写，卡片标题用脱轨 1.04rem；正是启发式 4/8 的系统性不一致。
  - Fix: 新增 caption/score 与 corner-pad token，四个组件全部接管；卡片标题上型量表。
  - Suggested command: $impeccable typeset

- **[P1] chrome/HUD 隐藏态仍可聚焦可点击；移动端 HUD 触控区 <44px（ReaderTopBar/ReaderHud [data-hidden] + control-xs；ReaderView chrome-toggle）**
  - Why: opacity-only 隐藏让键盘聚焦到"看不见的按钮"，可误触发；移动端 prev/next 缩到 32px；☰ 开关语义弱。
  - Fix: 隐藏时加 visibility:hidden(+transition-delay) + inert；移动端触控区保持 ≥44px；增强开关可发现性。
  - Suggested command: $impeccable harden

- **[P2] 详情操作栏 5 个等权动作，且两个"阅读"按钮重叠（DetailActionBar）**
  - Why: 最重要决策点给两个冗余阅读路径 + 三个无关动作同一层级，弱化主操作、埋掉危险操作。
  - Fix: 只留一个 dominant primary（继续阅读），从第 1 页降级/收进菜单，移除本地加明显示危险处理与间距。
  - Suggested command: $impeccable layout

- **[P2] 标签筛选墙（TagFilterBar / LibraryView slice(0,18)）**
  - Why: ~20 个 chip 同时可见，超出工作记忆上限；移动端成为超长换行条。
  - Fix: 可见 chip 限制 6–8 个，其余收进"更多标签"展开；或移到折叠行 + 渐隐。
  - Suggested command: $impeccable distill

## Persona Red Flags

**Alex（Power User）**: 无批量缓存/移除（收藏夹按 cache-ratio/喜欢筛选，天然要 batch）；书架无 `/` 聚焦搜索、详情无快捷键继续读；5 按钮平铺让他要在两个读入口里做多余选择；cache-all 部分成功误标 error 更刺眼。

**Sam（Accessibility-Dependent）**: 阅读器隐藏的 chrome 仍可聚焦（opacity-0 未 inert），Tab 会落在不可见的返回/设置/全屏/HUD 按钮上；主按钮白字对朱砂约 4.42:1 略低于 WCAG AA 正文标准；迷你角标 0.62rem 在照片上的 scrim 对比临界。

**Casey（Distracted Mobile User）**: 移动端 HUD 翻页按钮缩到 32px 触控未达标且在拇指区易误触；chrome 自动隐藏让他中途找不到控制，恢复要点顶部的小 ☰；标签筛选 ~20 chip 在低注意场景形成长条干扰；hero 里"缓存全部 600P"无中途进度不可取消。

## Minor Observations

- cacheAll 部分成功用 `toast(..., 'error')` 上抛——语义错位（progress 而非 failure）。
- window.confirm 文案带书名号但无产品内引导/严重度。
- LibraryView watch(store.error) 可能与逐次调用 toast 重复弹。
- ReaderSettingsPanel 重复 .reader-btn/.segmented，已是漂移隐患。
- PageTile `0.12rem 0.4rem`、`top:0.4rem` 不在 4pt 上。
- hero-stats 内侧 gap `0.1rem` 脱标。
- 卡片正文层级偏平：title 1.04rem 与 meta/tags 权重接近。
- experiment-bar（HTML-in-Canvas 开关）在书架首屏多了一个非核心控制面。

## Questions to Consider

- 详情页是否只留一个 hero 动作"继续阅读"，其余全部降级为次要/菜单？
- 缓存全部这个长任务是否该可取消、可断点恢复、可离线补齐；移除是否需要"软归档"（本地优先的本分）？
- 标签筛选到底是"浏览书架"还是"精确找书"？搜索驱动的标签下拉是否比 chip 墙更好？
- 阅读器自动隐藏时，是否只保留进度 HUD 这一个常驻控件，其余全藏？
- "移除本地"是否应明说"远端原始件仍在，本地缓存会丢失"，把后果与产品价值讲清？
