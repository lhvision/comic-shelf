---
timestamp: 2026-09-12T11-34-09Z
slug: search-commands
---

# 纸间 · 搜索框快捷指令中枢与命令胶囊（Command Chip）独立评审与打磨记录

- **评审执行方法**：`Method: dual-agent (Assessment A: Design Director Critique, Assessment B: detect:slop)`
- **目标组件**：
  - `src/components/library/SearchCommandChip.vue`
  - `src/components/library/SearchCommandMenu.vue`
  - `src/composables/useSearchCommands.ts`
  - `src/views/LibraryView.vue`
- **日期**：2026-09-12
- **评审总监评分**：初始 22/40（存在 3 项实质 P1 缺陷）-> 照单打磨修复后提升至 38/40

---

## 1. 独立设计总监（Design Director）初始检出缺陷

### 🔴 [P1-1] 中文输入法（IME）合成态冲突导致输入劫持与键盘陷阱

- **问题**：`handleKeydown` 未防范 `e.isComposing || e.keyCode === 229`，导致用户使用拼音输入法敲击候选词时被强行拦截并误触发快捷指令。
- **修复**：在 `useSearchCommands.ts` 的 `handleKeydown` 入口处设立 IME 安全守卫，在合成态期间绝不拦截事件。

### 🔴 [P1-2] Escape 按键层级越权导致毁灭性全清

- **问题**：在台词搜索模式下按下 `Escape`，系统无差别调用 `clearCommand()` 抹杀输入框长句并退出命令模式，导致 `LibraryView.vue` 的关闭下拉逻辑沦为死代码。
- **修复**：实现三级阶梯式退出（Cascading Dismiss）：
  1. 浮层展开时：放行交由外部先关闭浮层；
  2. 输入框有文字时：按 Escape 仅清空文本，保留命令胶囊；
  3. 输入框为空且无浮层时：按 Escape 或 Backspace 才退出命令胶囊模式。

### 🔴 [P1-3] `<label>` 元素非法嵌套多重交互控件与读屏器 Accessible Name 污染

- **问题**：搜索框外层使用 `<label class="search-field field">` 嵌套了胶囊关闭按钮、以图搜图按钮和文件上传控件，违反 W3C HTML 规范并导致读屏器把所有按钮提示拼进输入框标题。
- **修复**：将容器重构为 `<div class="search-field field" role="search">`，在内部 `<input>` 上显式标注 `aria-label="搜索书架藏书或输入 / 唤出快捷命令"`，胶囊关闭按钮绑定 `@click.stop`。

### 🟡 [P2 优化项落实]

1. **触控目标扩展**：在 `SearchCommandChip.vue` 的 `.chip-clear-btn` 挂载 `::before` 伪元素并设置 `inset: -10px`，触控区域从 26px 扩展至 44px（符合 WCAG 2.5.5 与 Apple HIG 标准）；
2. **图标语义差异化**：新增单源原子图标 `IconMessageSquare.vue`，将台词胶囊的放大镜图标替换为气泡对白图标，消除与搜索框主放大镜并列的视觉冗余；
3. **WAI-ARIA Listbox 契约修正**：将 `role="listbox"` 下沉至 `.menu-list`，确保其直接子元素全为 `role="option"`；修复空结果时 `aria-activedescendant` 悬空 Bug；
4. **键盘导航视口跟随**：在 `SearchCommandMenu.vue` 中添加 `focusedIndex` 监听器与 `scrollIntoView({ block: 'nearest' })`，保障长选单无障碍可见；
5. **小屏占位符优化**：精简命令占位符至紧凑版（`检索分镜（至少2字）…`），防止 360px 屏幕横向挤压截断。
