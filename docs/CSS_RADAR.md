# CSS 前瞻技术雷达（CSS Foresight Radar）

> **用途**：纸间（Paper Room）项目的 CSS 现代特性追踪文档。记录已落地用法、降级方案与尚在草案中的特性，供下一次迭代直接查阅，无需重复读 MDN 或频繁回查张鑫旭老师专栏。
>
> **维护约定**：每次引入新 CSS 特性或发现规范升级时，更新对应条目的 **状态** 与 **用法片段**。

---

## 目录

1. [兼容性快查表](#1-兼容性快查表)
2. [已落地特性（Shipped）](#2-已落地特性shipped)
   - [2.1 `light-dark()` — 双相原子色彩令牌](#21-light-dark--双相原子色彩令牌审慎评估与双层回退守则)
   - [2.2 `color-mix(in oklab, ...)` — 色彩混合](#22-color-mixin-oklab---色彩混合)
   - [2.3 `@container (inline-size)` — 容器查询](#23-container-inline-size--容器查询)
   - [2.4 `@layer` — 级联层](#24-layer--级联层)
   - [2.5 CSS Nesting（`&`）](#25-css-nesting)
   - [2.6 `@property` — 带类型的自定义属性](#26-property--带类型的自定义属性)
   - [2.7 HTML Popover API (`popover="auto"`) — 原生顶层浮层体系](#27-html-popover-api-popoverauto--原生顶层浮层体系)
   - [2.8 CSS Anchor Positioning — 锚点定位与动态指示器](#28-css-anchor-positioning--锚点定位与动态指示器)
   - [2.9 全局 View Transitions API (`startViewTransition`) — 页面级丝滑过渡](#29-全局-view-transitions-api-startviewtransition--页面级丝滑过渡)
   - [2.10 `-webkit-line-clamp` 与多行文本截断体系（W3C 兼容规范与单源收敛）](#210--webkit-line-clamp-与多行文本截断体系w3c-兼容规范与单源收敛)
   - [2.11 `font-size-adjust` — 字形度量均衡与微型字阶渲染（Baseline 2024）](#211-font-size-adjust--字形度量均衡与微型字阶渲染baseline-2024)
   - [2.12 `srcset` 与 `sizes` — 响应式阶梯封面与多密屏幕自适应（HTML5/CSS 媒体管线）](#212-srcset-与-sizes--响应式阶梯封面与多密屏幕自适应html5css-媒体管线)
3. [渐进增强特性（Progressive Enhancement）](#3-渐进增强特性progressive-enhancement)
   - [3.1 `interpolate-size: allow-keywords` 与 CSS Grid 复合轨道](#31-interpolate-size-allow-keywords-与-css-grid-复合轨道)
   - [3.2 `::details-content` — 原生展开内容伪元素](#32-details-content--原生展开内容伪元素)
   - [3.3 `@container scroll-state(...)` — 滚动状态容器查询](#33-container-scroll-state---滚动状态容器查询)
   - [3.4 `scroll-timeline` 与 `view-timeline` — 滚动驱动动画](#34-scroll-timeline-与-view-timeline--滚动驱动动画dual-track-渐进增强架构)
   - [3.5 `popover="hint"` — 非互斥轻量浮层与多层叠加](#35-popoverhint--非互斥轻量浮层与多层叠加)
   - [3.6 `@container anchored(fallback)` — 锚点容器查询与小三角自适应翻转](#36-container-anchoredfallback--锚点容器查询与小三角自适应翻转)
   - [3.7 `Element.prototype.startViewTransition` — 局部作用域视图过渡](#37-elementprototypestartviewtransition--局部作用域视图过渡)
   - [3.8 Interest Invokers API (`interestfor`) — 声明式悬停意图交互](#38-interest-invokers-api-interestfor--声明式悬停意图交互)
4. [实验草案特性（Experimental / Stage 1-2）](#4-实验草案特性experimental--stage-1-2)
   - [4.1 CSS `if()` 行内条件函数](#41-css-if-行内条件函数)
   - [4.2 CSS `@function` 自定义函数](#42-css-function-自定义函数)
   - [4.3 `@container style(...)` 样式容器查询（范围语法）](#43-container-style-样式容器查询范围语法)
   - [4.4 CSS `progress()` 数学函数](#44-css-progress-数学函数)
   - [4.5 CSS 动态鼠标跟随锚点（Mouse-Follow Anchor）](#45-css-动态鼠标跟随锚点mouse-follow-anchor)
   - [4.6 `text-fit` — 容器宽度文字自动适配（Stage 1-2 / Chrome 150+）](#46-text-fit--容器宽度文字自动适配stage-1-2--chrome-150)
5. [升级路线图（Roadmap）](#5-升级路线图roadmap)
6. [参考资源（MDN & 博客专栏）](#6-参考资源mdn--博客专栏)

---

## 1. 兼容性快查表

> 数据来源：MDN BCD + Can I Use，更新于 2026-09。

| 特性 / API                              |             Chrome              |             Firefox              |                Safari                 |                 规范状态 / Baseline                  |                        本项目落地状态                        |
| :-------------------------------------- | :-----------------------------: | :------------------------------: | :-----------------------------------: | :--------------------------------------------------: | :----------------------------------------------------------: |
| `light-dark()`                          |              123+               |               120+               |                 17.5+                 |                   ✅ Baseline 2024                   |      ⚠️ 审慎评估（保留 hex+oklch 双层回退，防色彩丢失）      |
| `color-mix(in oklab, ...)`              |              111+               |               113+               |                 16.2+                 |                   ✅ Baseline 2023                   |           ✅ 已落地（tokens.css / 柔和半透明色阶）           |
| `@container (inline-size)`              |              105+               |               110+               |                  16+                  |                   ✅ Baseline 2023                   |            ✅ 已落地（ImportPanel / 响应式侧栏）             |
| `@layer`                                |               99+               |               97+                |                 15.4+                 |                   ✅ Baseline 2022                   |            ✅ 已落地（main.css 顶层样式层级声明）            |
| CSS Nesting (`&`)                       |              120+               |               117+               |                 17.2+                 |                   ✅ Baseline 2024                   |                ✅ 已落地（全站 SFC 样式规范）                |
| `@property`                             |               85+               |               128+               |                 16.4+                 |                   ✅ Baseline 2024                   |           ✅ 已落地（tokens.css 渐变遮罩变量插值）           |
| **HTML Popover (`auto`/`manual`)**      |              114+               |               125+               |                  17+                  |                   ✅ Baseline 2024                   | ✅ 已落地（`AppPopover` / `AppDropdown` / `StoragePopover`） |
| **HTML Popover (`hint`)**               |              151+               |               153+               |                  ⏳                   |               🔶 Newly Available 2026                |          ✅ 渐进增强（`Tooltip.vue` 轻量气泡提示）           |
| **Interest Invokers (`interestfor`)**   |             130+🚩              |                ⏳                |                  ⏳                   |                   🧪 Experimental                    |   ✅ 渐进增强（`Tooltip.vue` 声明式属性 + JS 定时器兜底）    |
| **CSS Anchor Positioning API**          |              125+               |               147+               |                  26+                  |                ✅ Baseline 2025/2026                 |   ✅ 已落地（`AppPopover` / `Tooltip` / `SegmentedTabs`）    |
| **`@container anchored(fallback)`**     |              135+               |                ⏳                |                  ⏳                   |                   🧪 Experimental                    |   ✅ 渐进增强（`AppPopover` / `Tooltip` 小三角自适应翻转）   |
| **全局 View Transitions API**           |     111+<br>_(125+ types)_      |      144+<br>_(147+ types)_      |        18+<br>_(18.2+ types)_         |                ✅ Baseline 2024/2025                 |     ✅ 已落地（`useViewTransition.ts` / 跨页面路由推进）     |
| **`-webkit-line-clamp` / `line-clamp`** | 6+ (前缀)<br>_(Preview 无前缀)_ | 68+ (前缀)<br>_(Preview 无前缀)_ | 5+ (前缀)<br>_(18.2-18.3 误开已回退)_ | ✅ W3C 兼容事实标准（前缀）<br>⏳ 规范草案（无前缀） |     ✅ 已落地（`AppTextClamp.vue` / `main.css` 实用类）      |
| **`font-size-adjust`**                  |              127+               |     3+<br>_(92+ two-values)_     |      16.4+<br>_(17+ two-values)_      |                   ✅ Baseline 2024                   |    ✅ 渐进增强（微标 `--text-caption` 与多语言字形排版）     |
| **`srcset` / `sizes` (`w` 描述符)**     |      38+<br>_(34+ srcset)_      |               38+                |         9.1+<br>_(8+ srcset)_         |                   ✅ Baseline 2016                   |           📋 路线图（响应式阶梯封面分阶调度管线）            |
| **`sizes="auto"` (懒加载原生联动)**     |              126+               |               150+               |                  ⏳                   |               🔶 Newly Available 2026                |         📋 路线图（配合 `loading="lazy"` 自动槽位）          |
| **局部 Element-Scoped VT**              |              147+               |                ⏳                |                  ⏳                   |                      🧪 Stage 2                      |     ✅ 渐进增强（`useViewTransition.ts` 元素级门面封装）     |
| `interpolate-size: allow-keywords`      |              129+               |                ⏳                |                  ⏳                   |               🔶 Limited Availability                |         ✅ 已落地（TagFilterBar / ImportPanel 展开）         |
| `::details-content`                     |              131+               |               143+               |                 18.4+                 |               🔶 Limited Availability                |          ✅ 渐进增强（main.css 全局 details 动画）           |
| `scroll-timeline` / `view-timeline`     |              115+               |              111+🚩              |                18.0+⏳                |               🔶 Limited Availability                |             ✅ 已落地（ReaderView 读物双轨渲染）             |
| `@container scroll-state(...)`          |              133+               |                ❌                |                  ❌                   |                   🧪 Experimental                    |           ⚠️ LightningCSS 解析限制，降级为 VueUse            |
| `@container style(...)`                 |              111+               |               151+               |                  18+                  |                     🔶 有限支持                      |                 — 暂未采用（等范围语法成熟）                 |
| `CSSStyleSheet` (Constructable)         |               73+               |               101+               |                 16.4+                 |                   ✅ Baseline 2023                   |              ⚠️ 与 Vue SFC scoped CSS 模式冲突               |
| CSS `progress()` 数学函数               |              138+               |               155+               |                  26+                  |               🔶 Newly Available 2026                |    ✅ 渐进增强（以 `--progress` + `AppProgressBar` 承接）    |
| CSS 动态鼠标跟随锚点                    |              144+               |                ⏳                |                  ⏳                   |                      🧪 Stage 2                      |          📋 路线图（未来漫画阅读器局部高倍放大镜）           |
| **`text-fit`**                          |              150+               |                ❌                |                  ❌                   |                      🧪 Stage 2                      |         📋 路线图（未来阅读器顶栏长标题压缩防折行）          |
| CSS `if()` 行内条件                     |             137+🚩              |                ❌                |                  ❌                   |                      🧪 Stage 1                      |                  🚫 构建工具限制，暂不采用                   |
| CSS `@function`                         |             139+🚩              |                ❌                |                  ❌                   |                      🧪 Stage 2                      |                    🚫 过早引入，暂不采用                     |

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

---

### 2.5 CSS Nesting（`&`）

**MDN**：[CSS Nesting](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_nesting)  
**Baseline**：2024 (Chrome 120+, Firefox 117+, Safari 17.2+)

```css
.import-field {
  border: 1px solid var(--line);

  &:focus-within {
    border-color: var(--accent);
  }

  &.is-invalid:focus-within {
    border-color: var(--danger);
  }
}
```

---

### 2.6 `@property` — 带类型的自定义属性

**MDN**：[@property](https://developer.mozilla.org/en-US/docs/Web/CSS/@property)  
**Baseline**：2024 · Chrome 85+, Firefox 128+, Safari 16.4+  
**本项目落地状态**：✅ 已在 `src/styles/tokens.css` 落地

```css
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

.site-nav {
  transition:
    --mask-left var(--duration-2) var(--ease-out),
    --mask-right var(--duration-2) var(--ease-out);
}
```

---

### 2.7 HTML Popover API (`popover="auto"`) — 原生顶层浮层体系

**MDN**：[Popover API](https://developer.mozilla.org/en-US/docs/Web/API/Popover_API)  
**Baseline**：2024 · Chrome 114+, Firefox 125+, Safari 17+  
**参考**：[张鑫旭 JS原生HTML popover实现下拉菜单](https://www.zhangxinxu.com/wordpress/2024/01/js-html-popover-dropdown/)  
**本项目落地状态**：✅ 已在 `AppPopover.vue` / `AppDropdown.vue` / `StoragePopover.vue` / `ReaderPassPopover.vue` 落地

**核心原理与优势**：

1. **顶级渲染层（Top Layer）**：由浏览器将浮层提升至专有顶层，彻底解决父级容器 `overflow: hidden`、`contain: paint` 带来的像素硬截断与 `z-index` 无休止叠加冲突；
2. **原生失焦关闭（Light Dismiss）**：点击浮层外部空白或按下键盘 `Esc` 时，浏览器原生自动收起浮层，无需手动绑定 `document.addEventListener('click')` 全局监听；
3. **安全离散进出场过渡（Discrete Transitions & @starting-style）**：配合 `overlay` / `display` 的 `allow-discrete` 特性与 `@starting-style`，实现原生浮层 0 布局闪烁的平滑缩放淡入淡出。

**纸间生产落地范式（`AppPopover.vue`）**：

```html
<template>
  <div class="app-popover-root">
    <div class="app-popover-trigger">
      <slot :toggle="toggle" />
    </div>

    <div :id="popoverId" ref="popoverEl" popover="auto" class="app-popover-panel surface">
      <slot name="content" :close="closePopover" />
    </div>
  </div>
</template>
```

```css
.app-popover-panel {
  margin: 0;
  inset: auto;
  position: fixed;
  box-sizing: border-box;

  /* 进退场与离散动画 */
  opacity: 0;
  scale: 0.98;
  transition:
    opacity var(--duration-1) var(--ease-out),
    scale var(--duration-1) var(--ease-out),
    overlay var(--duration-1) var(--ease-out) allow-discrete,
    display var(--duration-1) var(--ease-out) allow-discrete;
}

/* 激活态（原生 :popover-open） */
.app-popover-panel:popover-open {
  opacity: 1;
  scale: 1;
}

/* 入场前初始帧 */
@starting-style {
  .app-popover-panel:popover-open {
    opacity: 0;
    scale: 0.96;
  }
}
```

---

### 2.8 CSS Anchor Positioning — 锚点定位与动态指示器

**MDN**：[CSS Anchor Positioning](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Anchor_positioning)  
**Baseline**：2025/2026 · Chrome 125+, Firefox 147+, Safari 26+  
**参考**：[张鑫旭 CSS 锚点定位 API 深入浅出](https://www.zhangxinxu.com/wordpress/2024/06/css-anchor-positioning-api/)  
**本项目落地状态**：✅ 已在 `AppPopover.vue` / `Tooltip.vue` / `SegmentedTabs.vue` 落地

**核心原理与优势**：

1. **九宫格声明式定位（`position-area`）**：彻底取代传统 JS 坐标重算与繁琐的 `anchor(top)` 手动计算，使用 `position-area: bottom span-right` 或 `top` 配合 `justify-self: anchor-center` 直观宣告相对锚点的相对方位；
2. **视口越界自适应翻转（`position-try-fallbacks`）**：声明 `position-try-fallbacks: flip-block, flip-inline`，当底部屏幕高度不足时由渲染引擎自动翻转到上方，0 布局抖动；
3. **物理滑动胶囊动效（`SegmentedTabs.vue`）**：利用 `anchor-name` 给当前激活项赋予锚点名，滑块指示器纯 CSS 绑定锚点四边，实现 0 JS 重排的 120Hz 满帧跟手滑动。

**纸间生产落地范式 A（`AppPopover.vue` 浮层锚定）**：

```css
.app-popover-trigger {
  anchor-name: --popover-uid;
}

.app-popover-panel {
  position: fixed;
  position-anchor: --popover-uid;
  position-area: bottom span-right;
  justify-self: anchor-center;
  position-try-fallbacks: flip-block, flip-inline, --custom-bottom-left;
  container-type: anchored;
}

/* 自定义回退策略（@position-try） */
@position-try --custom-bottom-left {
  position-area: bottom span-left;
  justify-self: start;
}

/* 锚点定位降级（旧浏览器） */
@supports not (anchor-name: --test) {
  .app-popover-panel {
    position: absolute;
    top: calc(100% + var(--space-1-5));
    left: 0;
  }
}
```

**纸间生产落地范式 B（`SegmentedTabs.vue` 纯 CSS 滑动胶囊指示器）**：

```css
/* 当前激活的 Tab 项被赋予锚点名 */
.segmented-tab.is-active {
  anchor-name: --tab-active;
}

/* 胶囊指示器基于锚点尺寸与位置直接插值定位 */
.segmented-indicator {
  position: absolute;
  position-anchor: --tab-active;
  inset: anchor(top) anchor(right) anchor(bottom) anchor(left);
  background: var(--paper-0);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-sm);
  transition:
    inset var(--duration-2) var(--ease-out),
    opacity var(--duration-1) var(--ease-out);
}
```

---

### 2.9 全局 View Transitions API (`startViewTransition`) — 页面级丝滑过渡

**MDN**：[View Transition API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API)  
**Baseline**：2024/2025 · Chrome 111+ (125+ types), Firefox 144+ (147+ types), Safari 18+ (18.2+ types)  
**参考**：[张鑫旭 View Transitions API 基础与 SPA 实践](https://www.zhangxinxu.com/wordpress/2024/08/view-transitions-api/)  
**本项目落地状态**：✅ 已在 `src/composables/useViewTransition.ts` / `src/router/index.ts` 落地

**核心原理与安全不变量**：

1. **共享封面形态插值（Shared Element Morph）**：书架卡片 `view-transition-name: comic-cover-active` 在跳转详情页 Hero 封面时，浏览器自动计算尺寸与坐标插值（神奇移动）；
2. **批量类名过渡（`view-transition-class`）**：针对网格多卡片批量形变，声明 `view-transition-class: book-card-transition`，使用 `::view-transition-group(.book-card-transition)` 统一定义伪元素动画，避免对每张卡片手写重复规则；
3. **类型状态机（`types`）**：调用 `document.startViewTransition({ update, types: ['forward'] })`，通过 CSS `:active-view-transition-type(forward)` 区分前后推进动画；
4. **安全边界红线（Invariant Rule 8）**：
   - 必须捕获 Promise 异常（`transition?.ready?.catch(() => {})`、`finished?.catch(() => {})`），防止快速切页触发 `AbortError` 崩溃；
   - **严格禁止在阅读器内部翻页/切话触发全局快照**（防止打断 GPU 滚动与文字亚像素模糊）；
   - 弹窗与微交互使用 Vue `<Transition>`，杜绝全屏快照。

---

### 2.10 `-webkit-line-clamp` 与多行文本截断体系（W3C 兼容规范与单源收敛）

**MDN**：[line-clamp](https://developer.mozilla.org/en-US/docs/Web/CSS/line-clamp) · [CSS Compatibility Specification](https://compat.spec.whatwg.org/#css-simple-aliases)  
**Baseline / 规范状态**：

- 前缀语法（`-webkit-line-clamp`）：✅ **全网事实标准（De-facto Standard）** · Chrome 6+ · Safari 5+ · Firefox 68+ (2019) · Edge 79+
- 无前缀标准（`line-clamp`）：⏳ **规范草案与实验阶段**（Chrome/Firefox 需开实验旗预览；Safari 18.2 误开后已在 18.4 移除）  
  **本项目落地状态**：✅ 已在 `src/components/AppTextClamp.vue` 与 `src/styles/main.css` 落地单源收敛

**为什么不盲目写标准属性 `line-clamp`**：

1. **历史倒逼的标准**：`-webkit-line-clamp` 虽然带着 `-webkit-` 前缀，但并不是 iOS 独占，而是 2010 年代 WebKit 时代留下的全网通用方案。现代 Firefox 甚至在 2019 年反向实现了 `-webkit-line-clamp` 与 `display: -webkit-box`；WHATWG / W3C 在《CSS 兼容性规范》中直接将这套组合拳列为所有浏览器内核必须实现的规范特性；
2. **VS Code 虚假警告根源**：VS Code CSS 语言服务机械化提示 `Also define the standard property 'line-clamp' for compatibility`，但由于无前缀标准目前并未在主流浏览器正式投产，若盲目在业务中双写 `line-clamp: N`，目前不仅无效，还可能在未来标准语法（包含 `continue: collapse` 和 `block-ellipsis`）发生变化时产生未定义行为；
3. **消除虚假告警**：在 `.vscode/settings.json` 中配置 `"css.lint.vendorPrefix": "ignore"` 消除噪音。

**纸间黄金截断组合拳（底层标准实现）**：

```css
/* 现代浏览器全内核 100% 稳定截断 */
display: -webkit-box;
-webkit-box-orient: vertical;
-webkit-line-clamp: 2;
overflow: hidden;
```

**工程落地与单源收敛守则**：

1. **Vue 视图层优先使用 `<AppTextClamp>`**：
   - 业务组件（如卡片标题、作者、简介）一律使用 `<AppTextClamp :lines="2" :text="item.title">`；
   - 优势：不仅自动处理跨浏览器 line-clamp，还结合了 `ResizeObserver` 仅在**真实发生截断**时才激活原生 HTML Popover + CSS Anchor Positioning 浮层，鼠标悬浮或 Tab 聚焦即可阅读全文，短文本 0 DOM 冗余；
2. **纯样式/静态 Canvas 视图使用全局实用类**：
   - 在 `src/styles/main.css` 提供了 `.line-clamp-1`、`.line-clamp-2`、`.line-clamp-3` 实用类（包含在 `@layer utilities` 中）；
   - 如 `HtmlCanvasCard.vue` 或纯静态 HTML 片段直接复用该实用类，严禁在业务组件 `<style scoped>` 中重复手写样板代码；
3. **属性级联顺序与过时前缀清理**：
   - **级联顺序**：当同一规则中前缀与标准属性并存时，严格遵循“前缀在前、标准在后”（如 `-webkit-backdrop-filter` 在前，`backdrop-filter` 在后；`-webkit-mask-image` 在前，`mask-image` 在后），确保现代标准引擎不会被私有前缀逆向覆盖；
   - **过时前缀清理**：彻底剔除 2011 年 iOS 5 遗留的 `-webkit-overflow-scrolling: touch`，自 iOS 13 起该属性已被官方移除并默认为原生惯性平滑滚动，全仓已作为死代码清理。

---

### 2.11 `font-size-adjust` — 字形度量均衡与微型字阶渲染（Baseline 2024）

**MDN**：[font-size-adjust](https://developer.mozilla.org/en-US/docs/Web/CSS/font-size-adjust)  
**Baseline**：2024 · Chrome 127+ (2024-07) · Firefox 3+ (92+ 双值语法) · Safari 16.4+ (17+ 双值语法)  
**参考**：[张鑫旭 不要搞混了，不是text而是CSS font-size-adjust属性](https://www.zhangxinxu.com/wordpress/2025/02/css-font-size-adjust/)  
**本项目落地决策**：✅ **渐进增强（已在设计规范确立，用于微型徽标 `--text-caption` (11px) 与多语言书名排版）**

**核心原理与度量体系**：

传统 Web 排版中，不同字体的字形高度与宽度比例截然不同（例如英文字体 Times 相比 Verdana 显得小一圈；中文字体楷体比苹方显得小一圈）。`font-size-adjust` 允许声明一个比率值，强制浏览器按指定度量微调字符视觉尺寸，使不同字体或回退字体展现出近乎一致的视觉字重。

支持 5 种字体度量（Font Metrics）模式：

- `ex-height`（默认）：基于小写字母 `x` 的高度占比调节；
- `cap-height`：基于大写字母高度调节；
- `ch-width`：基于数字 `0` 的宽度调节（单等宽数字排版极佳）；
- `ic-width`：基于中文字“水”的宽度调节；
- `ic-height`：基于中文字“水”的高度调节。

**三大核心价值与纸间落地场景**：

1. **突破 12px 最小渲染限制（取代 `transform: scale()` 反模式）**：
   - **痛点**：纸间设计系统中定义了极小徽标/角标 Token `--text-caption: 0.6875rem`（11px）。在过往前端实践中，由于桌面端浏览器有 12px 渲染限制，开发者常通过 `transform: scale(0.85)` 缩放，但这会导致外层盒模型尺寸不缩小、定位基准偏移、文本模糊与鼠标命中区错位；
   - **解法**：通过 `font-size-adjust: ic-width 0.6875` 或结合等宽数字 `font-size-adjust: ch-width 0.5`，可在不改变 `font-size` 真实计算值（保持盒模型几何稳定）的前提下，由文本渲染引擎直接将字形清晰微调至 11px 真实大小，0 变形、0 模糊。
2. **不影响 `em` 相对单位计算**：
   - `font-size-adjust` 仅调整字形的视觉渲染大小，并不改变元素的 `font-size` 计算值。因此，子元素或内联图标如果使用 `width: 1em; height: 1em;`，依然会严格锚定原始的 `font-size` 物理像素，不会产生意外的布局雪崩。
3. **中日西文混排与后备字体平滑过渡**：
   - 漫画车号、汉化组署名、多语言长书名常包含中/日/西文与特殊符号。当首选西文字体（如 `Avenir Next`）与中文字体（如 `Noto Sans SC`）切换时，统一声明 `font-size-adjust: from-font` 或指定 `ex-height`，可消除视觉下沉感与字形撕裂。

**代码范式（微标与紧凑徽章）**：

```css
.badge-caption {
  font-family: var(--font-mono);
  font-size: var(--text-xs); /* 12px 兜底 */
  font-size-adjust: ch-width 0.48; /* 视觉微调至 ~11px，保持盒模型完整 */
  line-height: var(--leading-tight);
}
```

---

### 2.12 `srcset` 与 `sizes` — 响应式阶梯封面与多密屏幕自适应（HTML5/CSS 媒体管线）

**MDN**：[HTMLImageElement: srcset](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/srcset) · [HTMLImageElement: sizes](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/sizes)  
**Baseline**：2016（全网事实标准）· Chrome 38+ · Firefox 38+ · Safari 9.1+  
**现代演进**：`sizes="auto"`（Chrome 126+, Firefox 150+）  
**参考**：[张鑫旭 响应式图片srcset全新释义sizes属性w描述符](https://www.zhangxinxu.com/wordpress/2014/10/responsive-images-srcset-size-w-descriptor/)  
**本项目落地决策**：📋 **纳入响应式媒体管线标准，指导封面派生图与阅读器高分屏分阶按需拉取**

**核心机制与关键原理**：

1. **`w` 描述符是物理像素，不是视口宽**：
   - 例如 `srcset="cover-360.webp 360w, cover-720.webp 720w"` 表示各张切片真实的物理像素宽度。
2. **`sizes` 是渲染预期的 CSS 槽位尺寸**：
   - 浏览器在解析 HTML 阶段，尚未执行 CSS 样式计算和重排，不知道图片最终在屏幕上会渲染成多大；
   - `sizes` 用于在 HTML 解析阶段提前告知浏览器该图片在不同断点下的预期槽位宽度（如 `sizes="(max-width: 680px) 50vw, 200px"`）；
   - 浏览器将 `sizes 计算宽度 × 设备像素比 (DPR)`，计算出所需的最小物理像素数，再从 `srcset` 中选择最适宜的一档资源。
3. **避坑红线：严禁只写 `w` 描述符而省略 `sizes`**：
   - **痛点复盘**：如果写了 `srcset="... 360w, ... 720w, ... 1440w"` 却漏写了 `sizes`，WHATWG 规范规定浏览器默认按 `sizes="100vw"` 处理；
   - **后果**：在桌面 2K/4K 屏幕上，即便书架卡片在界面上只占 180px 宽度，浏览器也会按 2000px+ 视口计算，导致强行下载最大的 1440w 超大原图，带来严重的带宽浪费与解码内存暴涨！必须始终配套编写精确的 `sizes`。
4. **现代前瞻：`sizes="auto"` 与懒加载原生联动**：
   - Chrome 126+ 与 Firefox 150+ 已支持 `sizes="auto"`；
   - 当图片带有 `loading="lazy"` 时，浏览器在图片即将进入视口前，会根据已完成排版的 DOM 真实布局宽度自动推导 `sizes`，彻底免去手动编写复杂媒体查询的成本。

**纸间生产落地蓝图（`ComicCard.vue` 封面标准契约）**：

```html
<!-- 书架卡片封面响应式声明范式 -->
<img
  :src="coverUrl"
  :srcset="`${coverUrlThumb} 360w, ${coverUrl} 720w`"
  sizes="(max-width: 680px) calc(50vw - 1.5rem), (max-width: 960px) 33vw, 200px"
  loading="lazy"
  decoding="async"
  alt="封面"
  class="comic-cover"
/>
```

---

## 3. 渐进增强特性（Progressive Enhancement）

### 3.1 `interpolate-size: allow-keywords` 与 CSS Grid 复合轨道

**MDN**：[interpolate-size](https://developer.mozilla.org/en-US/docs/Web/CSS/interpolate-size)  
**可用**：Chrome 129+（全局无级插值）；全主流浏览器（CSS Grid 复合轨道 `0fr ⇄ 1fr` 插值）  
**参考**：[张鑫旭 calc-size 与 interpolate-size](https://www.zhangxinxu.com/wordpress/2024/11/css-calc-interpolate-size/)

**作用**：允许浏览器在 `height: 0` 与 `height: auto` 之间进行纯数值插值，彻底消除 JS 测量 `scrollHeight` 的重排开销与异步闪烁。

**范式：标签流式溢出抽屉（`TagFilterBar.vue`）**：

```css
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
  overflow: clip;
}
```

---

### 3.2 `::details-content` — 原生展开内容伪元素

**MDN**：[::details-content](https://developer.mozilla.org/en-US/docs/Web/CSS/::details-content)  
**可用**：Chrome 131+, Firefox 143+, Safari 18.4+  
**参考**：[张鑫旭 details target-content-open](https://www.zhangxinxu.com/wordpress/2025/11/css-details-target-content-open/)

```css
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

---

### 3.3 `@container scroll-state(...)` — 滚动状态容器查询

**MDN**：[scroll-state containment](https://developer.mozilla.org/en-US/docs/Web/CSS/@container#scroll-state_container_queries)  
**可用**：Chrome 133+ · 其他浏览器❌  
**参考**：[张鑫旭 CSS container scroll-state](https://www.zhangxinxu.com/wordpress/2025/08/css-container-scroll-state/)

> ⚠️ **工具链限制（2026-09 现状）**：Vite 底层的 **LightningCSS** 解析器遇到 `scroll-state()` 语法时会抛出 `{ expected` 解析错误。目前仍以 VueUse `useScroll` 注入 `.has-scroll-*` 状态类作为稳定兜底。

---

### 3.4 `scroll-timeline` 与 `view-timeline` — 滚动驱动动画（Dual-Track 渐进增强架构）

**MDN**：[CSS Scroll-driven Animations](https://developer.mozilla.org/en-US/docs/Web/CSS/CSS_scroll-driven_animations)  
**可用**：Chrome 115+, Safari 18+ (部分) · Firefox 需开 Flag  
**参考**：[张鑫旭 不能落后，好好缕缕CSS滚动动画](https://www.zhangxinxu.com/wordpress/2024/08/css-scroll-timeline/)

**落地场景（`ReaderView.vue`）**：

```css
.reader-scroll {
  scroll-timeline-name: --reader-scroll;
  scroll-timeline-axis: block;
}

@supports (animation-timeline: scroll()) {
  .reader-view {
    timeline-scope: --reader-scroll;
  }

  .reader-view :deep(.reader-progress span) {
    transform: none;
    animation: reader-progress 1ms linear both;
    animation-timeline: --reader-scroll;
    transform-origin: 0 50%;
  }
}
```

---

### 3.5 `popover="hint"` — 非互斥轻量浮层与多层叠加

**MDN**：[popover="hint"](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Global_attributes/popover#hint)  
**可用**：Chrome 151+ (133+ partial), Firefox 153+ (149+ partial), Safari TP  
**参考**：[张鑫旭 HTML popover=hint 提示类型](https://www.zhangxinxu.com/wordpress/2025/07/html-popover-hint/)  
**本项目落地状态**：✅ 已在 `src/components/Tooltip.vue` 落地

**核心优势**：

- `popover="auto"` 在打开新浮层时会关闭先前的 auto 浮层（互斥）；
- `popover="hint"` 专为气泡提示设计，**可以在保持下拉菜单或对话框处于打开状态的同时叠加浮现**，绝不破坏前台已有的交互上下文。

```html
<!-- Tooltip 采用 popover="hint" -->
<span id="tip-1" popover="hint" role="tooltip" class="tooltip__tip"> 提示内容 </span>
```

---

### 3.6 `@container anchored(fallback)` — 锚点容器查询与小三角自适应翻转

**规范阶段**：CSS Anchor Positioning Level 2 · Experimental  
**可用**：Chrome 135+  
**参考**：[张鑫旭 CSS Anchor + Container Query 容器查询](https://www.zhangxinxu.com/wordpress/2025/12/css-anchor-container-query/)  
**本项目落地状态**：✅ 已在 `src/components/AppPopover.vue` 与 `src/components/Tooltip.vue` 落地

**解决的痛点**：
当锚定浮层声明了 `position-try-fallbacks: flip-block`（空间不足向上翻转）时，浮层本身位置倒转，但传统的 `::before` 伪元素小三角依然指向下方空气。通过把浮层声明为 `container-type: anchored`，CSS 引擎可在触发 fallback 时自动重置小三角边框与方位，**0 JS 监听**。

**生产标准写法（`Tooltip.vue` / `AppPopover.vue`）**：

```css
.tooltip__tip {
  container-type: anchored;
  position-try-fallbacks: flip-block, flip-inline;
}

/* 默认下方箭头：指向触发源 */
.tooltip__tip.side-top::before {
  bottom: -0.3rem;
  border-top: none;
  border-left: none;
  border-bottom: 1px solid var(--line-strong);
  border-right: 1px solid var(--line-strong);
}

/* 锚点容器查询：当发生垂直轴翻转 fallback 时，小三角与悬停安全桥自动颠倒指向 */
@container anchored (fallback: flip-block) {
  .tooltip__tip.side-top::before {
    bottom: auto;
    top: -0.3rem;
    border-bottom: none;
    border-right: none;
    border-top: 1px solid var(--line-strong);
    border-left: 1px solid var(--line-strong);
  }

  .tooltip__tip.side-bottom::before {
    top: auto;
    bottom: -0.3rem;
    border-top: none;
    border-left: none;
    border-bottom: 1px solid var(--line-strong);
    border-right: 1px solid var(--line-strong);
  }

  .tooltip__tip[data-side='top']::after {
    bottom: auto;
    top: calc(-1 * var(--space-2));
  }

  .tooltip__tip[data-side='bottom']::after {
    top: auto;
    bottom: calc(-1 * var(--space-2));
  }
}

/* 当发生水平侧边翻转 fallback 时（side-left ⇄ side-right） */
@container anchored (fallback: flip-inline) {
  .tooltip__tip.side-left::before {
    right: auto;
    left: -0.3rem;
    border-top: none;
    border-right: none;
    border-bottom: 1px solid var(--line-strong);
    border-left: 1px solid var(--line-strong);
  }

  .tooltip__tip.side-right::before {
    left: auto;
    right: -0.3rem;
    border-bottom: none;
    border-left: none;
    border-top: 1px solid var(--line-strong);
    border-right: 1px solid var(--line-strong);
  }

  .tooltip__tip[data-side='left']::after {
    right: auto;
    left: calc(-1 * var(--space-2));
  }

  .tooltip__tip[data-side='right']::after {
    left: auto;
    right: calc(-1 * var(--space-2));
  }
}
```

> 💡 **工程避坑守则（现行浏览器落地实录）**：
>
> 1. **物理分层（避免幽灵滚动条）**：当浮层内有超长文本需要滚动时，**绝对禁止**将 `overflow-y: auto` 施加在包含 `::before`（小三角）与 `::after`（安全桥）的根浮层容器上，否则负边距伪元素会被计入溢出计算导致短文本常驻垂直滚动条并裁切箭头；必须将滚动收敛至内部独立容器 `.tooltip__content`；
> 2. **动态横向对齐翻转感知（`actualAlign`）**：在不支持 `@container anchored (fallback: flip-inline)` 的现行浏览器中，若视口右缘碰撞触发 CSS Anchor 的 `flip-inline` 向左展开，模板静态绑定的 `align-start` 会将箭头错误留在最左端。必须在 JS `updateActualSide()` 中计算触发源中线相对浮层的位置偏移，动态切换 `actualAlign` 为 `end`（`right: 0.85rem`），确保箭头始终精准垂直对齐触发源。

---

### 3.7 `Element.prototype.startViewTransition` — 局部作用域视图过渡

**MDN**：[Element: startViewTransition()](https://developer.mozilla.org/en-US/docs/Web/API/Element/startViewTransition)  
**规范阶段**：CSS View Transitions Level 2 · Stage 2  
**可用**：Chrome 147+ (2026-04), Opera 131+ · Firefox / Safari 规划中  
**参考**：[张鑫旭 Element.prototype.startViewTransition 与 DOM 局部更新](https://www.zhangxinxu.com/wordpress/2026/07/sethtml-element-startviewtransition/)  
**本项目落地状态**：✅ 已在 `src/composables/useViewTransition.ts` 落地统一门面

**核心原理与优势**：

- `document.startViewTransition` 捕获整屏快照，在并发多个组件状态变更时容易冲突抢占；
- `element.startViewTransition(callback)` 仅在指定 DOM 子树容器（`transitionRoot`）建立过渡根，局部内容更新（如装订状态切换、红心点赞、单个卡片展开）极为丝滑且不阻塞外部视图。

**纸间使用门面（`useViewTransition.ts`）**：

```ts
import { useViewTransition } from '@/composables/useViewTransition'

const { withViewTransition } = useViewTransition()

// 指定局部 element 作用域
await withViewTransition(
  async () => {
    isFavorite.value = !isFavorite.value
    await nextTick()
  },
  { element: cardRef.value },
)
```

---

### 3.8 Interest Invokers API (`interestfor`) — 声明式悬停意图交互

**MDN**：[Using interest invokers](https://developer.mozilla.org/en-US/docs/Web/API/Popover_API/Using_interest_invokers)  
**规范阶段**：HTML / OpenUI Standard Track · Stage 2  
**可用**：Chrome 130+🚩 (Origin Trial) · Firefox / Safari 规划中  
**参考**：[张鑫旭 CSS interestfor 与 Invoker Target/Source 机制](https://www.zhangxinxu.com/wordpress/2026/03/css-interestfor-invoker-target-source/)  
**本项目落地状态**：✅ 渐进增强声明（`Tooltip.vue` 中声明 `interestfor` + `interest-delay`，旧环境由 Vue 事件定时器无缝兜底）

**核心机制**：

1. **声明式悬停关联**：`<button interestfor="tooltip-id">` 自动将悬停/聚焦意图派发至目标 popover，无需 JS 监听 mouseenter；
2. **隐式锚点（Implicit Anchor）**：目标浮层只需写 `position-area: top` 即可自动定位，无需手写 `position-anchor`；
3. **CSS 延迟与连环触发**：通过 `interest-delay: 100ms 150ms` 避免扫过时的误触，结合 `p:has(:interest-source) button { interest-delay-start: 0s }` 实现群组图标连续划过即时显现。

---

## 4. 实验草案特性（Experimental / Stage 1-2）

### 4.1 CSS `if()` 行内条件函数

**规范阶段**：Values and Units Level 5 · Stage 1  
**Chrome**：137+ 需开 Flag  
**参考**：[张鑫旭 CSS if 函数](https://www.zhangxinxu.com/wordpress/2025/07/css-if-function/)

---

### 4.2 CSS `@function` 自定义函数

**规范阶段**：CSS Functions Module Level 1 · Stage 2  
**Chrome**：139+ Canary  
**参考**：[张鑫旭 CSS @function at-rules](https://www.zhangxinxu.com/wordpress/2025/09/css-function-at-rules/)

---

### 4.3 `@container style(...)` 样式容器查询（范围语法）

**规范阶段**：CSS Containment Level 3 · 部分落地  
**可用**：Chrome 111+, Firefox 151+, Safari 18+  
**参考**：[张鑫旭 CSS style container range syntax](https://www.zhangxinxu.com/wordpress/2025/12/css-style-container-range-syntax/)

---

### 4.4 CSS `progress()` 数学函数

**规范阶段**：CSS Values and Units Module Level 5 · Standard Track  
**可用**：Chrome 138+, Firefox 155+, Safari 26+  
**参考**：[张鑫旭 CSS progress() 函数简介](https://www.zhangxinxu.com/wordpress/2025/12/css-progress-function/)

---

### 4.5 CSS 动态鼠标跟随锚点（Mouse-Follow Anchor）

**规范阶段**：CSS Anchor Positioning Level 2 · Stage 2  
**Chrome**：144+（支持 `position_after_layout` / 动态 point 锚点）  
**参考**：[张鑫旭 CSS 锚点定位实现鼠标跟随效果](https://www.zhangxinxu.com/wordpress/2025/11/css-anchor-position-mouse-follow/)

**原理与场景**：
通过在阅读器画卷容器监听鼠标移动并将坐标写入 CSS 自定义属性（`--mouse-x`、`--mouse-y`），结合纯 CSS 锚点或动态定位，实现**零 JS 重排循环的漫画高分辨率局部放大镜（Loupe Zoom）与悬浮检字预览卡片**。

```css
/* 鼠标跟随浮动放大镜模型 */
.manga-loupe {
  position: fixed;
  position-anchor: --cursor-anchor;
  position-area: top span-right;
  pointer-events: none;
  width: 180px;
  height: 180px;
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-3);
}
```

---

### 4.6 `text-fit` — 容器宽度文字自动适配（Stage 1-2 / Chrome 150+）

**MDN / 规范**：[CSS Text Module Level 5: text-fit](https://drafts.csswg.org/css-text-5/#text-fit-property)  
**规范阶段**：Stage 1-2（Experimental / Standard Track）  
**可用**：Chrome 150+ (2026-06-30), Opera 134+ · Firefox ❌ · Safari ❌  
**参考**：[张鑫旭 卧靠，这是好东西，CSS text-fit属性简介](https://www.zhangxinxu.com/wordpress/2026/08/css-text-fit/)  
**本项目落地决策**：📋 **实验草案储备；严格界定使用边界（限单体 HUD/工具栏长标题防折行，严禁侵入书架网格阵列）**

**语法与适配模型**：

```css
text-fit: <fit-type> <fit-target>;
```

- `<fit-type>`（缩放类型）：
  - `none`：不进行自动适配；
  - `grow`：放大文本以填满可用空间；
  - `shrink`：缩小过长文本以防止溢出。
- `<fit-target>`（适配目标）：
  - `per-line`：逐行单独计算，让每行各自填满容器；
  - `per-line-all`：所有行共同参与、强制填满；
  - `consistent`：整块文本按统一比例等比缩放，保持行间字号相对一致。

**纸间适配场景与设计红线**：

1. **强适用场景（阅读器顶栏 HUD & 紧凑工具栏）**：
   - **痛点**：在 `ReaderView` 顶栏或手机端窄屏下，部分长篇漫画书名（如《关于我转生变成史莱姆这档事...》）会换行并撑破沉浸式工具栏，以往必须手写 JS 测量或粗暴截断；
   - **解法**：在单行顶栏标题声明 `text-fit: shrink per-line`，配合 `white-space: nowrap`，超出容器宽度的长书名由浏览器底层排版引擎无级缩小至容纳，0 JS 开销且绝不折行。
2. **严苛禁止场景（书架卡片网格流）**：
   - **红线**：**绝对禁止在书架卡片网格的标题中使用 `text-fit: grow`**！
   - **根因**：网格排版依赖严整的视觉节律与统一字阶底线（`DESIGN_NOTES.md` §2.2 / `CONTEXT.md` 第 112 条）。如果短标题（如 4 个字）被放大至 36px，长标题被缩小至 12px，整个书架卡片网格的字号高低错落，视觉美感完全丧失。书架卡片标题坚决坚守 `<AppTextClamp :lines="2">` 截断 + 悬停 Tooltip 浮层。

**未来试验代码模型**：

```css
/* 阅读器 HUD 紧凑长标题自适应（前瞻草案） */
.reader-hud__title {
  font-size: var(--text-md);
  white-space: nowrap;
  overflow: hidden;
  text-fit: shrink per-line; /* 现代 Chrome 150+ 自动压缩防折行 */
}
```

---

## 5. 升级路线图（Roadmap）

### 已落地（2026-08 / 2026-09）

- [x] **`@property` 整合到 `tokens.css`**：已为 `--mask-left`、`--mask-right` 声明 `<length>` 类型，支持渐变遮罩的纯 CSS 平滑数值插值；
- [x] **HTML Popover API 与现代浮层基础设施（ADR 0004）**：全站下拉选单与卡片收敛至 `AppPopover.vue` / `AppDropdown.vue`，享受原生 Top Layer 与 Light Dismiss；
- [x] **CSS Anchor Positioning 九宫格与动态滑动指示器**：在 `AppPopover`、`Tooltip` 与 `SegmentedTabs` 落地纯 CSS 锚定与胶囊滑动动效；
- [x] **`@container anchored(fallback)` 箭头自适应反转**：`AppPopover` 与 `Tooltip` 补齐容器查询翻转规则，视口越界时小三角纯 CSS 倒转；
- [x] **`popover="hint"` 与 Interest Invokers 渐进增强**：`Tooltip.vue` 落地非互斥浮层规范与 `interest-delay` 延迟声明；
- [x] **全局与局域双轨 View Transitions (`useViewTransition.ts`)**：封装 `document` 与 `Element.prototype.startViewTransition` 门面，完善 Promise 异常拦截与 Rule 8 边界防护；
- [x] **CSS Grid 复合轨道无级折叠动效**：已在 `TagFilterBar.vue` 与 `ImportPanel.vue` 落地；
- [x] **色彩双层回退基线固化**：坚持 `#hex` + `oklch()` 双层声明；
- [x] **`AppProgressBar.vue` 统一 CSS 进度条架构**：全站进度条收敛为 CSS 变量 `--progress` + GPU 合成层驱动；
- [x] **`font-size-adjust` 字形度量规范确立**：确立在 `--text-caption` (11px) 微标与多语言混排中取代 `transform: scale()` 盒模型副作用的渐进增强方案。

### 短期（预计 2026 Q4，等浏览器 Baseline 达标）

- [ ] **`::details-content` 落地 Baseline**（Safari 18.4+ 已支持，等 Firefox 144+ 稳定版）：统一全站原生 `<details>` 折叠展开；
- [ ] **全量启用原生 `interestfor` 意图触发**：当 Chromium 与 WebKit 正式版稳定支持后，逐步减少 Tooltip 中的 `useTimeout` 定时器；
- [ ] **响应式阶梯封面（Responsive Stepped Covers）**：结合后端派生缩略图在 `ComicCard` 与详情页接入 `srcset` (`360w`, `720w`) + `sizes` 规范，配合 Chrome 126+/Firefox 150+ `sizes="auto"` 渐进增强。

### 中期（预计 2027，等规范 Stage 3-4）

- [ ] **漫画阅读器高倍放大镜（Mouse-Follow Loupe）**：基于 CSS 鼠标跟随锚点实现画卷高倍率检字与画质细节放大器；
- [ ] **CSS `@function`**：当 Vite/LightningCSS 支持且三大内核跟进后，将 `clamp()` 组合与阴影合成提取为命名 CSS 函数；
- [ ] **`@container style(...)` 范围语法稳定后**：将密度模式从尺寸查询演进为样式查询。

### 长期（等 CSS `if()`、`progress()` 与 `text-fit` 落地 Baseline）

- [ ] **CSS `if()` 行内条件**：收敛部分类名状态机为纯 CSS 声明；
- [ ] **原生 CSS `progress()` 数学函数**：将进度换算移交 CSS 引擎就地计算；
- [ ] **`text-fit` 阅读器顶栏长标题压缩**：当 Firefox 与 Safari 稳定支持后，在沉浸顶栏 HUD 落地 `text-fit: shrink per-line`。

---

## 6. 参考资源（MDN & 博客专栏）

### 规范与 MDN 官方文档

- [MDN CSS 参考](https://developer.mozilla.org/en-US/docs/Web/CSS)
- [MDN font-size-adjust 属性](https://developer.mozilla.org/en-US/docs/Web/CSS/font-size-adjust)
- [MDN HTMLImageElement: srcset 属性](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/srcset)
- [MDN HTMLImageElement: sizes 属性](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/sizes)
- [W3C CSS Text Module Level 5: text-fit 草案](https://drafts.csswg.org/css-text-5/#text-fit-property)
- [MDN Popover API](https://developer.mozilla.org/en-US/docs/Web/API/Popover_API)
- [MDN Using Interest Invokers](https://developer.mozilla.org/en-US/docs/Web/API/Popover_API/Using_interest_invokers)
- [MDN CSS Anchor Positioning](https://developer.mozilla.org/en-US/docs/Web/CSS/Guides/Anchor_positioning)
- [MDN View Transition API](https://developer.mozilla.org/en-US/docs/Web/API/View_Transition_API)
- [MDN Element.prototype.startViewTransition](https://developer.mozilla.org/en-US/docs/Web/API/Element/startViewTransition)
- [W3C CSS Working Group 草案](https://www.w3.org/Style/CSS/current-work)
- [Can I Use](https://caniuse.com)
- [Baseline (web-platform-dx)](https://web.dev/baseline)

### 张鑫旭技术博客专栏清单

| 特性分类     | 特性名称 / 主题                                         | 专栏文章链接                                                                             |
| :----------- | :------------------------------------------------------ | :--------------------------------------------------------------------------------------- |
| **排版字效** | CSS `font-size-adjust` 属性详解与字形度量               | https://www.zhangxinxu.com/wordpress/2025/02/css-font-size-adjust/                       |
| **排版字效** | CSS `text-fit` 容器宽度文本自动适配                     | https://www.zhangxinxu.com/wordpress/2026/08/css-text-fit/                               |
| **媒体管线** | 响应式图片 `srcset` 全新释义、`sizes` 属性与 `w` 描述符 | https://www.zhangxinxu.com/wordpress/2014/10/responsive-images-srcset-size-w-descriptor/ |
| **浮层交互** | CSS `interestfor` 与 Invoker Target/Source 机制         | https://www.zhangxinxu.com/wordpress/2026/03/css-interestfor-invoker-target-source/      |
| **浮层交互** | HTML `popover="hint"` 提示类型深度解析                  | https://www.zhangxinxu.com/wordpress/2025/07/html-popover-hint/                          |
| **浮层交互** | JS 原生 HTML `popover` 实现下拉菜单                     | https://www.zhangxinxu.com/wordpress/2024/01/js-html-popover-dropdown/                   |
| **锚点定位** | CSS Anchor Positioning API 深入浅出                     | https://www.zhangxinxu.com/wordpress/2024/06/css-anchor-positioning-api/                 |
| **锚点定位** | CSS Anchor + Container Query 容器查询                   | https://www.zhangxinxu.com/wordpress/2025/12/css-anchor-container-query/                 |
| **锚点定位** | CSS 锚点定位实现鼠标跟随效果                            | https://www.zhangxinxu.com/wordpress/2025/11/css-anchor-position-mouse-follow/           |
| **视图过渡** | `Element.prototype.startViewTransition` 与 DOM 局部更新 | https://www.zhangxinxu.com/wordpress/2026/07/sethtml-element-startviewtransition/        |
| **视图过渡** | View Transitions API 基础与 SPA 实践                    | https://www.zhangxinxu.com/wordpress/2024/08/view-transitions-api/                       |
| **现代函数** | CSS `progress()` 函数简介与应用                         | https://www.zhangxinxu.com/wordpress/2025/12/css-progress-function/                      |
| **现代函数** | CSS `if()` 行内条件函数                                 | https://www.zhangxinxu.com/wordpress/2025/07/css-if-function/                            |
| **滚动容器** | `@container scroll-state(...)` 状态感知                 | https://www.zhangxinxu.com/wordpress/2025/08/css-container-scroll-state/                 |
| **动画折叠** | `interpolate-size` 与 `calc-size()` 无级尺寸插值        | https://www.zhangxinxu.com/wordpress/2024/11/css-calc-interpolate-size/                  |
| **滚动驱动** | `scroll-timeline` 滚动驱动动画详解                      | https://www.zhangxinxu.com/wordpress/2024/08/css-scroll-timeline/                        |
| **色彩管理** | `light-dark()` 色彩函数实战                             | https://www.zhangxinxu.com/wordpress/2026/06/css-color-theme-light-dark-function/        |
| **原生折叠** | `<details>` & `::details-content` 伪元素                | https://www.zhangxinxu.com/wordpress/2025/11/css-details-target-content-open/            |
| **函数规则** | CSS `@function` at-rules 自定义函数                     | https://www.zhangxinxu.com/wordpress/2025/09/css-function-at-rules/                      |

### 前端侦探 / CodePen 参考

| 特性 / 技巧                 | 资源                                                                                           |
| :-------------------------- | :--------------------------------------------------------------------------------------------- |
| CSS 拟真非线性进度条        | https://mp.weixin.qq.com/s/LIDMxVSqBhT1RX41WnCKHg （前端侦探《CSS 如何模拟“真实”的进度条？》） |
| 拟真进度条交互 CodePen Demo | https://codepen.io/xboxyan/pen/emOmazz                                                         |
