---
timestamp: 2026-09-12T06-15-33Z
slug: reader-bubble-overlay
---

---

target: src/components/ReaderBubbleOverlay.vue
total_score: 25
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 2
timestamp: 2026-09-12T06:15:08Z
slug: src-components-readerbubbleoverlay-vue
---

# 设计评审快照：ReaderBubbleOverlay.vue & useReaderBubble.ts（阅读器台词气泡呼吸高亮浮层组件）

## 评审元信息

- **目标组件**：`src/components/ReaderBubbleOverlay.vue` & `src/composables/useReaderBubble.ts`
- **设计健康度评分**：**25 / 40**（等级：Acceptable）
- **认知负荷评估**：中度负荷（8 项中 3 项不合格：视觉层级留存、工作记忆超载、加载态渐进显露）
- **严重性缺陷统计**：P0: 0 项 · **P1: 2 项** · P2: 2 项 · P3: 1 项

---

## 1. Nielsen 10 项可用性启发式评分表

| #        | 启发式原则                                            | 得分 (0-4)  | 关键缺陷与设计检视                                                                                                                                                                                                  |
| -------- | ----------------------------------------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | 系统状态可见性 (Visibility of System Status)          | 2           | **[P1 缺陷]** 异步图片加载期动效提前夭折：图片网络下载与解码期（骨架屏）浮层即开始播放，大图呈现时 2.2 秒呼吸脉冲已结束并 `visibility: hidden`；淡出后页面零视觉残留，用户无从得知是否成功命中台词。                |
| 2        | 系统与真实世界匹配 (Match System / Real World)        | 3           | 朱砂金墨线框契合纸间“私塾阅览室朱砂圈点”真实隐喻；但在缺失坐标时凭空捏造 `DEFAULT_BUBBLE_BOX` 虚假分镜框（右上区域），在白底或无对白处圈画，违背现实世界批注规律。                                                  |
| 3        | 用户控制与自由度 (User Control and Freedom)           | 2           | **[P1 缺陷]** 缺少动效重播、主动隐藏与 URL 状态清理机制：动画淡出后无法重新唤醒；若读者觉得遮挡想要提前关闭无从操作；路由 `?bubble=1` 参数永久滞留在地址栏，刷新或分享导致意外回放。                                |
| 4        | 一致性与标准 (Consistency and Standards)              | 2           | **[P1 缺陷]** 归一化坐标系与 Flex 容器 Letterbox 空间脱节：以 `inset: 0` 铺满外层 Flex 容器而非实际包含黑边的图片渲染矩形，在横向翻页、单页双页及适应高度模式下，高亮框严重偏移漫画画面，飘在黑边留白处。           |
| 5        | 防错机制 (Error Prevention)                           | 3           | 坐标数值通过 `clampedYmin/clampedXmin` 等做好了 0~1 越界保护；但台词微标胶囊 `.bubble-callout` 未做视口边界防碰撞，顶部分镜对白（`ymin < 0.08`）导致胶囊向上溢出被截断。                                            |
| 6        | 认知识别优于记忆回想 (Recognition Rather Than Recall) | 2           | 2.2 秒脉冲彻底消失后，多角色杂乱分镜下用户必须完全依靠短期记忆记住刚才高亮在哪里；长句台词被写死 `max-width` 截断且无完整展示通道。                                                                                 |
| 7        | 灵活性与使用效率 (Flexibility and Efficiency)         | 2           | 缺乏键盘快捷键（如按 `B` 键重播对白高亮）；长卷瀑布流阅读模式下仅滚动到页首，未将页面内具体的高亮气泡纵向坐标（`box[0]`）平滑滚动至视口正中。                                                                       |
| 8        | 审美与无干扰设计 (Aesthetic and Minimalist Design)    | 3           | 严格遵循纸间设计哲学：朱砂主色 `oklch(0.59 0.17 38)` 调和金墨 `#d49f48`，绝无廉价毛玻璃与紫色渐变，`pointer-events: none` 杜绝阻碍翻页；但呼吸峰值时 3 层高斯阴影稍显赛博朋克霓虹光晕，可进一步收敛为温润金石墨晕。 |
| 9        | 容错与恢复 (Error Recovery)                           | 3           | 坐标字符串格式异常（非数值、长度不足）能安全回退；但当参数异常时静默降级为假分镜框，缺乏“坐标已失效，已定位至本页”的真实错误反馈。                                                                                  |
| 10       | 帮助与文档 (Help and Documentation)                   | 3           | 代码层拥有规范 JSDoc/TSDoc 注释；但 DOM 上对读屏器声明了 `aria-hidden="true"`，使得视障用户完全无法获取命中的台词文本与定位依据。                                                                                   |
| **总分** |                                                       | **25 / 40** | **Acceptable**（基础视觉雅致，但存在 2 项影响核心定位功能的实质性 P1 缺陷，必须整改后方可交付）                                                                                                                     |

---

## 2. 认知负荷核对（Cognitive Load Checklist）

- [x] **单点聚焦 (Single focus)**：聚焦单页单个台词气泡，避免视觉噪音分散。
- [x] **信息分块 (Chunking)**：高亮矩形框 + 单条文本摘要，层级清晰。
- [x] **视觉编组 (Grouping)**：金墨线框、朱砂微晕与胶囊标签紧密组合。
- [ ] **视觉层级 (Visual hierarchy)**：❌ **失败**。在动画运行的 2.2 秒内视觉重心极强，但一旦动画淡出结束，视觉层级瞬间归零，界面毫无提示，断崖式衰减。
- [x] **单步决策 (One thing at a time)**：被动指示高亮，用户仅需跟随视线阅读。
- [x] **极简选择 (Minimal choices)**：无需任何冗余交互选择。
- [ ] **工作记忆 (Working memory)**：❌ **失败**。高亮在 2.2 秒后 `opacity: 0; visibility: hidden;`，漫画一页常有 5~10 个对白框，读者一旦视线移开或受打扰，必须消耗短期工作记忆去回想方才高亮的位置。
- [ ] **渐进显露 (Progressive disclosure)**：❌ **失败**。图片异步加载期间未做时序门禁，在骨架屏/黑屏阶段就把高亮动效消耗殆尽，未能配合图片呈现进行渐进式呈现。

---

## 3. 设计特征度诊断（Design Specificity Verdict）

- **LLM 评估**：
  组件严格贯彻了纸间私人阅览室（Quiet Archive）与古典书房的调性规范：
  1. **色彩与材质**：彻底摒弃了现代 Web 泛滥的紫色渐变与廉价毛玻璃（`backdrop-filter`），选用品牌朱砂主色 `oklch(0.59 0.17 38)` 与暖金纸色 `#d49f48` 进行 `color-mix` 调和，背景采用宣纸暖琥珀朱砂微底，带有传统文人朱砂批注的雅致韵味；
  2. **交互安全性**：全局注入 `pointer-events: none` 与 `overflow: visible`，用户点击、翻页、双击放大操作丝滑穿透，绝无阻碍阅读的遮罩胶水；
  3. **动效弹性**：严守 `prefers-reduced-motion` 规范，无障碍降级为静态平滑淡入淡出。
     然而，在**几何空间计算**与**网络异步时序**两个工程维度上脱离了纸间真实阅读器的运行环境，出现了“坐标系对错基准”与“加载期提前夭折”两大硬伤。

---

## 4. 优势亮点（What's Working）

1. **纯正朱砂金墨纸材质感（Exquisite Quiet Archive Aesthetics）**：
   以 `color-mix(in oklab, var(--accent) 84%, #d49f48 16%)` 勾勒金墨朱砂双色，宣纸底色微泛琥珀朱砂晕，彻底杜绝了廉价毛玻璃堆叠与蓝紫渐变，与深墨色阅读器底色浑然一体。
2. **绝对零阻碍与平滑降级（Zero-Obstruction Interaction & Motion Resilience）**：
   全链路配置 `pointer-events: none`，无论是翻页触控、鼠标滚轮还是双击缩放，交互完全零感穿透；对 `prefers-reduced-motion` 提供了降级为仅透明度过渡的静态动画。
3. **参数清洗与边界收敛（Robust Coordinate Parsing & Clamping）**：
   `parseBubbleBox` 考虑了逗号分隔与数组中括号格式，且利用 `Math.max(0, Math.min(1, val))` 对坐标进行了严格的归一化保护，有效抵御畸变数据崩溃。

---

## 5. 核心缺陷与改进清单（Priority Issues）

### [P1] 归一化气泡坐标系与 Flex 容器 Letterbox 空间脱节（Geometry Coordinate System Mismatch & Pillarbox/Letterbox Drift）

- **问题定义**：
  `targetBubble.box` 遵循图像归一化百分比标准 `[ymin, xmin, ymax, xmax]` ∈ [0, 1]（基于漫画原图实际像素宽高）。然而在外层 Flex 居中容器下，图片四周存在黑边/留白（Letterbox / Pillarbox）。直接以外层 Flex 容器计算百分比，会导致在横向翻页或适应高度模式下，高亮框严重偏离实际漫画画格。
- **落地修复方案**：
  在 `ComicPageImage.vue` 内部，将插槽包裹在与 `<img>` 精确同宽高、同位置的图像锚点容器（`.comic-page-img-frame`）内部，确保百分比基准 100% 锁定在图片本体。

### [P1] 异步图片加载与 2.2 秒脉冲动效生命周期严重脱节，白屏/骨架期即刻提前夭折（Premature Animation Expiration During Image Loading）

- **问题定义**：
  大图处于网络下载与解码期（`loading === true`，展示 `ReaderLoadingState` 骨架水墨动画）。`ReaderBubbleOverlay.vue` 中的呼吸脉冲在挂载时即刻启动，并在 2.2 秒后淡出。等到真正的漫画图片加载就绪呈现时，气泡早已消失不见。
- **落地修复方案**：
  1. **就绪门禁（Image Ready Gate）**：`ComicPageImage` 仅在图片 `@load` 加载就绪（`loading === false`）后才激活气泡高亮动画，确保读者在看到画面的第一眼迎接呼吸脉冲；
  2. **温润朱砂暗印留存（Resting Stamp）**：动效结束后不彻底消失，平滑转入 18% 透明度的极细朱砂金墨静止线框（`.is-resting`），降低读者工作记忆负担，随时可看清命中对白。

### [P2] 边缘碰撞越界与视口安全溢出（Boundary Collision & Viewport Flipping）

- **落地修复方案**：
  当 `ymin < 0.12` 时将台词微标胶囊动态翻转至气泡框下方；当 `xmin > 0.65` 时对齐右侧，彻底杜绝顶部或右侧切屏。

### [P2] 类型定义单源收敛（Single Source of Truth for TargetBubble）

- **落地修复方案**：
  将 `TargetBubble` 单一真理源收敛至 `src/composables/useReaderBubble.ts`，组件层直接引用复用。
