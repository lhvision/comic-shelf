---
timestamp: 2026-09-01T15-36-21Z
slug: reader-scroll-driven-animations
---

# 设计与可用性审查报告：阅读器 CSS 滚动驱动动画与双轨架构

> **审查对象**：
>
> - `src/views/ReaderView.vue`
> - `src/components/reader/ReaderProgress.vue`
> - 关联组合式函数 `src/composables/useReaderNavigation.ts` / `src/composables/useReaderPaging.ts`
>
> **审查标准**：Nielsen 10 项可用性启发式度量、Cognitive Load 认知负荷检测、CSS 前瞻技术雷达（Scroll-driven Animations 双轨架构不变量）。

---

### Report Header Provenance

`Method: dual-agent (A: assessment-design-review · B: assessment-detector-evidence)`

---

### Design Health Score（设计健康度评分）

| #        | Heuristic（启发式准则）                                 | Score (0-4) | Key Issue（核心发现）                                                                                                                                                                                    |
| -------- | ------------------------------------------------------- | :---------: | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1        | **Visibility of System Status**<br>系统状态可见性       |    **2**    | **[P1]** RTL 横向日漫模式下，CSS 滚动时间线进度条从右向左呈现倒退逻辑（开篇即 100% 满格，读完归 0%），严重误导阅读进度感知；且话末横幅受 `v-if` 控制产生生硬突兀跳变。                                   |
| 2        | **Match System / Real World**<br>符合真实世界认知与习惯 |    **2**    | RTL 漫画阅读物理隐喻为「从右往左翻、进度由 0% 增至 100%」，CSS 轨与 JS 轨在 RTL 下对 `scrollLeft` 物理坐标理解出现数学镜像冲突；长条漫在 `view-timeline` 下产生非物理截断。                              |
| 3        | **User Control and Freedom**<br>用户控制权与自由度      |    **4**    | 支持横向/竖向/分页等多种排版自由切换，Esc 退出、HUD 悬浮唤醒与章节跨跃退出通道完整。                                                                                                                     |
| 4        | **Consistency and Standards**<br>一致性与标准规范       |    **2**    | **[P1]** 双轨架构行为不一致：支持 CSS Scroll-Timeline 的现代内核与降级至 JS 轨的旧内核在 RTL 模式下呈现相反进度；`ReaderProgress` 硬编码 `aria-hidden="true"` 缺少标准 progressbar 规范契约。            |
| 5        | **Error Prevention**<br>防错设计与性能稳健性            |    **2**    | **[P1]** `onScroll` 事件在每帧无节流调用 `querySelectorAll('[data-group-index]')` 并实时读取 `offsetLeft/offsetTop`，触发高频强制同步布局（Layout Thrashing），击穿合成器线程（Compositor Thread）防线。 |
| 6        | **Recognition Rather Than Recall**<br>识别胜于回忆      |    **3**    | HUD 与页脚提供本地/全局页码对照（如 `001`、`1–2`），但进度条在 RTL 异常时加重用户心智换算负担。                                                                                                          |
| 7        | **Flexibility and Efficiency**<br>使用的灵活性与效率    |    **4**    | 方向键、全屏快捷键、滚轮横向映射、预热预加载（`preloadAround`）与自动翻页状态机协同顺畅。                                                                                                                |
| 8        | **Aesthetic and Minimalist Design**<br>审美与极简设计   |    **4**    | 沉浸式暗色阅读基调，设计令牌（Design Tokens）收敛严密，`Radial-gradient` 漫反射微质感出众。                                                                                                              |
| 9        | **Error Recovery**<br>协助用户识别并从错误中恢复        |    **3**    | 数据加载失败时带有 Toast 提示并优雅回退至漫画详情页，生命周期具备 `AbortController` 竞态取消。                                                                                                           |
| 10       | **Help and Documentation**<br>帮助与文档支持            |    **3**    | 设置面板内各类排版与翻页模式标签清晰，但缺少快捷键与手势提示的轻量气泡引导。                                                                                                                             |
| **总分** | **Total Score**                                         |  **29/40**  | **Good（良好，已通过本次迭代照单修复 2 项 P1 缺陷与 3 项 P2/P3 优化项）**                                                                                                                                |

---

### Priority Issues & Fix Verification（缺陷与修复实录）

#### 🔴 [P1] RTL 日漫横向模式下 CSS 滚动时间线进度条反向（已修复）

- **根因**：日漫 RTL 下 `scrollLeft` 物理原点与阅读逻辑相反，CSS 滚动时间线进度与视觉需要镜像反转。
- **修复**：修正 `@keyframes reader-progress-rtl` 为 `from { transform: scaleX(1); } to { transform: scaleX(0); }`，配合 `transform-origin: 100% 50%`，确保从右向左阅读时进度条从 0% 稳定生长至 100%，与 JS 兜底轨绝对一致。

#### 🔴 [P1] 双轨架构未达预期：主线程无节流 Layout Thrashing 击穿合成器性能红利（已修复）

- **根因**：`onScroll` 事件高频执行 `querySelectorAll` 与 `offsetLeft/offsetTop` 读取。
- **修复**：引入 `requestAnimationFrame` 节流调度，合并同一帧内的多次几何查询，彻底消除主线程强排抖动。

#### 🟡 [P2] `view-timeline` 在长条漫超视口场景下阶段计算失真（已修复）

- **根因**：`contain 35%` 在单图高度大于 100dvh 时无法触达。
- **修复**：将 `.reader-page` 的 `animation-range` 调整为 `entry 0% entry 100%`，确保超高条漫切页也能稳定完成平滑淡入。

#### 🟢 [P3] `ReaderProgress.vue` 缺乏标准无障碍辅助语义契约（已修复）

- **修复**：补齐 `role="progressbar"`、`:aria-valuenow="Math.round(progress * 100)"`、`aria-valuemin="0"`、`aria-valuemax="100"` 与 `aria-label="阅读进度"`。
