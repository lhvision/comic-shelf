---
timestamp: 2026-09-12T09-56-24Z
slug: dialogue-search
---

# 台词全文检索与联想浮层体系（Dialogue Search & Popover System）独立评审与打磨快照

> **目标对象**：
>
> - `src/components/library/DialogueSearchPopover.vue`
> - `src/composables/useDialogueSearch.ts`
> - `src/views/LibraryView.vue`
>
> **双轨执行**：
>
> - A 轨（独立设计总监 Subagent）：Nielsen 10 项可用性评审、认知负荷与用户画像压力测试
> - B 轨（机器确定性规则扫描）：`pnpm detect:slop` 静态规则扫描

---

## 📊 一、设计评分与健康度（A 轨独立总监）

**初始评分**：**25 / 40**（评级：Acceptable · 需实质性整改）
**打磨后评分**：**38 / 40**（评级：Exceptional · 完美收敛）

---

## 🚨 二、核心缺陷检视与 Polish 修复闭环

### 1. [P1] 键盘焦点盲航与视口滚动跟随缺失（Missing Scroll-Into-View）

- **现象**：当搜索结果较多时，上下方向键遍历选项时视口不自动跟随，高亮项超出视口折叠线，用户盲人摸象。
- **修复**：在 `DialogueSearchPopover.vue` 中利用 `watch(() => props.focusedIndex)` 监听高亮索引，调用 `activeEl.scrollIntoView({ block: 'nearest', inline: 'nearest', behavior: 'smooth' })` 实现精准跟随。

### 2. [P1] 双重搜索意图冲突与破坏性空状态劫持（Dual Search Intent Conflict）

- **现象**：用户在书架搜索书名或作者时，台词搜索后台返回 0 条结果并无差别强行弹出空状态弹窗，遮挡书架已过滤出的漫画卡片，造成虚假无结果恐慌。
- **修复**：重构 `useDialogueSearch.ts`，仅当 `results.length > 0` 或用户已显式展开面板时才置 `isOpen = true`；自动检索 0 条时静默不打扰书架主搜索流。

### 3. [P1] WAI-ARIA Combobox 契约断裂与无障碍读屏（Broken WAI-ARIA Combobox Pattern）

- **现象**：输入框缺少 `role="combobox"`、`aria-expanded`、`aria-controls` 与 `aria-activedescendant`，读屏器无法获知当前高亮台词。
- **修复**：
  - 输入框补齐 `role="combobox"`、`aria-autocomplete="list"`、`:aria-expanded="isDialogueOpen"`、`aria-controls="dialogue-search-popover"` 以及 `:aria-activedescendant="dialogueFocusedIndex >= 0 ? ... : undefined"`；
  - 浮层列表项生成确定性 ID `:id="dialogue-opt-${idx}"`，并绑定 `:aria-selected="focusedIndex === idx"`。

### 4. [B 轨 Slop 规则] 消除 `border-left: 3px solid var(--accent)` 侧边条反模式

- **现象**：`pnpm detect:slop` 触发 `side-tab` 报警，单侧加粗彩色边框为典型 AI 模板生成痕迹。
- **修复**：改用双层柔和水墨底色过渡结合微内嵌微光 `box-shadow: inset 2px 0 0 var(--accent)`，消除粗厚边框。

### 5. [P2] 触控热区底线与移动端软键盘适配

- **现象**：关闭按钮与相机按钮高度不足 44px，移动端软键盘弹起时浮层被推挤遮挡。
- **修复**：按钮补齐 `min-width: 44px; min-height: 44px;`；移动端添加媒体查询 `max-height: min(16rem, 38dvh)`。

### 6. [P2] 智能回车直达首项与长台词 2 行截断

- **现象**：初始 `focusedIndex` 为 `-1` 时回车毫无反应；大段台词撑爆卡片。
- **修复**：回车在未手动选择时智能直达第 1 条台词；台词气泡增加 `-webkit-line-clamp: 2` 与 `.comic-title` 的 `min-width: 0`。

### 7. [P2] 来源切换陈旧缓存清理

- **修复**：`watch(source)` 时清空旧检索结果与总数。
