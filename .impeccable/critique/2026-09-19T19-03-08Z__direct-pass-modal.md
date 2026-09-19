---
target: src/components/detail/DirectPassModal.vue
total_score: 21
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 2
timestamp: 2026-09-19T19-03-08Z
slug: direct-pass-modal
---

# 纸间 · Paper Room 设计评审报告（DirectPassModal）

Method: independent-design-director (A: Design Review & Deep Token Inspection · B: Slop Detector & Style Engine Analysis)

### Design Health Score (Nielsen 10 Usability Heuristics)

| #         | Heuristic                       |   Score   | Key Issue                                                                                                                                                                                                                     |
| --------- | ------------------------------- | :-------: | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1         | Visibility of System Status     |    1/4    | 核心时长选项点击后无任何可见视觉状态变迁（Token 未定义导致 active 态与默认态完全同化为 0 变化）；复制状态仅由 2 秒悬浮 Toast 支撑，链接卡片缺乏就绪常态反馈。                                                                 |
| 2         | Match System / Real World       |    2/4    | 底层工程术语泄漏明显（代码与界面逻辑充斥 `TTL` / `TTL_OPTIONS` 纯网络时效术语）；直达通行证直出 URL 文本框，缺乏纸间“图书借阅笺 / 单本朱砂凭证”的实体纸质隐喻。                                                               |
| 3         | User Control and Freedom        |    3/4    | 具备“取消”与“重新配置”逃生出口，Modal 框架遵循 ESC/遮罩关闭；但生成通行证后若读者误触关闭，缺乏未复制提醒机制。                                                                                                               |
| 4         | Consistency and Standards       |    1/4    | **设计系统基线全面脱轨**：全组件充斥 30+ 处凭空捏造的未定义 CSS Token（如 `--color-vermilion`, `--color-surface`, `--radius-sm` 等通用后台残影），彻底背离 `src/styles/tokens.css` 单源契约，且未复用统一原子组件 `AppChip`。 |
| 5         | Error Prevention                |    2/4    | 起始页码允许输入负数、0 或超出 `pageCount` 的数字，行内无实时校验与边界拦截，直到提交时才在脚本中静默 `Math.min/max` 截断，违背预防在先原则。                                                                                 |
| 6         | Recognition Rather Than Recall  |    3/4    | 自动预填第 1 页并提供“上次阅读进度”一键切换按钮，降低记忆门槛；但 5 档时长描述文字扁平重复，缺乏主次与“推荐”锚点。                                                                                                            |
| 7         | Flexibility and Efficiency      |    2/4    | 缺少键盘加速通道（页码输入后按 Enter 无法直接签发，时效选项无法使用左右方向键切换）；无一键“签发并复制”的极速链路。                                                                                                           |
| 8         | Aesthetic and Minimalist Design |    2/4    | 呈现为冰冷的 SaaS 表单弹窗；5 档时长在移动端或窄视口下断行为 3+2 不对称破碎排布，视觉呼吸感较差；边框与背景色因变量失效呈现纯透明或初始墨色，缺乏纸墨雅致。                                                                   |
| 9         | Error Recovery                  |    2/4    | 接口报错仅抛出通用 Toast，表单内部无字段级错误高亮与就地重试引导，关闭 Toast 后读者无法得知具体失败字段。                                                                                                                     |
| 10        | Help and Documentation          |    3/4    | 沙箱隔离与只读边界安全提示（`sandbox-banner`）说明详尽，读者易于理解受访者权限；但针对移动端借阅分享缺乏指引。                                                                                                                |
| **Total** |                                 | **21/40** | **Acceptable (52.5%)**（存在多项严重破坏可用性的 P1 缺陷，必须整改后方可达到发布标准）                                                                                                                                        |

### Design Specificity Verdict

- **LLM Assessment**:
  **Category-Interchangeable（品类通用、毫无个性的通用表单反模式）**。
  纸间的核心品牌隐喻是“**私人阅览室（Reading Room）+ 图书馆卡片目录（Card Catalog）+ 旧书脊与朱砂印（Vermilion Ink）**”。给好友签发单本沙箱临时通行证，本质是一次充满典雅书香的“古籍单本借阅 / 盖印借书笺”的礼仪体验。
  但当前的 `DirectPassModal.vue` 从代码设计到视觉呈现均严重偏离：代码内充斥着 `TTL_OPTIONS`（Time To Live 后端术语）、`ttl-chip`、`color-surface` 等通用后台开发样板代码。组件完全丧失了纸间“Quiet, Tactile, Archival”的克制美感与宣纸墨韵，是一次典型的“AI 生成通用后台弹窗”对纸间设计系统的无感侵蚀。

- **Deterministic Scan**:
  - `pnpm detect:slop` 报告 0 处违规字符（基础图标合规，未直接写死内联 SVG）；
  - 但深入样式引擎与 Token 检索发现：**整整 32 处使用了全站未定义的虚构 CSS Token**（全站只有 `--paper-*`、`--ink-*`、`--accent*`、`--line*`、`--radius-1~4`、`--duration-1~3`，根本不存在 `--color-*`、`--radius-sm` 或 `--duration-fast`）。

### Overall Impression

业务主干逻辑完整（状态重置、剪贴板复制与接口交互链路清晰），但**核心交互体验在视觉与无障碍维度上已经实质性瘫痪**。由于样式层全面依赖不存在的虚构 Token，导致用户最频繁交互的时长选项（TTL_OPTIONS）在被点击后**没有任何视觉变化**，给用户造成“按键坏死、完全不可点”的强烈阻碍感；加之 ARIA 语义缺失与认知负荷超标，整体仍停留在原型期粗糙代码阶段。

### What's Working

1. **贴心的阅读进度自动继承（Recognition over Recall）**：自动识别 `props.lastRead` 并提供 `上次进度 (第 N 页)` 与 `第 1 页` 快捷按钮。
2. **清晰的沙箱安全边界教育（Safety First）**：配置了独立的“单本物理沙箱保护已就绪”信息块，用通俗语言明确告知权限边界。
3. **剪贴板集成体验（useClipboard Integration）**：借助 VueUse `useClipboard` 实现了原生的复制反馈与 `copiedDuring: 2000` 状态切换。

### Priority Issues (P0 - P3)

- **[P1] CSS Token 命名全面虚构，导致核心时长选项激活态 0 视觉反馈**：
  将虚构 Token 彻底换为真实 Paper Room Token：`--line`, `--paper-0`, `--paper-1`, `--paper-2`, `--ink-0`, `--ink-1`, `--ink-2`, `--accent`, `--accent-soft`, `--accent-strong`, `--accent-contrast`, `--radius-1`, `--radius-2`, `--duration-1`。
- **[P1] 核心单选组无障碍语义（ARIA）与键盘导航全链路缺失**：
  父级挂载 `role="radiogroup" aria-label="借阅有效时长"`，选项挂载 `role="radio" :aria-checked="selectedTtl === opt.seconds"`，键盘左右方向键导航与清晰的 `:focus-visible` 描边。
- **[P2] 认知负荷超限与移动端断行失衡**：
  精简为 4 档黄金时效（2小时、24小时【推荐·默认】、3天、7天），锁死在 ≤4 认知限度内，排布规整对称。
- **[P2] 起始页码输入缺乏行内即时动态校验与回车签发快捷键**：
  添加实时边界检查，按 Enter 键直接触发签发。
- **[P3] 生成直达链接后缺乏焦点管理与卡片式实体隐喻**：
  生成后自动聚焦复制按钮，结果卡片采用“纸间借阅笺”水墨纸张质感。
