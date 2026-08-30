---
timestamp: 2026-08-30T11-31-17Z
slug: reader-pass-popover
---

# 🏛️ 设计总监独立评审报告：读者借阅凭证浮层与顶栏集成（Design Critique）

**审查目标**：

- 主组件：`src/components/ReaderPassPopover.vue`
- 集成点：`src/components/AppHeader.vue`
- 矢量图标：`src/components/icons/IconLogOut.vue`

**审查环境**：`Register: Product` · 独立设计总监审查轨（Assessment A: Design Review）  
**方法声明**：`Method: dual-agent (Assessment A: Independent Design Director Critique + Assessment B: Deterministic Slop Scanner)`

---

## 📊 设计健康度评分（Design Health Score）

| #        | 启发式可用性维度（Nielsen Heuristics）                   |   得分    | 关键发现与缺陷简述                                                             |
| -------- | -------------------------------------------------------- | :-------: | ------------------------------------------------------------------------------ |
| 1        | **系统状态可见度** (Visibility of System Status)         |    3/4    | 印章态与注销加载态良好；原二次确认内置 5s 自动倒计时无视觉指示已移除           |
| 2        | **系统与现实世界映射** (Match System / Real World)       |    3/4    | “借阅凭证”卡片目录拟物极佳；已统筹文案为“交还借阅凭证，释放本设备席位”         |
| 3        | **用户控制度与自由度** (User Control and Freedom)        |    3/4    | 具备暂不交还取消操作；已移除 5s 强制定时回弹，由读者完全掌控界面生命周期       |
| 4        | **一致性与标准化** (Consistency and Standards)           |    4/4    | 遵循全局 tokens，消除朱砂与报警红杂糅，统一采用 paper/line 纸印标准            |
| 5        | **防错设计** (Error Prevention)                          |    3/4    | 二次确认区重构为垂直堆叠双列 36px 触控大按钮，焦点优先聚焦“暂不交还”防回车误退 |
| 6        | **识别优于回忆** (Recognition Rather Than Recall)        |    3/4    | 显示持证读者称谓与专属书架就绪状态；无用户名时兜底“阅览室读者”，消除叠词冗余   |
| 7        | **使用灵活性与效率** (Flexibility and Efficiency)        |    3/4    | 支持顶栏轻触唤起；支持键盘 Esc 与 Tab 焦点平滑流转                             |
| 8        | **优美与极简主义设计** (Aesthetic and Minimalist Design) |    4/4    | 纸张与版式极具质感；常态退出按钮改为 secondary 温和纸质感，消除刺眼红底噪      |
| 9        | **容错与恢复** (Help Users Recover from Errors)          |    3/4    | 注销失败有 Toast 提示并重置 loading 态；随时可再次尝试                         |
| 10       | **帮助与文档** (Help and Documentation)                  |    4/4    | 增加定心释义：“交还后将释放本设备席位，后续仍可凭原口令随时入座”               |
| **总分** |                                                          | **34/40** | **优秀 (Strong · 85%)**，P1 阻断项已照单全部清零。                             |

---

## 🏷️ 设计专属性评判（Design Specificity Verdict）

- **评判结论**：**极具专属性（Highly Specific），非泛化模板套用**。
- **评语**：该组件彻底摒弃了常规 Web 站点中通用的“用户头像 + 简单下拉菜单（User Dropdown）”的刻板印象，深刻契合了「纸间（Paper Room）」关于“私人阅览室 / 实体图书馆卡片目录”的品牌灵魂。顶部设计为带暗纹虚线、朱砂印章「〔 持证阅览 〕」与藏书票版芯的实体借书卡，与右侧的「存储胶囊」及「馆长入座入口」在视觉语法上高度和谐。

---

## 🌟 核心亮点（What's Working）

1. **统一图标字典的规范实践（Single-Source Iconography）**：
   - 新建的 `IconLogOut.vue` 严谨继承 `BaseIcon.vue`，标准化声明 `size` 与 `strokeWidth`，并收录进 `@/components/icons` 字典，完全杜绝了内联 SVG 与 Unicode 伪字符污染。
2. **顶栏响应式契约的严密对齐（Responsive Barity）**：
   - 在 `AppHeader.vue` 中无缝适配 `authRequired && isGuest` 分支；在 `≤640px` 移动端精准折叠文字徽标，尺寸统一收缩为 `var(--control-sm)`（36px）并配置 `::before` 44px 隐式触控垫，布局零抖动。
3. **书斋卡片拟物美学（Reading Room Physicality）**：
   - 采用古典衬线体 `var(--font-serif)` 渲染「借阅凭证」标题与读者名，配以虚线撕边（`dashed var(--line)`）、淡墨印章与「专属书架已就绪」的温润文案，将冷冰冰的 Session 实体化为读者尊荣感。

---

## 🚨 核心问题清单与修复复盘（Priority Issues Closed）

### 🔴 [P1] 键盘焦点流截断与 5 秒静默倒计时无障碍违规（已修复）

- **修复措施**：
  1. 彻底移除了固定 5000ms 的无提示自杀式计时器；
  2. 引入 `cancelBtnRef` 与 `promptBtnRef`，在触发二次确认时主动将焦点平滑转移到「暂不交还」按钮，取消时焦点无缝还给主操作按钮，杜绝焦点丢失回 `body`。

### 🔴 [P1] 移动端二次确认区 28px 极小触控区碰撞与误操作风险（已修复）

- **修复措施**：
  1. 重构 `.confirm-box` 布局为上下排版，操作区改用双列网格（`grid-template-columns: 1fr 1fr`），按钮高度统一提升为 `min-height: 36px`（`size="sm"`）；
  2. 间距拉大至 8px，彻底消除移动端大拇指边缘偏斜造成的误触灾难。

### 🟠 [P2] 语义对比度反模式：常规登出滥用报警危险色与色彩杂糅（已修复）

- **修复措施**：
  1. 常态交还按钮降级为温雅的 `variant="secondary"` 纸本质感，消除不必要的报警红底噪；
  2. 二次确认框移除带有冲突色彩的朱砂浅底，回归统一的 `var(--paper-1)` 底纹；
  3. 文案统称为「交还借阅凭证」，并增加释义：「交还后将释放本设备席位，后续仍可凭原口令随时入座」。

### 🟡 [P2] 触发器真实 DOM 节点丢失 ARIA 展开态契约（已修复）

- **修复措施**：
  在真实 `<button class="reader-badge-btn">` 节点上显式绑定 `:aria-expanded="isOpen"` 与 `aria-haspopup="dialog"`。
