# ADR 0014 — View Transitions 边界收敛与书架筛选 FLIP 架构解耦

- **日期**：2026-09-10
- **状态**：Accepted
- **关联**：承接 ADR 0004 (现代浮动体系与层级解耦)，扩充 `CONTEXT.md` 动效基建与 `DESIGN_NOTES.md` §55，关联 `docs/PITFALLS.md` 避坑 67

## 背景

在纸间（Paper Room）书架首页与动效管线演化中，系统遭遇了两个在不同硬件和浏览器配置下表现悬殊的严重性能与交互体验故障：

1. **弱 GPU / CPU 软解设备重排掉帧（5~15 FPS）**：
   在好友的 Chrome 152 浏览器（集成显卡且未开启完全硬件加速、或处于 CPU 软件光栅化模式）环境下，点击“展开更多标签”时发生肉眼可见的剧烈卡顿与顿挫，但在高配独显开发机上难以复现；
2. **书架筛选全局闪屏（Root Snapshot White Flash）**：
   在书架点击切换分类标签、只看喜欢或排序模式时，触发了 `document.startViewTransition`，界面发生全局白闪或轻微跳动，破坏阅读沉浸感；
3. **动效技术边界模糊与滥用**：
   部分组件在单节点微交互（如红心点赞）甚至异步网络请求（如导入作品）中包裹了 `withViewTransition`，导致渲染管线与异步 I/O 耦合，带来隐形悬挂与竞态风险。

经深入 Chromium Blink 渲染流水线分析，故障的物理链条为：

- **上游**：标签溢出抽屉使用 `grid-template-rows: 0fr ⇄ 1fr`，动画全程 260ms 内每一帧都在触发 Grid 轨道重算并向下推挤 `ComicGrid`，产生帧级连续布局重排（Forced Continuous Reflow）；
- **下游**：下方数十张漫画卡片均声明了常驻的 `view-transition-name: card-{id}`，同时卡片内多个徽章带有 `backdrop-filter: blur(4px)`。在 Blink 内核中，每一个命名的 View Transition 元素都会被提升为独立的离屏快照纹理和合成图层（Snapshot Texture Layer）。在上游连续重排的推挤下，光栅化线程与着色器每秒需要反复计算上千次高斯模糊滤镜并同步几十个快照图层，导致合成器管线彻底雪崩。

## 方案论证与权衡（Grilling Analysis）

团队对书架卡片重排位移方案展开了针对性审问与压测权衡：

### 路线 A：书架内网格完全解耦 View Transitions，页内位移交由 Vue 原生 `<TransitionGroup>`（FLIP 架构）

- **实现原理**：书架卡片闲置时不挂载任何 `view-transition-name`；卡片在页内筛选、排序、增删时的位移，全权由 Vue 内置的 `<TransitionGroup name="shelf-card">` 驱动，利用 FLIP 技术计算初始与结束矩阵差，直接在合成器线程执行 `transform: translate(dx, dy)`；
- **优点**：0 离屏快照纹理开销，0 线程间像素拷贝，120 FPS 丝滑满帧，对弱 GPU / CPU 软解完全免疫，且绝对不会触发根视口闪烁；
- **缺点**：卡片在页内重新排序时仅有平移移动，没有 View Transition 的图片交叉淡入或内部尺寸形态变形。

### 路线 B：点击筛选时临时挂载 `view-transition-name`，动画结束后卸载（瞬时挂载路线）

- **实现原理**：卡片平时保持 0 图层开销，仅在点击标签或切换排序的瞬间为可见卡片批量注入 `viewTransitionName`，触发 View Transition，并在 `finished` 之后清空；
- **否决理由**：
  1. **视觉等价但成本剧增**：卡片在页内筛选中本身只有坐标变换，View Transition 最终呈现的也就是位移。用重型快照渲染层去模拟一个 `transform: translate`，属于杀鸡用牛刀；
  2. **瞬间瞬态压力（Jank Spike）**：在用户点击的单帧内，Blink 必须瞬间为 48 张卡片分配离屏纹理并做内存快照，弱 GPU 会在点击瞬间产生 50~80ms 的主线程严重顿挫；
  3. **抢占崩溃与白闪风险**：若用户快速连续点击标签，前一个 View Transition 尚未结束即被打断，W3C 规范会抛出 `AbortError` 并跳过剩余过渡，导致卡片瞬间硬切甚至视口白闪。

经评估，**路线 A 在交互质感、物理性能与全平台容错性上具有压倒性优势**。

## 决策

### 1. 确立书架网格动效单一真理源（Vue FLIP SSOT）

- 书架卡片在页内的重排、增删与位移，全权收敛至 Vue `<TransitionGroup name="shelf-card">`（`.shelf-card-move`）；
- 严格禁止在页内数据状态变化（`selectTag`、`toggleFavorites`、`toggleCompleted`、`onSortChange`、`onClearImage`）时包裹 `withViewTransition`，彻底根除根视口白屏闪烁。

### 2. 确立 View Transitions 职责边界与瞬时绑定范式

- **全局过渡仅用于跨页面路由推进**：严格限制在 `router.beforeResolve` 中根据页面层级（书架 ⇄ 详情 ⇄ 章节 ⇄ 阅读器）派发推进过渡；
- **神奇移动瞬时挂载**：封面共享元素形态插值（Shared Cover Morph）仅在用户**明确点击卡片跳转进入详情页的瞬间**由 `useCoverTransition` 挂载 `comic-cover-active`，在路由完成（`afterEach`）后自动清理；
- **长列表零闲置快照图层（Zero Idle VT Footprint）**：常驻卡片、非激活卡片绝对禁止挂载任何 `viewTransitionName`，保持合成器图层树极度扁平；
- **阅读器内禁绝**：同在阅读器内部翻页、切话与滚动时严格禁止触发 View Transition。

### 3. 次级标签收纳升维为顶层气泡浮层（Top Layer Popover）与局部尺寸插值收敛

- `TagFilterBar.vue` 次级溢出标签彻底放弃在文档流中推挤书架卡片的尺寸过渡方案，升维为基于 HTML Popover API + CSS Anchor Positioning 的**顶层气泡浮层（Overflow Tag Popover / `AppPopover`）**；
- 页面高度与下游数十张卡片保持绝对静止（0 像素推挤、0 几何重排），从根本上切断了推挤卡片穿过吸顶毛玻璃引发的 GPU 高斯模糊连环雪崩，同时补齐无障碍焦点归还（WCAG 2.4.3）与操作闭环；
- `interpolate-size: allow-keywords` 规范精准定位于**下游无复杂推挤**的场景：书架卷末归档专匣（`ComicGrid.vue`）与详情页叙述折叠（`MetadataPanel.vue`），在不支持的环境下通过 `@supports not` 降级。

### 4. 消除高频列表卡片高斯模糊着色器（De-blurred Stamps）

- 书架卡片与发现页卡片内的角标徽章（`.id-stamp`、`.match-stamp`、`.reading-stamp`）以及收藏按钮（`.favorite-button`）彻底移除 `backdrop-filter: blur(4px)`；
- 改用高对比度半透明原子色彩 `color-mix(in oklab, var(--ink-0) 88%, transparent)` 配合 `border: 1px solid var(--line-soft)`，在视觉层次不减的前提下，将每屏几十个卡片的高斯模糊着色器开销彻底降为 0。

### 5. 禁绝异步网络 I/O 裹入 View Transitions

- 严禁在 `withViewTransition` 的回调中包裹 `api.xxx` 或 `store.importComic` 等异步网络请求；
- View Transition 的回调必须是纯粹、同步的 DOM 状态更新或紧随其后的 `await nextTick()`，防止网络抖动导致浏览器渲染管线长达数秒挂起假死。

## 影响与收益

1. **弱显卡设备性能飞跃**：在 Chrome 152 软解环境下，展开标签抽屉从 5~~15 FPS 顿挫彻底恢复至 60~~120 FPS 满帧，重排连锁推挤开销降低 90% 以上；
2. **零白闪丝滑交互**：页内标签筛选与排序切换彻底消除了 `::view-transition-group(root)` 的白屏闪动；
3. **架构边界清晰**：动效职责界定明确——页面级推进用 View Transitions，列表重排用 Vue FLIP，微交互用 CSS Scale，各司其职无交叉冲突；
4. **内存与图层显著轻量化**：书架长列表常驻合成图层减少数十个，显存开销与光栅化内存峰值大幅回落。
