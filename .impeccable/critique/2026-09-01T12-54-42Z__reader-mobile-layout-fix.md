---
timestamp: 2026-09-01T12-54-42Z
slug: reader-mobile-layout-fix
---

# 🎨 Design Critique: 阅读器移动端排版与渲染系统深度审查与重构

Method: dual-agent (A: design-director · B: architectural-inspector)

---

### 📊 Design Health Score (设计健康度启发式评分)

| #        | 启发式原则 (Nielsen Heuristics)                    | 得分 (0-4) | 关键缺陷 / 审查发现                                                                                                                             |
| -------- | -------------------------------------------------- | :--------: | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | **系统状态可见性 (Visibility of System Status)**   |     2      | 图片加载完成切换 `data-state` 瞬间容器尺寸发生灾难性跳变，`content-visibility: auto` 的估算高度与塌陷后的 40px 真实高度严重脱节导致滚动条抖动。 |
| 2        | **贴合现实与直觉 (Match System / Real World)**     |     1      | 竖向连续模式（Webtoon/条漫流）完全丧失纸卷/条漫自然连贯的下落物理感，沦为 28px 邮票微缩陈列。                                                   |
| 3        | **用户控制度与自由度 (User Control & Freedom)**    |     2      | 移动端塌陷后用户无法通过缩放或滑动正常阅读内容；设置面板的连页选项缺少针对移动端竖向模式的强约束降级。                                          |
| 4        | **一致性与标准 (Consistency & Standards)**         |     1      | 桌面端与移动端媒体查询断裂；连续模式与单页模式在 CSS 中强行套用相同的高宽约束；顶栏折叠开关违规使用伪字符。                                     |
| 5        | **防错机制 (Error Prevention)**                    |     1      | 缺乏对 `height: auto` 弹性盒内子元素百分比高度计算为 0 的防御性尺寸兜底；移动端未对多页分屏做物理隔离。                                         |
| 6        | **识别优于回忆 (Recognition Rather Than Recall)**  |     2      | 页面塌陷为 28×40px 后画面文字完全不可辨识，强制读者凭记忆猜测漫画内容。                                                                         |
| 7        | **灵活性与使用效率 (Flexibility & Efficiency)**    |     2      | 自动翻页与滚动定位在塌陷微缩状态下一次跳过多页，导航与定位逻辑失焦。                                                                            |
| 8        | **审美与简约设计 (Aesthetic & Minimalist Design)** |     1      | 移动端首屏塞入 9~14 个微型黑框邮票，顶栏遮罩与第一屏画面发生穿透重叠，视觉秩序彻底瓦解。                                                        |
| 9        | **协助识别与恢复错误 (Error Recovery)**            |     2      | 排版崩溃属于静默逻辑失效，系统无任何视觉自愈或异常重绘机制，刷新后继续从 localStorage 读取错误状态。                                            |
| 10       | **帮助与文档 (Help & Documentation)**              |     2      | 设置面板提示“无吸附，自由滚到底”，但实际交付给移动端用户的却是网格压缩图钉。                                                                    |
| **总分** |                                                    | **16/40**  | **Poor (亟需重大重构 / 核心体验阻塞)**                                                                                                          |

---

### 🧠 认知负荷评估 (Cognitive Load Assessment)

- ❌ **Single focus (单一焦点)**：失败。单屏内平铺 9+ 张微型邮票，用户视线完全失去阅读锚点，无法聚焦于当前阅读分镜。
- ❌ **Chunking (信息分块 ≤4)**：失败。9~14 张微型页面强行充斥单屏，超出短时工作记忆极限（4±1）。
- ❌ **Grouping (视觉分组与亲和度)**：失败。页码角标、微缩黑框、外层边距在极小尺寸下挤成一团，图文层级瓦解。
- ❌ **Visual hierarchy (视觉层级清晰度)**：失败。所有页面缩略为同等微小尺寸，丢失封面与正文主次之分。
- ❌ **One thing at a time (步进聚焦)**：失败。滚动时数十张微缩图飞速掠过，用户无法逐页理解剧情。
- ❌ **Working memory (无额外记忆依赖)**：失败。文字与对白缩成像素噪点，读者被迫在多个缩略图之间反复来回辨识。
- 评估结论：**6/8 项违规，属于极高认知过载与视觉噪点（High Cognitive Load）**。

---

### 🔍 根本原因与代码深度诊断 (Root Cause Analysis)

#### 1. 致命 CSS 尺寸连锁塌陷（28px × 40px 的物理几何学真相）

- 在 `ReaderView.vue` 中仅为桌面端 `@media (min-width: 681px)` 声明了 `.reader-page` 的高度，移动端（<681px）完全缺失显式高度，回落为 `height: auto`；
- `.page-frame` 声明为 `flex: 1; min-height: 0;`。当父容器高度为 `auto` 时，`flex: 1` 的计算基准高度（flex basis）收缩为 0；
- `ComicPageImage.vue` 中图片加载就绪后，`[data-state='loading']` 的 min-height 占位被移除，子元素 `.comic-page-image` 与 `.comic-page-img` 继承父级 `height: 100% / max-height: 100%`，全部解析为 0px；
- `ReaderView.vue` 声明了 `.page-frame :deep(.comic-page-img) { min-height: 40px; }`。40px 成为整个渲染树中唯一的正向高度底线；
- 漫画单页原生宽高比大多约为 0.70（即 28:40）。浏览器根据 `min-height: 40px` 与固有宽高比计算，得出宽度为 `40px × 0.70 = 28px`；
- 最终导致全书每一页均被压成 28px × 40px 的微缩邮票，在移动视口中密密麻麻塞入 9+ 张。

#### 2. “竖向连续”与“单页 Contain”的模型语义混淆 (Semantic Conflation)

- 将 `[data-mode='vertical-continuous'][data-pages='1']` 与 `[data-mode='horizontal']`、`[data-mode='vertical-paged']` 混写在一起，强制施加 `height: calc(100dvh - ...)` 与 `object-fit: contain`；
- “竖向连续”本应是自由流动的卷轴/条漫模型（纵向自然伸展，宽度 100%，高度随比例自适应），代码却试图用分页居中裁切的思路来约束连续流。

#### 3. 顶栏穿透与安全区（Safe-Area Inset）缺陷

- `ReaderTopBar.vue` 采用 `position: absolute; inset: 0 0 auto;`，但容器内未计算移动端刘海屏/打孔屏的 `env(safe-area-inset-top)`；
- 连续滚动模式下，仅首个 spread 设置了 `padding-top: var(--reader-chrome-h)`，用户下滚后顶栏显隐交互会直接与正文画面产生文字穿透重叠。

#### 4. 违规使用 Unicode 伪图标字符

- 顶栏折叠开关直接在模板中书写了 `'—'` 和 `'☰'` 伪字符作为折叠按钮，违背了矢量图标单源收敛规范。

---

### 🚨 缺陷优先级清单 (Priority Issues)

#### 🔴 [P1] 移动端视口高度塌陷与微缩邮票灾难 (28px × 40px Stamp Collapse)

- **重构方案**：
  1. 重构 `ReaderView.vue` 布局规则：在 `vertical-continuous` 模式下，移除所有 `100dvh` 锁死约束与 flex 0 高度陷阱；
  2. 让 `.reader-page` 与 `.page-frame` 在连续模式下自然撑开，`.comic-page-image` 与 `.comic-page-img` 设定为 `width: 100%; height: auto; max-width: 100%;`；
  3. `ComicPageImage.vue` 内部采用 `aspect-ratio: 0.72` 固有比例容器，防止加载前后布局剧烈抖动（CLS = 0）。

#### 🔴 [P1] 连续流与分页模式架构混杂 (Mode Entanglement)

- **重构方案**：
  1. 解耦 CSS 状态分流：清晰拆分 `.reader-scroll[data-mode='vertical-continuous']`、`[data-mode='vertical-paged']` 与 `[data-mode='horizontal']` 三套独立容器与图片尺寸模型；
  2. 移动端强制约束：在窄屏下无论设置如何，竖向连续模式与窄屏环境强制收敛为单列（`pagesPerView = 1`）。

#### 🟡 [P2] 移动端顶栏安全区与内容穿透重叠 (Chrome Collision & Safe Area)

- **重构方案**：
  1. `ReaderTopBar` 增加 `min-height: calc(var(--header-h) + env(safe-area-inset-top, 0px))` 与 `padding-top: env(safe-area-inset-top, 0px)`；
  2. 连续滚动模式下增加首屏安全区预留与底栏 `env(safe-area-inset-bottom)` 保护。

#### 🟡 [P2] 顶栏与 HUD 违规 Unicode 伪图标清理 (Unified Iconography)

- **重构方案**：全面替换为 `src/components/icons/` 下的统一 `AppIcon` 矢量组件（`IconChevronUp` / `IconMenu`），并补充精确的 `aria-label`。

---

### 👤 用户画像红线审查 (Persona Red Flags)

- 📱 **Casey (单手通勤移动读者)**：在拥挤地铁上单手打开漫画，迎面而来的是 14 张看不清任何字的 28px 灰黑方块；大拇指下滑动一下瞬间滚过 30 页。修复后单页 100% 宽度丝滑滚动，触控与排版完美还原。
- ⚡ **Alex (高阶效率读者)**：在桌面端习惯使用双页/四页翻页排版，手机打开后移动端自动收敛为单列全宽，排版无撕裂。
- 📖 **Jordan (首访小白读者)**：在设置中选择“竖向连续”，符合直觉的条漫连续滑动，阅读无障碍。
