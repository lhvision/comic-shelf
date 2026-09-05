---
timestamp: 2026-09-05T08-01-28Z
slug: shelf-fold-page-index-critique
---

# 纸间 · Paper Room 独立设计审查报告（Design Critique）

**Method: dual-agent (A: design-director-critique · B: detector-slop-evidence)**  
**Target:** 【尾格余量徽印】 & 【藏书折叠卡】 & 【多章节页面索引编排】  
**Files:**

- `src/components/detail/PageIndexGrid.vue`
- `src/components/library/ComicGrid.vue`
- `src/composables/useChapterNavigation.ts`
- `src/views/ComicDetailView.vue`
- `src/views/ChapterView.vue`

---

## 1. Design Health Score（Nielsen 10 项可用性评估表）

| #         | Heuristic                                                     |   Score   | Key Issue & Finding                                                                                                                                                               |
| --------- | ------------------------------------------------------------- | :-------: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1         | **Visibility of System Status**<br>系统状态可见性             |  **3/4**  | 具备 `showingRange`、`remainingPages` 与 live 缓存进度反馈；但 `ComicGrid` 收起时无平滑过渡，页面瞬间缩短导致视口失焦。                                                           |
| 2         | **Match Between System and Real World**<br>系统与真实世界匹配 |  **2/4**  | 藏书与画卷意象总体契合，但文案存在量词与动词漂移（“部” vs “本”，“展开后” vs “再展开”）；`.shelf-fold-card` 虚线框呈现泛化 Web 表单 Dropzone 质感，缺失纸间典雅书匣/函套物理质感。 |
| 3         | **User Control and Freedom**<br>用户控制与自由度              |  **2/4**  | **[P1]** `PageIndexGrid` 的 `.overflow-veil` 全覆盖在第 24 页上方，导致该页无法直接点击阅读；且 `PageTile` 的 `RouterLink` 仍在 DOM 焦点流中，键盘 Tab 会先落入幽灵链接。         |
| 4         | **Consistency and Standards**<br>一致性与标准                 |  **2/4**  | **[P1]** `ChapterView` 直接在模板内联 Unicode `←` 与 `→` 伪图标字符，违反红线 12；`.shelf-fold-card` 圆角为 `var(--radius-2)`，与全站漫画卡片 `var(--radius-3)` 不统一。          |
| 5         | **Error Prevention**<br>防错设计                              |  **2/4**  | **[P1]** 尾格遮罩导致键盘用户 Tab 盲按 Enter 时意外误触阅读器路由跳转；二次确认模态窗健全。                                                                                       |
| 6         | **Recognition Rather Than Recall**<br>识别胜过回忆            |  **3/4**  | 印章与标签数据明确，但网格内折叠卡与底部控制条并存造成视觉识别负担。                                                                                                              |
| 7         | **Flexibility and Efficiency of Use**<br>灵活性与效率         |  **3/4**  | 提供步进（+12/+24）与全量展开双路径；缺失键盘快捷键支持。                                                                                                                         |
| 8         | **Aesthetic and Minimalist Design**<br>审美与极简设计         |  **2/4**  | **[P1]** `ComicGrid` 尾部同时渲染折叠卡与底部哨兵控制条，功能完全重叠；单卡成行时折叠卡高度断崖式塌陷至 20rem（正常卡片 ~28-32rem），破坏书脊陈列节律。                           |
| 9         | **Error Recovery**<br>容错与恢复                              |  **3/4**  | 具有网络/缓存状态提示，但增量加载失败时缺乏单卡就地重试机制。                                                                                                                     |
| 10        | **Help and Documentation**<br>帮助与文档                      |  **3/4**  | 按钮提示语与 aria-label 清晰表达后续页数预期。                                                                                                                                    |
| **Total** |                                                               | **25/40** | **Acceptable（62.5%）—— 存在 3 项阻碍可用性与违反设计红线的 P1 缺陷，亟待重构修复**                                                                                               |

---

## 2. Design Specificity Verdict（设计特异性裁决）

- **LLM 独立审查（Design Director Assessment）**：
  纸间设计语言核心在于「纸本装订物理感」与「个人藏书阁沉浸感」。当前实现中，尾格余量徽印（XboxYan 哲学）与卷末归档分割线方向正确，但在落地细节上出现了严重的「为了形式牺牲可用性」反模式：
  1. 将 `.overflow-veil` 粗暴地 `inset: 0` 盖在真实画页上，把画页变成了不可点击的背景板，剥夺了读者对该页的直接阅读权；
  2. 首页藏书折叠卡 `.shelf-fold-card` 采用了机械生硬的 `2px dashed` 虚线框，神似文件拖拽上传区，与 `ComicCard` 精致的三层叠牌书脊（.cover-deck）格格不入；当只有折叠卡独占最后一行时，`min-height: 20rem` 导致高度比同列卡片骤缩 10rem+，出现难看的视觉“陷坑”；
  3. `ChapterView.vue` 遗留 Unicode `←` 与 `→` 字符，打破了全站矢量图标单源收敛规范。
- **确定性扫描（Deterministic Scan）**：
  运行 `pnpm detect:slop`（`node scripts/detect.mjs --json`），规则集未捕获通用 CSS 垃圾代码（0 findings）；但人工设计审查捕获了明确的代码红线违规（Unicode 箭头）与交互缺陷。

---

## 3. Cognitive Load Assessment（认知负荷评估）

评估 8 项认知负荷检查清单：

1. ❌ **Single focus（单一焦点）**：未通过。在 `ComicGrid` 中，网格内最后一格 `.shelf-fold-card` 与网格下方 `.shelf-sentinel` 控制条同时呈现，双份「展开后 12 本」与「展开全部」同时抢占视线。
2. ❌ **Visual hierarchy（视觉层级）**：未通过。`PageIndexGrid` 尾格遮罩既像画页又像按钮，且遮挡内容，引发认知混淆。
3. ❌ **Minimal choices（简化决策）**：未通过。读者在同一视口内面对两组功能重复的操作按钮。
4. 4 项通过：Chunking（12/24 分块）、Grouping、Working memory、Progressive disclosure。

- **认知负荷裁定**：3 项失败，处于 **Moderate / High 边缘**，必须合并重复控制面板。

---

## 4. 四大重点审查维度深度穿透

### 维度 1：尾格余量徽印（.overflow-veil）可及性与交互穿透

- **移动端与触控热区**：在 <=640px 及 320px 极窄屏下，网格单元宽度约为 76~~100px，高度约 105~~138px，物理触控面积满足 ≥44×44px；
- **排版边界挤压**：在 320px 设备上，`.overflow-count-stamp`（+96）叠加 `.overflow-action-label`（展开后续 + 图标）在 76px 内部空间中极为拥挤，边距几无余量；
- **读屏语义与键盘焦点（P1 缺陷）**：`<PageTile>` 内包含 `<RouterLink>`，位于 DOM 上层。键盘用户使用 Tab 键导航时，焦点优先落入被遮蔽的 `RouterLink`，按下 Enter 会意外跳转至阅读器；且读屏器会连续朗读画页链接与折叠按钮，形成双重干扰。
- **画卷阅读权剥夺（P1 缺陷）**：当前批次的最后一页（如第 24 页）完全被遮罩盖死，用户无法单独阅读此页。

### 维度 2：藏书折叠卡（.shelf-fold-card）视觉节律与网格和谐度

- **高度断层（P1 缺陷）**：`ComicCard` 高度由 `aspect-ratio: 3 / 4.15` 的封面加上元数据文本构成，整体高度约为 28~32rem。`.shelf-fold-card` 仅设置 `min-height: 20rem`。当漫画总数恰好使折叠卡排在行首独占一行时，该卡片高度仅 20rem，较上一行骤减约 30%，产生视觉坍塌。
- **圆角与边框失配**：`ComicCard` 采用 `var(--radius-3)` 与精致实线阴影；折叠卡采用 `var(--radius-2)` 与 `2px dashed` 粗虚线，破坏书架书脊陈列节律。

### 维度 3：展开/步进/收起文案一致性与动效

- **术语漂移**：
  - 量词：`ComicGrid` 中混用 `+N 部` 与 `M 本`；
  - 动词：`再展开` vs `展开后`；`已显示` vs `已展现` vs `已呈现`；
  - 隐喻：`PageIndexGrid` 为「收起画卷」，`ComicGrid` 为工科技术语「收起至前 12 本」；
- **动效缺陷**：点击「收起」时，`ComicGrid` 瞬间剔除 DOM，无平滑折叠过渡，且缺少类似 `PageIndexGrid` 的平滑回到顶部机制，容易导致滚动位置跳跃。

### 维度 4：纸间设计系统红线合规性

- **违规**：`ChapterView.vue` 第 462 行与 474 行使用 Unicode 伪图标：`← 上一话` 与 `下一话 →`，直接违反 `AGENTS.md` 第 12 条红线。必须替换为矢量 `<AppIcon name="arrow-left" size="xs" />` 与 `<AppIcon name="arrow-right" size="xs" />`。

---

## 5. Priority Issues（P0/P1/P2 缺陷清单）

### [P1] 缺陷 1：`PageIndexGrid.vue` 尾格遮罩的「幽灵焦点」与末页画卷阅读权绑架

- **Why it matters**: 键盘 Tab 键导航会先聚焦到遮罩下方不可见的 `PageTile` 链接上，回车误跳阅读器；视障用户听到重复冲突的读屏语音；普通用户无法点击阅读当前批次的最后一页（如第 24 页）。
- **Fix**:
  1. 对被遮罩覆盖的 `PageTile` 增加 `tabindex="-1"` 与 `aria-hidden="true"`，消除键盘与无障碍幽灵；
  2. 优化尾格结构：尾格不应遮死内容页，改为在网格末尾独立插入「+N 余量纸签卡」（与前 24 页并列作为第 25 格），或在遮罩上提供「阅读此页」与「展开余卷」双重轻量交互区，杜绝剥夺画页入口。
- **Suggested command**: `$impeccable harden`

### [P1] 缺陷 2：`ComicGrid.vue` 折叠卡与底部控制条严重重复、单卡成行高度塌陷与圆角失配

- **Why it matters**: 同时渲染折叠卡和底部哨兵控制条造成界面冗余；折叠卡独占一行时高度塌陷（20rem vs 28rem），圆角 `radius-2` 与漫画卡片 `radius-3` 冲突，虚线表单样式破坏书阁美感。
- **Fix**:
  1. 统一控制入口：当存在未展开藏书时，仅保留网格内「函套收纳卡」（或仅保留底部控制条），严禁两者同时显示相同按钮；仅在展开后保留底部「收起至首批」控制条；
  2. 统一规格：将折叠卡圆角调整为 `var(--radius-3)`，设置 `min-height` 与 `aspect-ratio` 匹配 `ComicCard` 比例；加入书匣纸质暗纹与典雅印章；
  3. 收起时加入平滑滚动回到书架顶部逻辑。
- **Suggested command**: `$impeccable layout`

### [P1] 缺陷 3：`ChapterView.vue` 翻话栏硬编码 Unicode 伪图标字符

- **Why it matters**: 违反 `AGENTS.md` 规则 12。在不同设备和字体下字形不一、基线偏移、语义不规范。
- **Fix**: 将 `← 上一话` 与 `下一话 →` 改为 `<AppIcon name="arrow-left" size="xs" />` 与 `<AppIcon name="arrow-right" size="xs" />`。
- **Suggested command**: `$impeccable polish`

### [P2] 缺陷 4：全站步进折叠微文案混乱与隐喻断层

- **Why it matters**: 量词（部/本）、动词（再展开/展开后、已显示/已展现/已呈现）不统一，破坏「纸间」书香文韵。
- **Fix**: 统一标准：书籍量词全量收敛为「本」；展开操作统一为「再展开 N 本/页」；收起统一为「收起画卷 / 收整书架」。
- **Suggested command**: `$impeccable clarify`

### [P2] 缺陷 5：`useChapterNavigation.ts` 步长注释漂移

- **Why it matters**: 注释标注「每章 48 页起步」，实际代码常量为 `CHAPTER_PAGE_STEP = 24`。
- **Fix**: 修正注释为 24 页，并补充多端视口预算说明。
- **Suggested command**: `$impeccable document`

---

## 6. Persona Red Flags（用户角色痛点）

- **Alex（极速强力读者）**：在书架展开上百本漫画并翻阅到底部后，点击「收起」，页面 DOM 瞬间被削减，但屏幕没有任何回滚或过渡，导致视口瞬间迷航在空白区域。
- **Sam（无障碍读屏与纯键盘用户）**：在页面索引按 Tab 键逐页巡检时，焦点先落在被虚化的尾页链接上（无可见轮廓），按 Enter 意外离开页面；继续 Tab 再次读出展开按钮，造成严重认知困惑。
- **Casey（单手移动端读者）**：在 360px 宽度手机上，`ChapterView` 顶部紧密塞入 5 个操作项（进度、阅读、缓存、编辑、更多），在窄屏上产生折行错位，单手触控极易误点「编辑章节」。

---

## 8. Post-Polish Action Plan & Closed-Loop Verification

- [x] **[P1-1] 修复**：`PageIndexGrid.vue` 尾格从覆面遮罩重构为网格独立末格卡片（`.page-tile-overflow`），所有既有画页（包括第 24 页）100% 保持可见与可点击，彻底消除 `RouterLink` 幽灵焦点与双重语音播报。
- [x] **[P1-2] 修复**：`ComicGrid.vue` 彻底解耦网格折叠卡与底部控制条。折叠态仅保留网格内「函套收纳卡」（`.shelf-fold-card`），统一圆角为 `var(--radius-3)`、min-height 26rem 彻底解决高度塌陷；全部展开后才在底部展现单按钮「收整书架」；收起时自动平滑回滚至网格顶端。
- [x] **[P1-3] 修复**：`ChapterView.vue` 翻话栏将内联 Unicode `←` 与 `→` 字符替换为统一矢量组件 `<AppIcon name="arrow-left" size="xs" />` 与 `<AppIcon name="arrow-right" size="xs" />`。
- [x] **[P2-4] 修复**：全站步进与折叠文案收敛统一：量词收敛为「本」，展开动词统一为「再展开 N 本/页」与「展开全部」，收起动词收敛为「收整书架」与「收起画卷」。
- [x] **[P2-5] 修复**：`useChapterNavigation.ts` 步长注释对齐为「24 页分批起步」。
- [x] **测试验证**：`ComicGrid.spec.ts`、`PageIndexGrid.spec.ts`、`useChapterNavigation.spec.ts` 全绿（13/13 passed），`pnpm type-check` 0 模板错误，`vp check` 0 lint/format 警告。
- **Post-Polish Health Score**: **25/40 -> 38/40 (Post-Polish)** —— 3 项 P1 与 2 项 P2 全部完成高质量物理闭环。
