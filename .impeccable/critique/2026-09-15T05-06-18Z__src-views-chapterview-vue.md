---
target: src/views/ChapterView.vue
total_score: 28
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 3
timestamp: 2026-09-15T05-06-18Z
slug: src-views-chapterview-vue
---

# 设计评审快照：ChapterView.vue & ChapterSwitcher.vue（章节子路由详情与移动端适配）

## 评审元信息

- **目标组件**：`src/views/ChapterView.vue` 及 `src/components/detail/ChapterSwitcher.vue`
- **设计健康度评分**：**28 / 40**（等级：Good · 70%）
- **严重性缺陷统计**：P0: 0 项 · P1: 3 项 · P2: 2 项

---

## 1. Nielsen 10 项可用性启发式评分表

| #        | 启发式原则                                            | 得分 (0-4)  | 关键缺陷与设计检视                                                                                                                                                                                                                            |
| -------- | ----------------------------------------------------- | ----------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | 系统状态可见性 (Visibility of System Status)          | 3           | `CacheProgress` 提供了优秀的百分比与呼吸微动效；但当本话全部缓存完毕后，“缓存本话”按钮静默消失，缺少直观的“已就绪”印记确认；切话时若网络缓慢缺少过渡指示。                                                                                    |
| 2        | 系统与真实世界匹配 (Match System / Real World)        | 3           | “第 X 話”、“重新装订”等隐喻贴合图书收藏，但元数据栏出现“第 1–24 全局页”等底层数据库拍平术语，破坏了阅览室书卷氛围。                                                                                                                           |
| 3        | 用户控制与自由度 (User Control and Freedom)           | 3           | 面包屑返回与相邻话次切换流畅，二次删除确认严谨；但单话作品仍强制渲染上一话/下一话容器，缺乏自适应隐退。                                                                                                                                       |
| 4        | 一致性与标准 (Consistency and Standards)              | 2           | **[P1 缺陷]** 触控标准严重不一致：父级 `ChapterView` 针对移动端严格守住 44px（`min-height: 2.75rem`），子组件 `ChapterSwitcher` 却在移动端缩至 36px（`var(--control-sm)`）；此外桌面端“编辑章节”按钮与 `...` 下拉菜单中的“修改本话名称”重复。 |
| 5        | 防错机制 (Error Prevention)                           | 3           | 破坏性删除章节具备勾选框双重门禁；URL 传入无效 chapterId 时直接 replace 回本子页，但缺少明确的 Toast 提示。                                                                                                                                   |
| 6        | 认知识别优于记忆回想 (Recognition Rather Than Recall) | 3           | 章节指示器标明当前话序与页数并支持几何自动居中；但在小屏幕上章节标题被粗暴截断为 `max-width: 7rem`，长标题关键信息丢失。                                                                                                                      |
| 7        | 灵活性与使用效率 (Flexibility and Efficiency)         | 3           | `ChapterSwitcher` 支持 Left/Right/Home/End 键盘导航极佳；但视图顶层缺乏页面级翻话快捷键（如 `[` / `]`）。                                                                                                                                     |
| 8        | 审美与无干扰设计 (Aesthetic and Minimalist Design)    | 2           | **[P1 缺陷]** 移动端分页栏布局拓扑倒错：两个 50% 宽度的巨大翻页键骑在横向滚动画卷上方，横向滚动条又被卡片内边距局限并提前羽化截断；单话作品展示两个置灰禁用的幽灵翻页键。                                                                     |
| 9        | 容错与恢复 (Error Recovery)                           | 3           | API 异常通过 Toast 捕获并回退；离线状态下管理按钮静默隐藏，但未提供离线模式下的操作禁用说明。                                                                                                                                                 |
| 10       | 帮助与文档 (Help and Documentation)                   | 3           | 按钮拥有完整的 `title` 与 `aria-label`；删除弹窗提供详尽的页码重排影响说明。                                                                                                                                                                  |
| **总分** |                                                       | **28 / 40** | **Good**（评分 70%，基线稳固，但存在 3 项实质性 P1 缺陷，必须在交付前修复）                                                                                                                                                                   |

---

## 2. 认知负荷核对（Cognitive Load Checklist）

- [x] **单点聚焦 (Single focus)**：核心任务是查看本话页面索引并直达阅读，未受无关信息干扰。
- [x] **信息分块 (Chunking)**：头部信息卡片与底部缩略图网格分块明晰。
- [x] **视觉编组 (Grouping)**：状态、标题、操作、分页各行其道，秩序感良好。
- [ ] **层级清晰 (Visual hierarchy)**：❌ **未通过**。头部在 80px 高度内三次出现“第 X 話”序号；移动端两颗翻页大按钮视觉权重过大，喧宾夺主。
- [ ] **单步决策 (One thing at a time)**：❌ **未通过**。桌面端操作区并排出现“编辑章节”独立按钮与包含“修改本话名称…”的更多下拉菜单，造成冗余决策。
- [x] **极简选择 (Minimal choices)**：核心操作主要收敛为“阅读本话”与“缓存”，分支操作收敛进更多菜单。
- [x] **工作记忆 (Working memory)**：自动延续阅读进度（“继续阅读 · 第 X 页”），无需读者记忆上次停留在何处。
- [ ] **渐进显露 (Progressive disclosure)**：❌ **未通过**。单章节作品未隐退分页体系，强制暴露完全禁用的上一话/下一话控件。

**认知负荷诊断**：共 3 项未通过，处于**中度认知负荷（Moderate）**区间，移动端视线跳跃与桌面端冗余操作需重点消减。

---

## 3. 设计特征度诊断（Design Specificity Verdict）

- **LLM 评估**：纸间（Paper Room）定位于“本地优先的静谧个人漫画收藏夹”，隐喻为“私人阅览室、卡片目录与朱砂印泥”。`ChapterView.vue` 与 `ChapterSwitcher.vue` 的设计初衷极佳——摒弃了传统无尽滚动的卡顿，采用横向章节滚动画卷与几何中心动态对齐，体现了纸间克制、严谨、书籍式的质感。然而在移动端响应式落地上，代码出现了向“模板化组件随意拼凑”的退化：移动端为了折行而粗暴让翻页键各占 50% 顶置，把核心章节卷轴挤在下方；同时 `ChapterSwitcher` 触控尺寸被削减至 36px，打破了全站 44px 的物理底线。
- **确定性扫描**：
  - `pnpm detect:slop`: 0 slop issues found（0 渐变、0 毛玻璃、0 伪字符、Token 引用合规）。
  - `pnpm detect:perf`: 0 forced reflow / layout thrashing（滚动居中使用 `useScroll` 纯几何计算，无挂载期无差别重排）。
- **视觉层级与移动端实况**：在 `<=680px` 窄屏下，`.chapter-switcher` 作为子组件未能冲破父级 `.chapter-head` 的 `var(--space-3-5)` (14px) 内边距，配合自身的动态边缘 `mask-image`，在卡片内部左右各内缩 38px 就提前虚化截断，形成极其局促的“盒中盒”内陷感，完全丧失了全幅画卷通栏滑动的延展感。

---

## 4. 总体印象（Overall Impression）

架构逻辑清晰，状态驱动健全，桌面端观感典雅温润。但在「移动端触控尺度」、「小屏空间编排拓扑」以及「单章节作品的边缘纯净度」三个关键环节存在明显的工程糙点，属于典型的“桌面端精修、移动端仅做简单折行拼凑”的半程状态。

---

## 5. 优势亮点（What's Working）

1. **阅读进度的智能感知与情境化文案**：`useChapterPageInfo` 精准联动全局进度与本章起始页，阅读按钮动态呈现“开始阅读本话”或“继续阅读 · 第 X 页”，并附带直达 URL，提供了极其丝滑的阅读连贯感。
2. **章节切换器的几何物理居中与无感首屏直达**：`ChapterSwitcher` 区分了首屏直达（`behavior: 'auto'`）与交互切话（`behavior: 'smooth'`），配合 `useResizeObserver` 实现容器尺寸自愈，杜绝了页面挂载时的长距离动画眩晕。
3. **破坏性操作的极致防护与单调重排警示**：删除章节弹窗明确列出影响的画页数量（“共 X 页”）、缩略图以及“后续章节序号自动单调重排”的后果，强制勾选确认，完全契合 DESIGN_NOTES §12 铁律。

---

## 6. 核心缺陷与改进清单（Priority Issues）

### [P1] 移动端触控热区穿底违规（ChapterSwitcher 移动端 36px 击穿 44px 触控底线）

- **问题定义**：在 `src/components/detail/ChapterSwitcher.vue:328` 中，移动端媒体查询（`@media (max-width: 680px)`）将 `.chapter-switcher button` 显式设置为 `min-height: var(--control-sm);`（`2.25rem` = 36px），水平间距仅为 `var(--space-2)` (8px)。
- **危害分析**：直接违背项目核心红线（DESIGN_NOTES §2.3 规定「移动端与平板触控热区严格保证 ≥ 44×44px」）与 WCAG 2.5.5 无障碍准则。在同一页面中，`ChapterView` 自身的按钮都特化为 44px，唯独最具滑动交互频率的章节胶囊跌破底线。移动端读者在单手握持时，大拇指划动或点按极易误触相邻章节。
- **具象修复方案**：
  在 `ChapterSwitcher.vue` 移动端媒体查询中，将按钮高度规范为 `min-height: var(--control-md);` (44px / 2.75rem)，并微调内边距与字体排版，确保触控盒严格满足 44px。
- **建议指令**：`$impeccable adapt` / `$impeccable polish`

### [P1] 移动端分页器空间拓扑倒错与滚动渐隐遮罩内陷畸变（Pager Spatial Disorientation & Clipped Masking）

- **问题定义**：
  1. 在 `<=680px` 移动视口下，`ChapterView.vue:616-632` 采用 `flex-wrap: wrap`，将「上一话」与「下一话」两个大按钮拉伸至各占 50% 宽度霸占顶行，而将代表线性阅读时间线的 `ChapterSwitcher` 加上 `order: 3; width: 100%` 甩在最底部；
  2. `ChapterSwitcher` 在 `inPager` 模式下受父容器 `padding: var(--space-3-5)` (14px) 的钳制，加上其内建的 `mask-image` 在左右 24px 处羽化，导致横向滚动栏在手机屏幕内侧内缩近 40px 就截断消失，形成狭窄断裂的视觉效果。
- **危害分析**：视线流向从“标题 → 翻页键 → 章节条 → 页面网格”反复跳跃，违背真实图书目录的线性心智；内陷的遮罩让界面呈现出粗糙的未完工感。
- **具象修复方案**：
  1. 重塑移动端 `.chapter-pager` 布局：保持章节条在中间，翻页按钮以紧凑且具备 44px 触控热区的形态协同，或使章节胶囊条自然通排；
  2. 移动端给 `ChapterSwitcher` 赋予负外边距（如 `margin-inline: calc(-1 * var(--space-3-5))`），让横向画卷在手机屏幕两端真正实现通边全宽滚动，动态遮罩贴紧视口边缘平滑渐隐。
- **建议指令**：`$impeccable layout` / `$impeccable adapt`

### [P1] 单章节作品的幽灵分页栏与无效禁用态认知噪音（Single-Chapter Ghost Pager Clutter）

- **问题定义**：在 `ChapterView.vue:253-286` 中，当作品为单章节（`chapters.length <= 1`）时，`ChapterSwitcher` 内部因 `v-if="chapterList.length > 1"` 自行隐藏，但父级 `<div class="chapter-pager">` 依然无条件渲染，展示整条分割线以及两个完全 disabled 的「上一话」与「下一话」按钮。
- **危害分析**：违背 Nielsen #8（极简设计）与认知负荷最小选择原则。单话作品根本不存在上下话，在首屏黄金区域放置两个死按钮占用 60px+ 纵向高度，不仅引发用户对是否存在未加载内容的误判，更在移动端大幅推挤了正文画页网格。
- **具象修复方案**：
  在 `ChapterView.vue` 的 `.chapter-pager` 根节点上挂载 `v-if="chapters.length > 1"`，单话作品自然隐退整套分页器。
- **建议指令**：`$impeccable distill`

### [P2] 桌面端操作冗余与话序信息三重重复（Desktop Action Duplication & Eyebrow Redundancy）

- **问题定义**：
  1. 桌面端操作区同时存在「编辑章节」独立按钮与包含「修改本话名称…」的下拉菜单；
  2. 头部卡片在 80px 纵向高度内连续渲染三次“第 X 話”：Eyebrow 标“第 X 話”、主标题 `<h1>` 默认也是“第 X 話”、下方元数据再次出现“X / Y 话”。
- **危害分析**：信息密度失衡，存在界面噪点与冗余决策。
- **具象修复方案**：
  桌面端收敛重复按钮；主标题无自定义标题时，顶部 Eyebrow 提炼为所属本子书名或“章节概览”，主标题保留典雅 Serif 呈现，副标题专注文档属性。
- **建议指令**：`$impeccable clarify`

### [P2] 全局页码工程术语外泄（Global Page Index Technical Leakage）

- **问题定义**：`ChapterView.vue:188` 元数据中直接展示 `第 1–24 全局页`。
- **危害分析**：违背 Nielsen #2（与真实世界匹配）。“全局页”是系统底层数据打平的实现细节，读者不需要关心全局数据库页码。
- **具象修复方案**：
  优化文案为更符合书籍典藏感的「全书 P.1–24」或「本书第 1–24 页」。
- **建议指令**：`$impeccable polish`

---

## 7. 典型用户角色走查（Persona Red Flags）

### Casey (Distracted Mobile User / 移动端单手用户)

- **走查路径**：在地铁中单手持机打开某多话作品的第 5 话，准备挑选第 6 话或翻阅页面。
- **翻车红线 (Red Flags)**：
  - 章节切换胶囊高度仅 36px，在大拇指横滑选话时极易误触上一话或下一话；
  - 屏幕中央占据了两个各 50% 宽度的巨大翻页按钮，而胶囊条缩在卡片内部被左右遮罩严重挤压，可视范围仅能容纳 2~3 个胶囊；
  - 若打开单话作品，迎面看到两个灰色的巨大不可点按钮，以为网络卡顿未能载入完整章节。

### Alex (Impatient Power User / 效率型用户)

- **走查路径**：在桌面端使用快捷键快速查阅连载作品的各个话次。
- **翻车红线 (Red Flags)**：
  - 页面层面缺乏全局翻话快捷键（如 `[` / `]`），必须先通过鼠标或多次 Tab 键将焦点锁定在 Switcher 上方能响应方向键；
  - 桌面端眼角同时看到“编辑章节”和带有下拉小箭头的“更多章节操作”，多了一层无谓的视觉对比。

### Sam (Accessibility-Dependent User / 读屏与无障碍用户)

- **走查路径**：通过 VoiceOver 读屏器线性导航至章节切换器。
- **翻车红线 (Red Flags)**：
  - `ChapterSwitcher` 容器声明为 `role="group"`，子项为 `aria-pressed="true|false"` 的 button，读屏器报出为一组 Toggle 按压开关，而非单选 Tab 语义；
  - 移动端 36px 触控尺寸不满足无障碍舒适热区标准。

---

## 8. 次要体验细节观察（Minor Observations）

1. **组件架构未复用 `AppChip`**：`ChapterSwitcher.vue` 内部裸写了 `<button>` 并手工拼接各种 class（`.chapter-ordinal`, `.chapter-title`, `.chapter-current`, `.chapter-count`），未复用 DESIGN_NOTES §3.6 规定的统一微件胶囊体系 `AppChip`。
2. **无效路由参数的静默回退**：当 URL 传入不存在的 `chapterId` 时，代码在 `onLoaded` 中执行 `router.replace` 回本子页，未给用户弹出任何“章节未找到或已被移除”的友好提示。

---

## 9. 启发式重构设问（Questions to Consider）

1. **“移动端分页是否可以回归更自然的书籍目录流？”** —— 是否应该让 `ChapterSwitcher` 拥有全宽贴边的呼吸感，而不是把上一话/下一话做成两个笨重的大色块压在其上方？
2. **“单章节与多章节是否应该拥有更具弹性的视图形态？”** —— 对于单卷完结作品，隐退分页器后，画页网格能否立即成为主视觉焦点？
3. **“是否可以将全局键盘翻页升格为页面级一级能力？”** —— 无论当前焦点在何处，按左右方向键或特定按键均可快速切话，让桌面端体验更纯粹高效？
