---
target: src/components/library/TagFilterBar.vue
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 2
timestamp: 2026-09-11T10-05-41Z
slug: src-components-library-tagfilterbar-vue
---

# 设计评审快照：TagFilterBar.vue（标签筛选工具栏与顶层气泡浮层）

## 评审元信息

- **目标组件**：`src/components/library/TagFilterBar.vue`
- **设计健康度评分**：**28 / 40**（等级：Good）
- **严重性缺陷统计**：P0: 0 项 · P1: 2 项 · P2: 2 项

---

## 1. Nielsen 10 项可用性启发式评分表

| #        | 启发式原则                                            | 得分 (0-4)  | 关键缺陷与设计检视                                                                                                                               |
| -------- | ----------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| 1        | 系统状态可见性 (Visibility of System Status)          | 3           | 展开浮层后按钮文案切为“收起标签”导致当前选中标签丢失；浮层头部未展示当前激活标签，并遮挡底栏提示                                                 |
| 2        | 系统与真实世界匹配 (Match System / Real World)        | 4           | 术语“只看喜欢”、“只看离线”、“在读/已读”与纸间私有书房隐喻高度契合                                                                                |
| 3        | 用户控制与自由度 (User Control and Freedom)           | 2           | **[P1 缺陷]** 浮层内部无“全部/清除筛选”紧急出口；点击已激活的“更多标签”按钮不会取消筛选而是重新展开弹窗                                          |
| 4        | 一致性与标准 (Consistency and Standards)              | 3           | 激活态“更多标签”外观为 AppChip 且标记 pressed，但点击行为是打开浮层而非状态反选；width 契约存在 34rem vs 32rem 隐形截断                          |
| 5        | 防错机制 (Error Prevention)                           | 3           | 阅读状态三态互斥杜绝了交集为空的白屏；但浮层内重复点击活动标签为静默取消并直接关闭弹窗，无任何操作警示                                           |
| 6        | 认知识别优于记忆回想 (Recognition Rather Than Recall) | 2           | 次级标签呈“选项之墙（The Wall of Options）”，海量标签无搜索过滤、无字母/拼音分组、当前激活标签在浮层内未置顶                                     |
| 7        | 灵活性与使用效率 (Flexibility and Efficiency)         | 2           | **[P1 缺陷]** 严重键盘无障碍与效率缺陷（WCAG 2.4.3）：Enter 选中标签关闭浮层后焦点直接掉落至 `document.body`；Tab 焦点未被 Trap 会穿透到底层卡片 |
| 8        | 审美与无干扰设计 (Aesthetic and Minimalist Design)    | 3           | 顶层浮层消除了书架网格推挤抖动，质感优秀；但外层面板与内部集群存在双重嵌套滚动条（Nested Scrollbars），指示小三角在横向翻转时脱节                |
| 9        | 容错与恢复 (Error Recovery)                           | 3           | 常驻状态下的“清除筛选”按钮存在，但浮层展开时被自身遮盖，浮层内缺乏快速重置恢复机制                                                               |
| 10       | 帮助与文档 (Help and Documentation)                   | 3           | 附带“正在查看标签”与“N 个次级标签”辅助元信息，缺少键盘快捷关闭（Esc）与操作引导提示                                                              |
| **总分** |                                                       | **28 / 40** | **Good**（基础良好，存在 2 项实质性 P1 缺陷，必须整改后方可交付）                                                                                |

---

## 2. 认知负荷核对（Cognitive Load Checklist）

- [x] **单点聚焦 (Single focus)**：筛选维度清晰解耦（喜欢/离线/状态/分类标签）。
- [ ] **信息分块 (Chunking)**：❌ 失败。外露 8 个高频标签符合预期，但浮层内部未分块，数十个次级标签一次性平铺（>4 visible options）。
- [x] **视觉编组 (Grouping)**：状态切换、喜欢切换与标签流有明确视觉分割线。
- [x] **层级清晰 (Visual hierarchy)**：高频在前、溢出收纳在后层次明确。
- [x] **单步决策 (One thing at a time)**：每次标签选择聚焦单一分类。
- [ ] **极简选择 (Minimal choices)**：❌ 失败。浮层内部面临 20~50+ 个并列选项的选择墙，缺乏认知梯级。
- [ ] **工作记忆 (Working memory)**：❌ 失败。浮层展开时原按钮文案变为“收起标签”，遮挡底层 note，用户需在心智中记忆刚才选了什么。
- [x] **渐进显露 (Progressive disclosure)**：采用高频外露 + 次级收拢的渐进显露机制。

---

## 3. 设计特征度诊断（Design Specificity Verdict）

- **LLM 评估**：纸间（Paper Room）定位于“本地优先的静谧个人漫画收藏夹”，追求“书房阅览室、卡片目录与朱砂印泥”的物理纸质质感。此次重构将过往在文档流中膨胀、推挤书架卡片网格的 `grid-template-rows` 废弃，改由基于 Top Layer 原生 Popover 的顶层气泡承载，方向完全契合 ADR 0014 与 DESIGN_NOTES §55 对 0-Reflow 和视口绝对静止的性能追求。然而，作为顶层浮层，其交互模式与键盘流转未完全成熟，存在“只管弹出、不管收敛”的断裂感。
- **确定性扫描**：
  - `detect.mjs --json`: 0 slop issues found (规范命名、Token 引用合规)。
  - `detect-perf.mjs`: 0 forced reflow / layout thrashing (无同步重排违规)。
- **视觉层级与端表现**：浮层渲染于 Top Layer，背景色与阴影契合 `--paper-0` 与 `--shadow-2`，但在无 CSS Anchor Positioning 降级环境下存在向右溢出视口的物理风险，指示小三角在右侧缺乏横向反转联动。

---

## 4. 总体印象（Overall Impression）

从“推挤文档流”向“顶层悬浮气泡”的跨越在性能和视觉稳定性上是一次重大升级，彻底消除了卡片跳跃与 144Hz 掉帧。然而，当前的实现只完成了“展示”这一半，在“海量标签时的操作闭环”、“键盘无障碍焦点流转（WCAG 2.4.3）”以及“次级浮层内的清空与检索”上留下了明显的体验硬伤，属于典型的“工程上优雅但交互深度未补齐”的半成品。

---

## 5. 优势亮点（What's Working）

1. **视口绝对静止与零重排（Zero Layout Shift）**：将次级标签从文档流抽离至原生 Top Layer，彻底拔除了书架卡片在展开时的剧烈下坠跳跃，兼顾了 60Hz~144Hz 屏下的极致平滑度。
2. **多维状态正交解耦（Orthogonal Dimension Clarity）**：分段胶囊（全部/在读/已读）收敛单选互斥，喜欢/离线作为独立偏好微件，前 8 标签直露，维度划分清晰明了。
3. **现代 CSS 特性渐进增强（Modern Standards Adoption）**：率先采用 HTML Popover API 与 CSS Anchor Positioning（`position-area`, `@starting-style`），并在降级模式下使用 VueUse `onClickOutside` 兜底。

---

## 6. 核心缺陷与改进清单（Priority Issues）

### [P1] 键盘焦点丢失与焦点归还断裂（Focus Drop to Body & Lack of Focus Restoration on Popover Close）

- **问题定义**：键盘用户按 Enter 选中浮层内的次级标签后，浮层立即关闭并 `display: none`。由于没有任何代码捕获并将焦点归还给触发器 `more-tags`，浏览器的活动焦点瞬间崩溃丢失并重置到 `document.body`。用户下次按 Tab 时将从整个网页最顶端的 Header 重新开始漫游，彻底打碎键盘交互连续性（严重违反 WCAG 2.1 2.4.3 准则）。
- **影响分析**：破坏读屏器（NVDA/VoiceOver）与键盘用户的操作流，导致用户迷失在 DOM 根节点。
- **落地修复方案**：
  1. 在 `onSelectOverflowTag` 或 `AppPopover` 关闭流程中引入 `nextTick(() => triggerButtonRef?.focus())` 显式焦点归还机制；
  2. 在浮层挂载时增加基础键盘焦点陷阱循环（Tab 循环或 Esc 逃生），阻止 Tab 穿透到浮层下方的卡片。
- **建议指令**：`$impeccable a11y` / `$impeccable harden`

### [P1] 溢出标签筛选与清空操作闭环断裂（Broken Filter/Clear Action Loop & Ambiguous Active Trigger）

- **问题定义**：当选中的标签是溢出标签时，外露的 `more-tags` 按钮呈现激活高亮状态（显示 `标签：xxx`）。此时用户本能期望点击它来“取消该标签筛选”（与常规 Chip 一致），但点击却强行弹出了次级浮层！而在弹出的浮层内部，既没有将选中的标签置顶，也没有任何“清空筛选”或“全部”按钮。用户必须在可能多达 30~50 个标签的“选择墙”中重新人工搜寻该标签才能取消，形成了极其挫败的操作死胡同（违反 Nielsen H3 与 H4）。
- **影响分析**：用户一旦在次级浮层中选中了标签，便陷入极难取消的困境，心智模型与主工具栏 Chip 严重割裂。
- **落地修复方案**：
  1. 在浮层头部 `.overflow-popover-header` 中，当 `isOverflowActive` 时增加显式的「清除已选」动作链接/按钮，点击后清除标签并顺畅关闭浮层；
  2. 浮层内将当前已选标签置于前排高亮展示，并带有清除印章；
  3. 外露的 `more-tags` 激活态胶囊支持点击后缀清除图标（`removable` 或独立 `×` 点击域）直接取消筛选。
- **建议指令**：`$impeccable clarify` / `$impeccable shape`

### [P2] 双重嵌套滚动条与浮层指示箭头脱节（Dual Nested Scroll Containers & Arrow Misalignment）

- **问题定义**：`AppPopover.vue` 面板已设置 `overflow-y: auto; max-height: min(80dvh, 36rem);`，而内部 `.overflow-cluster` 又设置了 `overflow-y: auto; max-height: min(50vh, 22rem);`，在矮屏幕笔记本或小视口下会出现两根平行的纵向滚动条，滚动轨迹链混乱。同时，小三角指引被固定在 `left: var(--space-4)`，当工具栏换行使触发按钮位于右侧时，箭头指向空气。
- **影响分析**：滚轮操作手感割裂，视觉引导出现虚指。
- **落地修复方案**：
  1. 移去外层面板的内滚与多余 padding（改用 `overflow: visible;` 保护小三角），由内部 `.overflow-cluster` 唯一负责内滚与边界；
  2. 参考 `Tooltip.vue` 为 Popover 增加横向碰撞时的箭头动态对齐。
- **建议指令**：`$impeccable polish` / `$impeccable layout`

### [P2] 海量标签缺乏检索梯级与小屏触控热区未达标（"The Wall of Options" & Sub-44px Mobile Tap Targets）

- **问题定义**：当次级标签超过 15 个时，平铺的 Chip 产生高认知负荷，用户难以迅速定位目标。此外在移动端屏幕（≤480px）下，Chip 触控高度不足 30px、间距仅 8px，违背项目 §2.3 规定的 ≥44×44px 移动触控安全底线。
- **影响分析**：移动端单手操作极易误触相邻标签，且一旦点错浮层自动关闭，挫败感倍增。
- **落地修复方案**：
  1. 在次级浮层头部增加轻量即时过滤输入框（当 `moreCount > 15` 时呈现）；
  2. 在移动端增加点按垫层或在 ≤480px 下使用底部抽屉形态展示次级标签。
- **建议指令**：`$impeccable adapt` / `$impeccable distill`

---

## 7. 典型用户角色走查（Persona Red Flags）

### Alex (Impatient Power User / 效率型用户)

- **走查路径**：纯键盘快速按 Tab 浏览书架分类，筛选次级标签“科幻”。
- **翻车红线 (Red Flags)**：
  - 打开浮层后面对 40 个次级标签没有过滤框，无法直接敲击字母定位；
  - 按 Enter 选定标签后浮层瞬间关闭，焦点直接掉进 `<body>` 虚空，Alex 必须从全站最顶部的 Header 重新按十几次 Tab 才能回到书架卡片，效率被严重腰斩。

### Sam (Accessibility-Dependent User / 读屏与无障碍用户)

- **走查路径**：通过 VoiceOver / NVDA 读屏与 Tab 键流转进行标签切换。
- **翻车红线 (Red Flags)**：
  - 浮层关闭瞬间没有任何焦点接管（Focus Restoration），读屏软件播报中断并跳回页面根节点；
  - 浮层展开时，Tab 键在到达最后一个次级标签后不会在浮层内循环，而是直接穿透到底层不可见区域，浮层面板依然浮在空中，构成严重的无障碍焦点陷阱/穿透。

### Casey (Distracted Mobile User / 移动端单手用户)

- **走查路径**：在拥挤地铁上单手握持手机翻阅书架，展开“更多标签”。
- **翻车红线 (Red Flags)**：
  - 浮层在 390px 视口下横向撑满，但内部标签触控高度不足 30px，单手大拇指极易误触临近标签；
  - 点错标签后浮层由于 `close?.()` 立即关闭，Casey 无法在浮层内撤回，必须再次点开气泡重新寻找，操作阻滞感强烈。

---

## 8. 次要体验细节观察（Minor Observations）

1. **尺寸契约截断隐患**：`TagFilterBar.vue` 传递给 `AppPopover` 的 `width="min(34rem, calc(100vw - 2rem))"` 超过了 `AppPopover.vue` 内部硬编码的 `max-width: 32rem`，导致 `34rem` 被无声裁切，暴露了组件契约与设计系统尺寸的不一致。
2. **事件冗余与孤立**：`TagFilterBar.vue` 的 `clearFilter` 函数同时派发了 `emit('selectTag', '')` 和 `emit('clearTag')`，但在父视图 `LibraryView.vue` 中仅监听了 `@select-tag`，`@clear-tag` 成为了无消费者的孤立契约。

---

## 9. 启发式重构设问（Questions to Consider）

- “当次级标签被激活时，触发按钮究竟是一个‘浮层开关’，还是一个‘可快速取消的标签胶囊’？”
- “如果一个书库拥有 80 个标签，纯靠气泡内平铺是否已经突破了 Popover 的承载极限，是否需要内嵌即时搜索过滤？”
- “在移动端小屏（≤480px）下，让气泡固定在触发器下方，还是像 §2.4 规范那样升格为底部贴边抽屉，哪种触控体验更平稳？”
