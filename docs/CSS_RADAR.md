# CSS 前瞻技术雷达（CSS Foresight Radar）

> **用途**：纸间（Paper Room）项目的 CSS 现代特性追踪文档。记录已落地用法、降级方案与尚在草案中的特性，供下一次迭代直接查阅，无需重复读 MDN。
>
> **维护约定**：每次引入新 CSS 特性或发现规范升级时，更新对应条目的 **状态** 与 **用法片段**。

---

## 目录

1. [兼容性快查表](#1-兼容性快查表)
2. [已落地特性（Shipped）](#2-已落地特性shipped)
3. [渐进增强特性（Progressive Enhancement）](#3-渐进增强特性progressive-enhancement)
4. [实验草案特性（Experimental / Stage 1-2）](#4-实验草案特性experimental--stage-1-2)
5. [升级路线图（Roadmap）](#5-升级路线图roadmap)
6. [参考资源](#6-参考资源)

---

## 1. 兼容性快查表

> 数据来源：MDN BCD + Can I Use，更新于 2026-08。

| 特性                                | Chrome | Firefox | Safari  |          状态           |                       本项目状态                       |
| :---------------------------------- | :----: | :-----: | :-----: | :---------------------: | :----------------------------------------------------: |
| `light-dark()`                      |  123+  |  120+   |  17.5+  |    ✅ Baseline 2024     |   ⚠️ 审慎评估（保留 hex+oklch 双层回退，防色彩丢失）   |
| `color-mix(in oklab, ...)`          |  111+  |  113+   |  16.2+  |    ✅ Baseline 2023     |                       ✅ 已落地                        |
| `@container (inline-size)`          |  105+  |  110+   |   16+   |    ✅ Baseline 2023     |                       ✅ 已落地                        |
| `@layer`                            |  99+   |   97+   |  15.4+  |    ✅ Baseline 2022     |                       ✅ 已落地                        |
| CSS Nesting (`&`)                   |  120+  |  117+   |  17.2+  |    ✅ Baseline 2024     |                       ✅ 已落地                        |
| `@property`                         |  85+   |  128+   |  16.4+  |    ✅ Baseline 2024     |          ✅ 已落地（tokens.css 遮罩变量插值）          |
| `interpolate-size: allow-keywords`  |  129+  |   ⏳    |   ⏳    | 🔶 Limited Availability |        ✅ 已落地（TagFilterBar / ImportPanel）         |
| `::details-content`                 |  131+  |  143+   |  18.4+  | 🔶 Limited Availability |                      ✅ 渐进增强                       |
| `scroll-timeline` / `view-timeline` |  115+  | 111+🚩  | 18.0+⏳ | 🔶 Limited Availability |          ✅ 已落地（ReaderView 读物双轨渲染）          |
| `@container scroll-state(...)`      |  133+  |   ❌    |   ❌    |     🧪 Experimental     |        ⚠️ LightningCSS 解析报错，降级为 VueUse         |
| `@container style(...)`             |  111+  |  151+   |   18+   |       🔶 有限支持       |                       — 暂未采用                       |
| `CSSStyleSheet` (Constructable)     |  73+   |  101+   |  16.4+  |    ✅ Baseline 2023     |                   ⚠️ 与 Vue SFC 冲突                   |
| CSS `if()` 行内条件                 | 137+🚩 |   ❌    |   ❌    |       🧪 Stage 1        |                    🚫 构建工具报错                     |
| CSS `@function`                     | 139+🚩 |   ❌    |   ❌    |       🧪 Stage 2        |                      🚫 过早引入                       |
| CSS `progress()` 数学函数           |  138+  |  155+   |   26+   | 🔶 Newly Available 2026 | ✅ 渐进增强（以 `--progress` + `AppProgressBar` 承接） |

**图例**：✅ 可用 · 🔶 部分支持 · 🧪 实验旗 · 🚩 需开 Flag · ❌ 未支持 · 🚫 本项目不采用

---

## 2. 已落地特性（Shipped）

### 2.1 `light-dark()` — 双相原子色彩令牌（审慎评估与双层回退守则）

**MDN**：[light-dark()](https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/light-dark)  
**Baseline**：2024 · Chrome 123+ · Firefox 120+ · Safari 17.5+  
**本项目落地决策**：⚠️ **坚持 `#hex` + `oklch()` 双层回退，暂不全量替换为 `light-dark()`**

**实战复盘与避坑红线**：

1. **老旧内核色彩丢失风险**：若直接全量改用 `--warning: light-dark(oklch(...), oklch(...))`，在不支持或未完全兼容 `light-dark()` 的渲染引擎中，整条属性声明会被浏览器判定为 invalid 直接丢弃，导致界面缺少颜色、整体发灰严重坍塌；
2. **纸间黄金基线模式（当前生产方案）**：
   ```css
   :root {
     /* 双层回退：第一层 hex 兜底，第二层 oklch 高保真感知均匀色 */
     --paper-0: #f7f2e9;
     --paper-0: oklch(0.965 0.014 88);
     --ink-0: #211f1c;
     --ink-0: oklch(0.225 0.012 70);
     --warning: #9a6b17;
     --warning: oklch(0.6 0.11 75);
   }

   @media (prefers-color-scheme: dark) {
     :root {
       --paper-0: #191b19;
       --paper-0: oklch(0.225 0.012 120);
       --ink-0: #f2ecdf;
       --ink-0: oklch(0.935 0.016 88);
       --warning: #ffbe4a;
       --warning: oklch(0.78 0.14 78);
     }
   }
   ```
3. **注意事项**：
   - `light-dark()` 只接受颜色值，**不能用于非颜色属性**（如 `box-shadow` 的完整值不能直接套用）；
   - 后续如需迁移，必须建立在自动化视觉回归快照（Midscene AI）覆盖 100% 页面且 0 色彩丢失的前提下进行。

---

### 2.2 `color-mix(in oklab, ...)` — 色彩混合

**MDN**：[color-mix()](https://developer.mozilla.org/en-US/docs/Web/CSS/color_value/color-mix)  
**Baseline**：2023

**用法**：

```css
/* 透明色柔化 */
--accent-soft: color-mix(in oklab, var(--accent) 13%, transparent);
--line: color-mix(in oklab, var(--ink-0) 15%, transparent);

/* 暗色叠加 */
background: color-mix(in oklab, var(--paper-1) 50%, transparent);
```

**为什么用 oklab 而不是 srgb**：oklab 是感知均匀色彩空间，混合后不会出现"灰泥感"或红绿叠加变棕的问题。

---

### 2.3 `@container (inline-size)` — 容器查询

**MDN**：[CSS Containment / @container](https://developer.mozilla.org/en-US/docs/Web/CSS/@container)  
**Baseline**：2023

**用法**：

```css
/* 1. 父级声明为容器 */
.import-panel {
  container-type: inline-size;
  container-name: import-panel;
}

/* 2. 子组件内部根据自身宽度响应 —— 不依赖全局视口 */
@container import-panel (max-width: 820px) {
  .import-grid {
    grid-template-columns: 1fr;
  }
}
```

**关键优势**：组件放入侧栏、对话框或不同宽度版面时，响应式行为完全自洽，不受全局 `@media` 干扰。

---

### 2.4 `@layer` — 级联层

**MDN**：[CSS @layer](https://developer.mozilla.org/en-US/docs/Web/CSS/@layer)  
**Baseline**：2022

**本项目用法（main.css 顶层声明）**：

```css
@layer reset, base, components, utilities;

@layer reset {
  /* ... */
}
@layer base {
  /* ... */
}
@layer components {
  /* ... */
}
```

**规则**：同一 `@layer` 内，后声明的规则权重更高；不同层之间，顺序在 `@layer` 声明行处固定，无论具体规则写在哪里。

---

### 2.5 CSS Nesting（`&`）

**MDN**：[CSS Nesting](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_nesting)  
**Baseline**：2024 (Chrome 120+, Firefox 117+, Safari 17.2+)

```css
/* 不再需要重复写父选择器 */
.import-field {
  border: 1px solid var(--line);

  &:focus-within {
    border-color: var(--accent);
  }

  &.is-invalid:focus-within {
    border-color: var(--danger);
  }

  & input {
    flex: 1;
    background: transparent;
  }
}
```

---

### 2.6 `@property` — 带类型的自定义属性

**MDN**：[@property](https://developer.mozilla.org/en-US/docs/Web/CSS/@property)  
**Baseline**：2024 · Chrome 85+, Firefox 128+, Safari 16.4+  
**本项目落地状态**：✅ 已在 `src/styles/tokens.css` 落地

**用法（tokens.css 核心模式）**：

```css
/* 声明带类型的 CSS 变量，使其可以被过渡动画平滑插值 */
@property --mask-left {
  syntax: '<length>';
  inherits: false;
  initial-value: 0px;
}

@property --mask-right {
  syntax: '<length>';
  inherits: false;
  initial-value: 0px;
}

/* 现在 --mask-left / --mask-right 可以被 transition 平滑数值插值 */
.site-nav {
  transition:
    --mask-left var(--duration-2) var(--ease-out),
    --mask-right var(--duration-2) var(--ease-out);
}
```

---

## 3. 渐进增强特性（Progressive Enhancement）

> 这些特性：**新浏览器获得更好体验，旧浏览器优雅降级**。

### 3.1 `interpolate-size: allow-keywords` 与 CSS Grid 复合轨道

**MDN**：[interpolate-size](https://developer.mozilla.org/en-US/docs/Web/CSS/interpolate-size)  
**可用**：Chrome 129+（全局无级插值）；全主流浏览器（CSS Grid 复合轨道 `0fr ⇄ 1fr` 插值）  
**参考**：[张鑫旭 calc-size 与 interpolate-size](https://www.zhangxinxu.com/wordpress/2024/11/css-calc-interpolate-size/)

**作用**：允许浏览器在 `height: 0` 与 `height: auto` 之间进行纯数值插值，彻底消除 JS 测量 `scrollHeight` 的重排开销与异步闪烁。

**本项目实战落地范式（生产标准）**：

#### 范式 A：标签流式溢出抽屉（`TagFilterBar.vue`）

```css
/* 溢出标签托盘：CSS Grid 轨道尺寸插值 */
.more-tags-tray {
  display: grid;
  grid-template-rows: 0fr;
  transition: grid-template-rows var(--duration-2) var(--ease-out);
}

.more-tags-tray.is-expanded {
  grid-template-rows: 1fr;
}

.more-tags-inner {
  min-height: 0;
  overflow: clip; /* 现代 clip 代替 hidden，杜绝滚动条闪烁 */
}

.overflow-cluster {
  opacity: 0;
  transform: translateY(-4px);
  transition:
    opacity var(--duration-2) var(--ease-out),
    transform var(--duration-2) var(--ease-out);
}

.more-tags-tray.is-expanded .overflow-cluster {
  opacity: 1;
  transform: translateY(0);
}
```

#### 范式 B：多端响应式折叠卡片（`ImportPanel.vue`）

```css
/* 桌面端：融入主网格 */
.import-animator {
  display: contents;
}

/* 移动端 (≤640px)：激活 CSS Grid 复合轨道展开 */
@media (max-width: 640px) {
  .import-animator {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows var(--duration-2) var(--ease-out);
  }

  .import-animator.is-expanded {
    grid-template-rows: 1fr;
  }

  .import-animator > .import-content {
    min-height: 0;
    overflow: clip;
    opacity: 0;
    transform: translateY(-4px);
    transition:
      opacity var(--duration-2) var(--ease-out),
      transform var(--duration-2) var(--ease-out),
      padding-top var(--duration-2) var(--ease-out);
  }

  .import-animator.is-expanded > .import-content {
    padding-top: var(--space-3);
    opacity: 1;
    transform: translateY(0);
  }
}
```

#### 范式 C：原生 `<details>` 声明式折叠（`main.css` 全局声明）

```css
/* 全局基础样式，放在 @layer base */
html,
details {
  interpolate-size: allow-keywords;
}

::details-content {
  height: 0;
  overflow: clip;
  transition:
    height var(--duration-2) var(--ease-out),
    content-visibility var(--duration-2) var(--ease-out) allow-discrete;
}

details[open]::details-content {
  height: auto;
}
```

---

### 3.2 `::details-content` — 原生展开内容伪元素

**MDN**：[::details-content](https://developer.mozilla.org/en-US/docs/Web/CSS/::details-content)  
**可用**：Chrome 131+, Firefox 143+, Safari 18.4+  
**参考**：[张鑫旭 details target-content-open](https://www.zhangxinxu.com/wordpress/2025/11/css-details-target-content-open/)

**用法**：直接控制 `<details>` 内部可收起区域的样式，无需额外 DOM 包裹层。

```css
/* 全局基础样式，放在 @layer base */
details {
  interpolate-size: allow-keywords;
}

::details-content {
  height: 0;
  overflow: clip;
  transition:
    height 240ms ease-out,
    content-visibility 240ms ease-out allow-discrete;
}

details[open]::details-content {
  height: auto;
}
```

**降级行为**：旧版浏览器（不支持 `::details-content`）中 `<details>` 仍正常折叠/展开，只是没有过渡动画。

> ⚠️ **选择器隔离红线（Selector Isolation Invariant）**：
> 严禁将 `::details-content` 与普通类选择器使用逗号合并书写（如 `details.custom, ::details-content { ... }`）。在不支持该伪元素的老版本浏览器（如 Safari <18.4）中，未识别的伪元素会导致整条逗号合并规则被解析器直接废弃丢弃。必须始终保持 `::details-content` 单独成条声明。

---

### 3.3 `@container scroll-state(...)` — 滚动状态容器查询

**MDN**：[scroll-state containment](https://developer.mozilla.org/en-US/docs/Web/CSS/@container#scroll-state_container_queries)  
**可用**：Chrome 133+ · 其他浏览器❌  
**参考**：[张鑫旭 CSS container scroll-state](https://www.zhangxinxu.com/wordpress/2025/08/css-container-scroll-state/)

> ⚠️ **工具链限制（2026-08 现状）**：Vite 底层的 **LightningCSS** 解析器遇到 `scroll-state()` 语法时会抛出 `{ expected` 解析错误，导致 `vp check` / `vp build` 失败。`@container scroll-state()` 目前**不能写进任何 `<style>` 块**（含 Vue SFC 的 `<style scoped>`）。

**作用**：纯 CSS 感知容器的滚动状态（是否可向左/右继续滚动），无需 JS 事件监听。

**设计好的用法（等 LightningCSS 支持后迁移）**：

```css
/* 1. 容器声明 */
.site-nav {
  container-type: scroll-state;
  container-name: nav-scroll;
}

/* 2. 纯 CSS 感知左侧可滚动 → 显示左侧渐隐遮罩 */
@container nav-scroll scroll-state(scrollable: inline-start) {
  .site-nav {
    --mask-left: 1.25rem;
  }
}

@container nav-scroll scroll-state(scrollable: inline-end) {
  .site-nav {
    --mask-right: 1.5rem;
  }
}
```

**当前项目实际用法（AppHeader.vue 顶栏导航渐变遮罩）**：

```css
/* 完全依赖 VueUse useScroll() 注入类名降级方案 */
.site-nav.has-scroll-left {
  --mask-left: 1.25rem;
}
.site-nav.has-scroll-right {
  --mask-right: 1.5rem;
}
```

**升级步骤（等 LightningCSS 支持后）**：

1. `container-type: scroll-state; container-name: nav-scroll;` 还原到 `.site-nav`；
2. 将上方「设计好的用法」代码块粘贴至 `AppHeader.vue <style scoped>`；
3. 可选：删除 VueUse `useScroll` 的监听逻辑与 `.has-scroll-*` 类名注入（CSS 已完全接管）。

**可查询的 scroll-state 值**：

- `scrollable: top / bottom / left / right` — 绝对方向
- `scrollable: inline-start / inline-end / block-start / block-end` — 逻辑方向（推荐）
- `stuck: top / bottom / left / right / none` — 粘性定位是否黏附
- `snapped: block / inline / none` — 是否处于 Scroll Snap 对齐状态

---

### 3.4 `scroll-timeline` 与 `view-timeline` — 滚动驱动动画（Dual-Track 渐进增强架构）

**MDN**：[CSS Scroll-driven Animations](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll-driven_animations)  
**可用**：Chrome 115+, Safari 18+ (部分) · Firefox 需开启实验 Flag  
**参考**：

- [张鑫旭 不能落后，好好缕缕CSS滚动动画](https://www.zhangxinxu.com/wordpress/2024/08/css-scroll-timeline/)
- [前端侦探 CSS 滚动驱动动画终于正式支持了](https://mp.weixin.qq.com/s/xpMXcFTz53S2E1ntlvtZ0A)

**作用**：将动画执行进度与滚动位置或可视区交叉状态直接绑定，脱离主线程 JS 监听，由合成线程（Compositor Thread）以 60/120Hz 满帧运行。

**本项目实战落地范式（`ReaderView.vue` / `ReaderProgress.vue`）**：

#### 范式 A：横竖双向与日漫 RTL 滚动进度条（`scroll-timeline` + `timeline-scope`）

```css
/* 1. 滚动容器声明命名时间线与轴向 */
.reader-scroll {
  scroll-timeline-name: --reader-scroll;
  scroll-timeline-axis: block;
}

.reader-scroll[data-mode='horizontal'] {
  scroll-timeline-axis: inline;
}

/* 2. 根视图提升作用域，穿透外围进度条 */
@supports (animation-timeline: scroll()) {
  .reader-view {
    timeline-scope: --reader-scroll;
  }

  /* 纵向与横向 LTR 模式：从左向右生长（附带 1ms duration 兼容补丁） */
  .reader-view :deep(.reader-progress span) {
    transform: none;
    animation: reader-progress 1ms linear both;
    animation-timeline: --reader-scroll;
    transform-origin: 0 50%;
  }

  /* 横向 RTL 日漫模式：从右向左生长 */
  .reader-view[data-mode='horizontal'] :deep(.reader-progress.is-rtl span) {
    transform: none;
    animation: reader-progress-rtl 1ms linear both;
    animation-timeline: --reader-scroll;
    transform-origin: 100% 50%;
  }
}

@keyframes reader-progress {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}

@keyframes reader-progress-rtl {
  from {
    transform: scaleX(0);
  }
  to {
    transform: scaleX(1);
  }
}
```

#### 范式 B：连续滚动单页微质感入场与话末横幅（`view-timeline` + `animation-range`）

```css
@supports (animation-timeline: view()) {
  @media (prefers-reduced-motion: no-preference) {
    /* 连续模式单页克制微显（≤6px 位移 + 35% 视区收敛） */
    .reader-scroll[data-mode='vertical-continuous'] .reader-page {
      animation: reader-page-appear 1ms var(--ease-out) both;
      animation-timeline: view();
      animation-range: entry 0% contain 35%;
    }

    @keyframes reader-page-appear {
      from {
        opacity: 0.15;
        transform: translateY(6px);
      }
      to {
        opacity: 1;
        transform: translateY(0);
      }
    }

    /* 话末到达横幅浮入 */
    .reader-scroll[data-mode='vertical-continuous'] ~ .reader-chapter-next {
      animation: reader-banner-appear 1ms var(--ease-out) both;
      animation-timeline: --reader-scroll;
      animation-range: calc(100% - 180px) 100%;
    }
  }
}
```

**双轨架构不变量（Dual-Track Invariant）**：

1. **视觉归 CSS**：所有位移、变形与透明度动画由 CSS 滚动驱动接管；
2. **状态归 JS**：页码持久化（`useLastRead`）、图片预热（`preloadAround`）、路由对齐等领域状态必须留在 Composable，严禁废弃 JS 数据闭环；
3. **无障碍降级**：必须在 `@media (prefers-reduced-motion: no-preference)` 保护下执行动效，不支持的旧引擎由 JS 内联样式兜底。

---

## 4. 实验草案特性（Experimental / Stage 1-2）

> 这些特性**不能用于生产**，但值得持续追踪。当浏览器支持度达到 Baseline 时，可以按照下方用法示例直接落地。

### 4.1 CSS `if()` 行内条件函数

**规范阶段**：Values and Units Level 5 · Stage 1  
**Chrome**：137+ 需开 `chrome://flags/#enable-experimental-web-platform-features`  
**参考**：[张鑫旭 CSS if 函数](https://www.zhangxinxu.com/wordpress/2025/07/css-if-function/)

**当前阻碍（2026-08）**：

- LightningCSS / Oxlint / Vite 解析器遇到 `if(...)` 报错，`vp check` 无法通过；
- 跨浏览器支持为 0，无法渐进增强。

**预期用法（等规范落地后）**：

```css
/* 单属性条件判断，不再需要多个选择器 */
.btn {
  padding: if(style(--size: compact) ? 0.25rem 0.5rem: 0.5rem 1rem);
  font-size: if(style(--size: compact) ? var(--text-xs): var(--text-sm));
}

/* 搭配 @property 定义枚举类型属性 */
@property --size {
  syntax: 'compact | default | large';
  initial-value: default;
  inherits: true;
}
```

**升级触发条件**：

- [ ] Vite / LightningCSS 更新至支持 `if()` 语法解析
- [ ] Chrome / Firefox / Safari 均达到正式版稳定支持
- [ ] `vp check` 通过

---

### 4.2 CSS `@function` 自定义函数

**规范阶段**：CSS Functions Module Level 1 · Stage 2  
**Chrome**：139+ Canary 才可开启  
**参考**：[张鑫旭 CSS @function at-rules](https://www.zhangxinxu.com/wordpress/2025/09/css-function-at-rules/)

**预期用法（等规范落地后）**：

```css
/* 定义一个流体字体大小函数 */
@function --fluid(--min, --max, --from: 360px, --to: 1440px) {
  result: clamp(
    var(--min),
    calc(
      var(--min) + (var(--max) - var(--min)) * ((100vw - var(--from)) / (var(--to) - var(--from)))
    ),
    var(--max)
  );
}

/* 使用 */
h1 {
  font-size: --fluid(1.5rem, 3rem);
}

/* 定义图书馆特有的阴影合成函数 */
@function --elevation(--level) {
  result:
    0 calc(var(--level) * 1px) calc(var(--level) * 3px) var(--shadow-color-direct),
    0 calc(var(--level) * 4px) calc(var(--level) * 12px) var(--shadow-color-ambient);
}

.card {
  box-shadow: --elevation(2);
}
```

**升级触发条件**：

- [ ] 规范 Stage 4 / W3C CR 阶段
- [ ] 三大内核正式版全支持

---

### 4.3 `@container style(...)` 样式容器查询（范围语法）

**规范阶段**：CSS Containment Level 3 · 部分落地  
**可用**：Chrome 111+ (基础), Firefox 151+ (基础), Safari 18+  
**参考**：[张鑫旭 CSS style container range syntax](https://www.zhangxinxu.com/wordpress/2025/12/css-style-container-range-syntax/)

**基础用法（已可用部分，基于 CSS 自定义属性）**：

```css
/* 父级容器 */
.card-grid {
  container-type: inline-size style;
  --density: default;
}

/* 根据父级 CSS 变量值调整子组件布局 */
@container style(--density: compact) {
  .book-card {
    padding: var(--space-2);
    font-size: var(--text-xs);
  }
}
```

**Range 语法（待全面落地）**：

```css
/* 数值范围查询，目前仅限原生 CSS 属性，自定义变量支持度不稳定 */
@container style(1em < font-size < 2em) {
  /* ... */
}
```

### 4.4 CSS `progress()` 数学函数

**规范阶段**：CSS Values and Units Module Level 5 · Standard Track (`web-features:progress-function`)  
**可用**：Chrome 138+ (2025-06) · Edge 138+ · Firefox 155+ (2026-09) · Safari 26+ (2025-09) · Opera 122+  
**参考**：

- MDN: [progress()](https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Values/progress)
- [张鑫旭 CSS progress() 函数简介](https://www.zhangxinxu.com/wordpress/2025/12/css-progress-function/)

**语法与原理**：
`progress(<value>, <start>, <end>)` 计算公式为 `(<value> - <start>) / (<end> - <start>)`，自动返回 `0~1` 的无量纲纯数值。

```css
/* 基础数值映射：返回 0.3 */
width: calc(100px * progress(300, 0, 1000));

/* 结合容器宽度 cqw 与 calc() 实现响应式动态尺寸 */
.card img {
  width: calc(100px + 200px * progress(80cqw, 150px, 800px));
}

/* 结合 CSS 变量与 clamp */
.progress-fill {
  transform: scaleX(progress(var(--cached), 0, var(--total)));
}
```

**纸间落地架构与渐进增强范式（`AppProgressBar.vue`）**：

1. **统一数据契约**：视图层统一以 CSS Custom Property `--progress: 0.xx`（0~1）作为单一事实源；
2. **合成层渲染**：内部由合成线程执行 `transform: scaleX(var(--progress, 0))` 渲染，具备 0 Reflow 的极佳性能；
3. **平滑承接**：已完全兼容原生 `progress()` 与 `@property` 规范，实现跨版本平滑渐进增强。

---

## 5. 升级路线图（Roadmap）

### 已落地（2026-08 / 2026-09）

- [x] **`@property` 整合到 `tokens.css`**：已为 `--mask-left`、`--mask-right` 声明 `<length>` 类型，支持渐变遮罩的纯 CSS 平滑数值插值；
- [x] **CSS Grid 复合轨道无级折叠动效**：已在 `TagFilterBar.vue`（标签溢出抽屉）与 `ImportPanel.vue`（移动端收录面板）落地，消除跳版与 `scrollHeight` 胶水代码；
- [x] **色彩双层回退基线固化**：坚持 `#hex` + `oklch()` 双层声明，防御低版本引擎的颜色丢失问题；
- [x] **`AppProgressBar.vue` 统一 CSS 进度条架构**：全站进度条收敛为 CSS 变量 `--progress` + GPU 合成层驱动，彻底根治缓存进度回退与时序竞争闪烁；

### 短期（预计 2026 Q4，等浏览器 Baseline 达标）

- [ ] **`::details-content` 落地 Baseline**（Safari 18.4+ 已支持，等 Firefox 144+ 稳定版）：目前项目已有实现，届时可统一全站原生 `<details>` 展开；

### 中期（预计 2027，等规范 Stage 3-4）

- [ ] **CSS `@function`**：当 Vite/LightningCSS 支持且三大内核跟进后，可将项目中的 `clamp()` 组合、阴影合成等提取为命名 CSS 函数，彻底消除重复代码；
- [ ] **`@container style(...)` 范围语法稳定后**：考虑将 `ImportPanel` 的密度模式（桌面/移动）从容器尺寸查询演进为样式查询，实现更语义化的主题化组件；

### 长期（等 CSS `if()` 与 `progress()` 落地 Baseline）

- [ ] **CSS `if()` 行内条件**：届时部分类名状态机（如 `is-active`、`is-invalid`）可以收敛为纯 CSS 声明，减少 Vue 模板绑定中的类名拼接逻辑；
- [ ] **原生 CSS `progress()` 数学函数**：当主流引擎全量支持后，可将进度换算彻底移交 CSS 引擎就地计算（`progress(var(--cached), 0, var(--total))`）。

---

## 6. 参考资源

### 规范与 MDN

- [MDN CSS 参考](https://developer.mozilla.org/en-US/docs/Web/CSS)
- [W3C CSS Working Group 草案](https://www.w3.org/Style/CSS/current-work)
- [Can I Use](https://caniuse.com)
- [Baseline (web-platform-dx)](https://web.dev/baseline)

### 张鑫旭技术博客（本次调研参考）

| 特性                               | 文章                                                                              |
| :--------------------------------- | :-------------------------------------------------------------------------------- |
| CSS `progress()` 函数              | https://www.zhangxinxu.com/wordpress/2025/12/css-progress-function/               |
| CSS `if()` 函数                    | https://www.zhangxinxu.com/wordpress/2025/07/css-if-function/                     |
| `@container scroll-state(...)`     | https://www.zhangxinxu.com/wordpress/2025/08/css-container-scroll-state/          |
| `@container` 容器查询基础          | https://www.zhangxinxu.com/wordpress/2022/09/css-container-rule/                  |
| DOM `CSSStyleSheet`                | https://www.zhangxinxu.com/wordpress/2026/01/dom-cssstylesheet/                   |
| `@container style(...)` 范围语法   | https://www.zhangxinxu.com/wordpress/2025/12/css-style-container-range-syntax/    |
| CSS Nesting & `@scope`             | https://www.zhangxinxu.com/wordpress/2024/03/css-nesting-scope-rules/             |
| CSS `@function` at-rules           | https://www.zhangxinxu.com/wordpress/2025/09/css-function-at-rules/               |
| `light-dark()` 色彩函数            | https://www.zhangxinxu.com/wordpress/2026/06/css-color-theme-light-dark-function/ |
| `<details>` & `::details-content`  | https://www.zhangxinxu.com/wordpress/2025/11/css-details-target-content-open/     |
| `interpolate-size` & `calc-size()` | https://www.zhangxinxu.com/wordpress/2024/11/css-calc-interpolate-size/           |
| `scroll-timeline` 滚动驱动动画     | https://www.zhangxinxu.com/wordpress/2024/08/css-scroll-timeline/                 |

### 前端侦探 / CodePen 参考

| 特性 / 技巧                 | 资源                                                                                           |
| :-------------------------- | :--------------------------------------------------------------------------------------------- |
| CSS 拟真非线性进度条        | https://mp.weixin.qq.com/s/LIDMxVSqBhT1RX41WnCKHg （前端侦探《CSS 如何模拟“真实”的进度条？》） |
| 拟真进度条交互 CodePen Demo | https://codepen.io/xboxyan/pen/emOmazz                                                         |
