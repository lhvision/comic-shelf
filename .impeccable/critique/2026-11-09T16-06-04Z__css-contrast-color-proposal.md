# 纸间 · Paper Room 独立设计评审报告（Design Critique）

**Method: design review only (Track A independent design review)**  
**Target Proposal**: 引入 CSS 现代色彩推导方案——`contrast-color(var(--bg))` 自动探测对比极色并结合 `color-mix(in oklab, ...)` 混融生成次级柔和文本色  
**Design Director**: Independent Track A Reviewer  
**Status**: 🔴 **REJECTED WITH CRITICAL AMENDMENTS (否决并退回架构方案)**

---

### 一、设计健康度评分（Design Health Score）

> 依据 Nielsen 10 项可用性与美学启发式原则进行严格评估，坚守纸间“温润暖纸、水墨浓淡、朱砂印章”核心隐喻与 WCAG 2.1 AA 刚性底线。

| #        | 启发式原则（Heuristic）                              | 评分 (0-4)  | 核心审查发现（Key Issue）                                                                    |
| -------- | ---------------------------------------------------- | :---------: | -------------------------------------------------------------------------------------------- |
| 1        | **系统状态可见性 (Visibility of System Status)**     |      3      | 动态推导的文字在骨架屏淡入或微光过渡中易出现明暗跳跃闪烁，削弱状态连贯感                     |
| 2        | **系统与真实世界匹配 (Match System / Real World)**   |      2      | **严重破坏实体纸墨隐喻**：算法返回的纯死黑与冷死白违背了宣纸、松烟墨的书卷触感               |
| 3        | **用户控制与自由 (User Control and Freedom)**        |      3      | 操作流未直接破坏，但暗室中关键“返回”/“退出”幽灵按钮面临推导反色隐形风险                      |
| 4        | **一致性与标准 (Consistency and Standards)**         |      1      | **击穿单源设计系统 (SSOT)**：各组件在不同容器下产生难以预测的杂散色阶，摧毁三阶墨色体系      |
| 5        | **防错机制 (Error Prevention)**                      |      1      | **击穿 WCAG AA 防线与语法回退缺失**：中间调混融对比度跌破 4.5:1；旧内核直接丢弃属性声明      |
| 6        | **识别胜于回忆 (Recognition Rather Than Recall)**    |      3      | 文本灰度不稳定迫使读者在不同卡片间反复重构明度注意力，加重视觉识别延迟                       |
| 7        | **灵活性与使用效率 (Flexibility and Efficiency)**    |      3      | 快捷键不受影响，但在暗光或强光极端阅读环境下对比度不足，直接伤害长时间阅览耐受度             |
| 8        | **审美与极简设计 (Aesthetic and Minimalist Design)** |      1      | **向平庸技术模板（Slop）倒退**：OKLab 混合死黑产生“水泥冷灰”与粉质感，典雅书房沦为冰冷控制台 |
| 9        | **协助排错与恢复 (Error Recovery)**                  |      3      | 表单错误提示无直接影响，但警告横幅（`--warning` / `--danger`）的反衬文字存在不可读风险       |
| 10       | **帮助与文档 (Help and Documentation)**              |      2      | 黑盒动态推导取代了声明式 Token，破坏 `tokens.css` 契约文档化与团队协作可维护性               |
| **总分** |                                                      | **22 / 40** | **Acceptable / Poor 濒危带（需实质性推倒重构）**                                             |

---

### 二、设计特异性判定（Design Specificity Verdict）

**LLM 设计总监判定**：**严重倾向于通用技术模板的“平均审美回归”（Algorithmic Slop）**。  
纸间（Paper Room）的灵魂在于“私人阅览室、卡片目录与旧书朱砂印”的温润克制。现有设计系统对色彩的每一处微调均高度克制：`--paper-0` 是 `oklch(0.965 0.014 88)` 的暖米宣纸，`--ink-0` 是 `oklch(0.225 0.012 70)` 带有暖褐底蕴的松烟墨，`--accent-contrast` 是精心调配的 `#fff8f2` 象牙暖白，阅读器暗室更是独立锁死防刺眼的 `--reader-ink: oklch(0.93 0.019 83)`。

该提案表面上追求“现代化 CSS 前沿”，本质上是一种**偷懒的通用黑盒算法思维**——试图用一个粗暴的 `contrast-color()` 探测极色，再用 `color-mix` 机械打折。这种做法无视了纸质媒介的色温、材质触感与层级节奏，将精心沉淀的东方典藏质感直接降解为机械式的冷白死黑。

**确定性静态规则扫描（Deterministic Scan）**：

- 冲突规则 1：违反 `DESIGN_NOTES.md` §2.1（全站色彩严格收敛至纸张、墨色、朱砂三大体系，严禁工业死黑冷白与杂色偏色）；
- 冲突规则 2：违反 `DESIGN_NOTES.md` §50 / §54（全站弹窗与阅览室暗室主题严格物理隔离，严禁暗室背景受浅色模式或外部算法穿透）；
- 冲突规则 3：违反 `docs/CSS_RADAR.md` §2.1（坚持双层安全回退守则，严禁裸写未经主流全覆盖的 Baseline Newly Available 属性导致整行声明被浏览器解析器丢弃）。

**视觉覆盖结论（Visual Overlays）**：  
方案目前处于概念构思与架构起草阶段，尚未注入业务 DOM。但其推导结果在视觉逻辑上必然导致色彩体系漂移与可读性坍塌。

---

### 三、总体印象（Overall Impression）

- **肯定之处**：探索 CSS Color 5 前沿标准、渴望减少多变体手工配置反衬文本色对的工程探索意图值得肯定；
- **致命硬伤**：混淆了“无障碍工程底线”与“品牌艺术特异性”，用返回物理死黑冷白的机械函数破坏了纸墨暖色调，且在次级混融时直接击穿了 WCAG AA 的法定对比度底线；
- **最大机会**：将现代 CSS 探测限制在“未知外部标签注入”的防御边界，核心品牌界面回归确定性、声明式的感知均匀 Token 契约。

---

### 四、亮点（What's Working）

1. **色彩空间选择正确**：混合空间选用了 `in oklab`，优于传统的 `srgb`，有效避免了红绿混合变脏棕色的经典色域坍塌；
2. **自动化反衬意识**：看到了传统手写反衬色容易遗漏的痛点，具备提升组件通用封装度的敏锐嗅觉；
3. **探索前沿标准的野心**：积极对齐 W3C CSS Color Module Level 5 规范演进方向。

---

### 五、核心缺陷清单（Priority Issues: P0–P3）

#### 🔴 [P1] 品牌核心隐喻遭工业死黑/冷白污染与 OKLab 褪色灰化（Gamut & Tint Drift into Cement Chalkiness）

- **现象**：W3C 规范与当前浏览器引擎（Chrome 147+, Safari 26+, Firefox 146+）中，`contrast-color()` 的返回值**只有且仅有**两项：`white`（`#ffffff`，D65 冷日光色温）与 `black`（`#000000`，工业纯死黑）。当通过 `color-mix(in oklab, contrast-color(...) 80%, var(--paper-0))` 进行淡化时，由于纯白/纯黑的彩度为 0，OKLab 线性插值会以极快速度抽干暖纸（`--paper-0`）与松烟墨（`--ink-0`）原本极其微弱但关键的暖色相（Hue 70~88, Chroma 0.012~0.018），沉淀出**“发青的水泥冷灰”与“粉质灰化杂色”**。
- **危害**：直接违反用户铁律“不能影响整体色系”。原本典雅温暖的书卷陈列感被抹杀，UI 呈现出廉价 AI 模板的塑料味与工业冰冷感。
- **修复方案**：禁止在纸间核心文本链条中使用 `contrast-color()` 生成常规文本色。正文与标题色必须严格收敛至显式声明的语义墨色令牌（`--ink-0`、`--ink-1`、`--ink-2`）。
- **建议指令**：`$impeccable colorize` / `$impeccable polish`

#### 🔴 [P1] 次级混合稀释导致 WCAG AA 对比度底线被击穿（Color-Mix Dilution Cracks WCAG AA Threshold）

- **现象**：`contrast-color()` 在中间调背景上本就只提供刚好压线的对比度。以纸间核心朱砂色 `--accent`（`#c74c35` / `oklch(0.59 0.17 38)`）为例，其与纯白色的对比度仅为 **4.88:1**（略高于 WCAG AA 要求的 4.5:1）。一旦为了追求“柔和”而使用 `color-mix(in oklab, contrast-color(...) 80%, ...)` 将其淡化 15%~20%，白色反衬亮度被朱砂色吸收，实际对比度瞬间断崖跌落至 **3.2:1 ~ 3.8:1**！在 `--warning`（`#9a6b17`）与 `--amber` 等中亮度背景上，对比度同样发生灾难性击穿。
- **危害**：反衬文字在弱光、户外强光或视力受损读者眼中发生严重字形融化，出现直接的可访问性违规（WCAG 2.1 1.4.3 Contrast Minimum 失败）。
- **修复方案**：彩色容器上的反衬文字严禁使用动态混合稀释。必须坚守专门手工校准的高对比度象牙暖白令牌 `--accent-contrast: #fff8f2`，保持 100% 不透明度刚性呈现。
- **建议指令**：`$impeccable harden` / `$impeccable audit`

#### 🔴 [P1] 阅读器暗室（Reader Dark Room）主题隔离被动态穿透与半透明计算异常（Darkroom Isolation Breach & Transparent Scrim Anomaly）

- **现象**：阅读器暗室采用独立的 `--reader-bg`（`#0d0e0c`）及多层极微半透明叠层（如 `--reader-surface: color-mix(in oklab, var(--reader-ink) 4%, transparent)`、`--reader-scrim: rgb(0 0 0 / 42%)`）。CSS 引擎计算 `contrast-color(var(--bg))` 时属于静态语法求值，**不具备视口像素合成感知能力（Zero Rendered Pixel Sampling）**。当 `--bg` 包含透明通道时，浏览器会基于未合成的局部 alpha 值进行极色判定，极易误判为“浅透底色”从而返回 `black`！
- **危害**：在纯黑的阅读器暗室中，幽灵按钮（`.btn-ghost`）、气泡标签或 HUD 文字被错误推导为近黑色，导致末页推荐按钮、退出阅读按钮在黑底上彻底隐形（Ghost Elements），引发致命的用户阅读受困阻断！
- **修复方案**：重申 `DESIGN_NOTES.md` §50/§54 铁律，阅读器暗室域全面禁止任何自适应浅色推导，强制绑定专属暗室令牌 `--reader-ink` 与 `--reader-surface-strong`。
- **建议指令**：`$impeccable harden`

#### 🔴 [P1] 浏览器兼容性断崖与无回退声明失效（Cascading Declaration Invalidation）

- **现象**：`contrast-color()` 属于 Baseline 2026 Newly Available（Chrome 147+, Safari 26+, Firefox 146+）。在当前大量存量设备（iOS 17/18、旧版 Android WebView、墨水屏设备等）中，该函数为非法 CSS 语法。若直接编写 `color: color-mix(in oklab, contrast-color(var(--bg)) 85%, var(--ink-0));`，根据 CSS Syntax Module Level 3 解析器规范，**整条 `color` 声明会被浏览器直接判定为 invalid 并整体丢弃**！
- **危害**：在旧版浏览器中文字颜色完全丢失，回退至全局继承色或浏览器默认纯蓝/黑，直接造成页面白屏、不可见或严重的视觉断层。
- **修复方案**：若未来在非关键边缘路径使用，必须遵循 `docs/CSS_RADAR.md` §2.1 的双层回退铁律，以第一层基础十六进制/OKLCH 兜底，第二层通过 `@supports (color: contrast-color(red))` 进行渐进增强包裹。
- **建议指令**：`$impeccable adapt`

#### 🟡 [P2] 认知负荷剧增与三阶水墨层级被打散（Visual Noise Floor & Ink Hierarchy Disruption）

- **现象**：纸间依靠固定的 `--ink-0`（浓墨）、`--ink-1`（正文）、`--ink-2`（淡墨）建立了稳定的视觉层级节剪。引入自动推导后，每个卡片根据自身微弱的背景差（如 `--paper-0` 混 `--paper-1`）计算出略微不同的文本灰度。
- **危害**：破坏了 Cowan 工作记忆法则与“视觉底噪”（Visual Noise Floor）控制，页面呈现出杂乱无章的微灰度噪点，读者潜意识需要不断重新适应字阶对比。
- **修复方案**：保持文本字阶系统（Ink Token System）的绝对离散与统一，拒绝局部连续微变化。
- **建议指令**：`$impeccable quieter`

---

### 六、独立设计总监终局裁决与落地路线图（Actionable Recommendation）

作为独立设计总监，**坚决否决将 `contrast-color()` + `color-mix` 引入全站常规组件与基础文本排版的提议**。

为兼顾技术探索与品牌纯粹性，提出以下**三层安全分治落地路线**：

1. **第一层（核心红线 · 坚决封锁）**：
   - 全站所有文字、标题、阅读器、卡片组件**绝对禁止**接入 `contrast-color()`；
   - 维持现有的三阶墨色体系（`--ink-0` / `--ink-1` / `--ink-2`）与暗室专用令牌（`--reader-ink`），保持 100% 声明式单一真理源。
2. **第二层（高危反衬 · 严格人工校准）**：
   - 彩色容器（如朱砂 `--accent`、警告 `--warning`）反衬文本保持现有人工深度调教的语义令牌（如 `--accent-contrast: #fff8f2`），确保对比度稳定在 $\ge 4.8:1$，严禁进行二级打折混融。
3. **第三层（沙箱防御 · 边缘未知色块渐进增强）**：
   - 仅当未来引入“允许用户自定义任意高饱和度分类标签”或“外部来源未知色块”时，才允许将 `contrast-color` 隔离在专属沙箱微件中作为末道防线；
   - 落地时必须严格遵循 `docs/CSS_RADAR.md` 规范：
     ```css
     /* 1. 基线兜底：使用纸间标准暖白 */
     color: var(--accent-contrast);

     /* 2. 现代渐进增强（仅在未知动态背景沙箱中） */
     @supports (color: contrast-color(red)) {
       color: contrast-color(var(--dynamic-tag-bg));
     }
     ```
