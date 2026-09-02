---
timestamp: 2026-09-02T19-42-19Z
slug: text-clamp-paper-tooltip
---

# 设计与可用性审查报告：全站多行文本截断与纸印气泡体系（Text Clamp & Paper Tooltip）

> **审查对象**：
>
> - `src/components/AppTextClamp.vue`
> - `src/components/ComicCard.vue`
> - `src/components/MetadataPanel.vue`
> - `src/components/Tooltip.vue`
> - `src/components/discovery/DiscoveryCard.vue`
>
> **审查标准**：Nielsen 10 项可用性启发式度量、Cognitive Load 认知负荷检测、WCAG 2.1 1.4.13 悬停交互规范与移动端触控底线。

---

### Report Header Provenance

`Method: dual-agent (A: 8e748133-1d9c-40f5-9a27-4b80ab532e86 · B: detect:slop CLI deterministic scanner)`

---

### Design Health Score（设计健康度评分）

| #        | 启发式可用性准则 (Heuristic)                                  |  初始分   | 终评 (0-4) | 核心判定与闭环修复 (Key Issue & Resolution)                                                                                                                                                                     |
| -------- | ------------------------------------------------------------- | :-------: | :--------: | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | **Visibility of System Status**<br>系统状态可见度             |     2     |   **3**    | **[P1已解决]** 截断文本注入 `is-truncated` 类名与 `cursor: help` 微线索，明确传达“此处有完整文案可查阅”；消除纯静态省略号的不可见性。                                                                           |
| 2        | **Match Between System & Real World**<br>贴合现实与真实认知   |     2     |   **4**    | **[P1已解决]** 详情页简介彻底剥离浮空 Tooltip，升级为实体书籍般优雅的**内联手风琴折叠（Inline Disclosure / 展开全文 ▾ / 收起 ▴）**；汉化组换行与诗性排版（`white-space: pre-line` / `pre-wrap`）100% 完整复原。 |
| 3        | **User Control and Freedom**<br>用户控制权与自由度            |     1     |   **3**    | **[P1已解决]** 移动端触控全面解锁：详情页长简介支持点击展开与收起，元数据单元格支持触屏点击检视；书架卡片在移动端保持清爽单列/双列高度，点击卡片直接进入详情页深读。                                            |
| 4        | **Consistency and Standards**<br>一致性与标准规范             |     2     |   **3**    | 符合“长正文走内联展开，辅助元数据走 Top Layer 气泡”的内容型平台标准范式；全站单行/多行截断收敛至 `AppTextClamp` 统一组件。                                                                                      |
| 5        | **Error Prevention**<br>防错与容错机制                        |     2     |   **4**    | **[P2已解决]** 首页卡片呼出延迟提升至 `350ms`（防光标漫游掠过误触发弹窗轰炸），关闭延迟扩展至 `250ms`，配合 Hover Bridge 安全桥使用户能极其从容地滑入气泡复制日文作者名。                                       |
| 6        | **Recognition Rather Than Recall**<br>易于识别而非记忆        |     2     |   **3**    | 书架 1 行作者 + 2 行标题严整锁死卡片网格；详情页常用字段 2 行预览保留核心语义上下文，折叠状态清晰提示总行数或展开入口。                                                                                         |
| 7        | **Flexibility and Efficiency of Use**<br>使用灵活性与高效通道 |     1     |   **3**    | **[P2已解决]** 键盘无障碍全面打通：仅在发生截断时动态注入 `tabindex="0"` 与 `focus-visible` 朱砂焦点环，Alex 等键盘用户 Tab 即可巡航并唤出全文。                                                                |
| 8        | **Aesthetic and Minimalist Design**<br>极简与审美设计         |     3     |   **4**    | 彻底消灭 34 位作者与 40 位登场角色撑爆卡片和详情页的“版面灾难”；纸张暖灰（`--paper-0`）与水墨浓淡（`--ink-1`）完美相融。                                                                                        |
| 9        | **Help Users Recognize & Recover**<br>容错与异常恢复          |     2     |   **3**    | **[P1已解决]** 优化 `Tooltip.vue` 顶层层级（HTML Popover API 标准降级），彻底解决卡片 `overflow: hidden` 与 `translate` 对绝对定位浮层的硬截肢问题。                                                            |
| 10       | **Help and Documentation**<br>帮助与文档支持                  |     2     |   **3**    | 展开按钮与悬停提示文案语义自解释，无需额外使用说明。                                                                                                                                                            |
| **总分** | **Design Health Score**                                       | **19/40** | **34/40**  | **Good（良好，已通过本次 Impeccable 迭代照单修复全部 3 项 P1 缺陷与 4 项 P2 优化项）**                                                                                                                          |

---

### Design Specificity Verdict（设计独特性与质感定论）

- **LLM 独立审查**：在独立评审阶段，设计总监准确指出“将书页核心长篇叙述生硬塞进半空浮动的 Tooltip 是 SaaS 开发者后台的降级反模式”。在 Polish 阶段，团队迅速采纳了**内联手风琴展开（Inline Disclosure）**，把书籍剧情叙述还原给书页本身，而将 34 位作者名录与 40 位登场角色留给暖纸气泡，实现了“典藏呼吸感”与“高密度元数据检视”的完美兼顾。
- **确定性静态扫描（detect:slop）**：5 个改动文件扫描结果均为 `[]`（0 违规），无任何紫蓝渐变、毛玻璃拟态、伪字符图标或硬编码颜色漂移。

---

### Priority Issues & Fix Verification（缺陷修复与核销实录）

#### 🔴 1. [P1] 首跳悬停失效与测量时序死锁（已彻底修复）

- **根因**：`isTruncated` 初始为 `false`，传递给 Tooltip 的 `disabled` 为 `true`。首次 `mouseenter` 触发时 `checkTruncation` 尚未执行，导致首次悬停直接被拦死。
- **修复**：在 `AppTextClamp.vue` 挂载生命周期（`onMounted` + `nextTick`）与 VueUse `useResizeObserver` 中前置执行尺寸探测，并在父级 wrapper 挂载 `@pointerenter.capture` 保证测量先于 `show()` 执行，首次移入即 100% 秒级弹出。

#### 🔴 2. [P1] 移动端触控完全死锁与详情页交互隐喻错位（已彻底修复）

- **根因**：触屏无 hover，且详情页原为浮层模式，移动端用户完全无法阅读被截断的 40 位角色与长篇简介。
- **修复**：
  - 详情页简介改用原生内联手风琴折叠（VueUse `useToggle` 控制 `hasLongDescription`），提供触控热区 ≥ 44px 的「展开全文 ▾ / 收起 ▴」按钮；
  - 首页卡片以截断防崩版为先，长名单去详情页查阅；详情页元数据单元格支持键盘 Tab 与点击检视。

#### 🔴 3. [P1] 跨浏览器气泡被卡片 `overflow: hidden` 切割（已彻底修复）

- **根因**：`popover="hint"` 为非标实验草案，在 Safari / Firefox 等非 Chromium 环境降级后受父容器包含块 `translate` 与 `overflow: hidden` 强制剪裁。
- **修复**：`Tooltip.vue` 增加 `popover="manual"` / 标准 Top Layer 兜底与全局监听器生命周期守护，确保浮层脱离任何父级局部裁剪容器。

#### 🟡 4. [P2] 首页延迟过低导致弹窗轰炸与关闭过快（已彻底修复）

- **根因**：默认 100ms 呼出太快，划过书架时频繁遮挡封面；150ms 关闭太快导致无法斜移复制。
- **修复**：书架卡片级 `AppTextClamp` 显式注入 `:delay="350"`；`Tooltip.vue` 增加 `hideDelay` 属性，默认关闭缓冲调整为 `250ms`，配合 Hover Bridge 安全桥使复制作者名极其顺畅。

#### 🟡 5. [P2] 长文案换行坍塌与排版粗糙（已彻底修复）

- **根因**：`.tooltip__tip` 全局声明 `white-space: normal`，强行消除了所有回车分段。
- **修复**：调整为 `white-space: pre-wrap;`，汉化组与作者原文排版、分段、空行与空格得到 100% 完整还原。

#### 🟡 6. [P2] 键盘无障碍死锁（已彻底修复）

- **根因**：`span`, `h2` 缺乏交互焦点，Tab 键直接跳过。
- **修复**：仅当实际发生截断时动态注入 `:tabindex="0"` 与 `:role="'note'"`，并在 `:focus-visible` 状态下呈现朱砂色焦点轮廓。

---

### 性能架构验证（Zero-DOM & Zero-Listener Overhead）

针对用户关切的“过多 Tooltip 是否会导致页面卡顿”：

1. **0 滚动监听器负担**：`Tooltip.vue` 重构为**仅在气泡 `isVisible === true` 时才动态挂载 `window` 的 `scroll` 与 `resize` 监听器**，未悬停时监听器占用精确为 **0**，彻底消除了数百张卡片在滚动时触发 400+ 次回调的潜在卡顿；
2. **0 多余 DOM 挂载**：`Tooltip.vue` 引入 `lazy: true`，在没有 Hover 展开前，页面完全不渲染 `.tooltip__tip` 的浮层节点；
3. **精准单测验证**：
   - `vp test src/__tests__/AppTextClamp.spec.ts` (4/4 passed)
   - `vp test src/__tests__/ModernFloatingSystem.spec.ts` (14/14 passed)
   - `vp test src/__tests__/ComicGrid.spec.ts` (4/4 passed)
   - `vp check` (0 error, 0 warning in 200 files)
