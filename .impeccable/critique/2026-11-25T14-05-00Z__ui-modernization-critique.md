# 纸间 Paper Room 前端样式与交互重构 — Impeccable 隔离评审快照

> **评审上下文**：独立 `Design Director` 子代理（会话 `5affea97-61ef-4235-b390-ddef9abe292e`）基于 `critique-rubric.md` 与 `DESIGN_NOTES.md` 执行隔离代码审查。

## Design Health Score（评审基线：28 / 40）

| #   | Heuristic                       | Score (0–4) | Key Issue                                                                                                      |
| --- | ------------------------------- | ----------- | -------------------------------------------------------------------------------------------------------------- |
| 1   | Visibility of System Status     | 3           | `CreateComicView` 提交禁用缺原因提示；`ReaderSettingsPanel` 作用域重复报态                                     |
| 2   | Match System / Real World       | 3           | `CreateComicView` 残留 `Local Workshop / 自建工坊` 英文眉题与括号标签                                          |
| 3   | User Control and Freedom        | 3           | `DetailActionBar` 自定义 `#trigger` 丢失下拉菜单键盘接管                                                       |
| 4   | Consistency and Standards       | 2           | `AppDropdown` 无 `v-model` 时点击后误入选中态打勾；`AppButton` 高特异度覆写业务样式；`.btn-md` 实高低于 44px   |
| 5   | Error Prevention                | 3           | `AppDropdown` 动作菜单误打 `✓` 易误导用户以为危险动作已勾选                                                    |
| 6   | Recognition Rather Than Recall  | 2           | `DetailActionBar` 更多按钮缺 ARIA 属性；`AppHeader` 移动端纯图标缺 `aria-label`；`GateSecretForm` 缺 `<label>` |
| 7   | Flexibility and Efficiency      | 3           | `DetailActionBar` 下拉菜单缺 `ArrowDown`/`ArrowUp` 键盘直达                                                    |
| 8   | Aesthetic and Minimalist Design | 3           | 暗室浅色系统模式下 `--accent`/`--warning` 小字对比度跌破 4.5:1；`PageIndexGrid` 窄屏截断                       |
| 9   | Error Recovery                  | 3           | `CreateComicView` 禁用提交时未提示缺项                                                                         |
| 10  | Help and Documentation          | 3           | 移动端纯图标按钮可读性不足                                                                                     |

## 本轮照单打磨闭环记录（Polish Resolution）

收到上述隔离评审后，已在同轮完成以下 **5 项 P1 缺陷** 与 **4 项 P2 体验项** 的定向修复：

1. **P1-1 `AppDropdown` 动作菜单态隔离与 `#trigger` 键盘/ARIA 透传**：
   - `AppDropdown.vue` 增加 `hasModelBinding` 与 `selectable` 判定，无 `v-model` 时点击菜单项不再篡改本地 `modelValue`，彻底消除「移除本地缓存…」误打 `✓` 勾；
   - `#trigger` 暴露 `triggerAttrs`（`aria-haspopup` / `aria-expanded` / `aria-controls` / `onKeydown`），并在 `DetailActionBar.vue`「更多」按钮透传绑定。
2. **P1-2 阅读器暗室专属高对比 Token（WCAG AA ≥ 4.5:1）**：
   - `tokens.css` 暗室区新增 `--reader-accent: oklch(0.71 0.15 38)` 与 `--reader-warning: oklch(0.78 0.13 78)`；
   - `ReaderSettingsPanel.vue`、`ReaderFilmstrip.vue`、`ReaderHud.vue`、`ReaderEndCard.vue` 暗室小字前景已全部切换。
3. **P1-3 `ComicCard` / `AppChip` 交互嵌套解除与减弱动效修复**：
   - `ComicCard.vue` 改用 `.card-shell` + `.card-link::after` 扩展链接结构，解除 `<a>` 内嵌套 `<FavoriteButton>` 与 `.match-stamp`；修复 `@media (prefers-reduced-motion: reduce)` 特异度，同步重置 `.card-shell`、`.deck-leaf` 与 `.cover-front`；
   - `TagFilterBar.vue` 移除 `removable` 芯片上冗余的 `@click="removeTag(tag)"`，消除 `role="button"` 嵌套删除按钮。
4. **P1-4 `AppButton` 作用域特异度收敛与 44px 触控底线**：
   - `main.css` 将 `.btn` `position: relative` 下沉至 `@layer components`（不压过业务 scoped 定位），并将 `.btn-md` 恢复为 `min-height: var(--control-md)`（44px）；
   - `AppButton.vue` 在 `@media (pointer: coarse)` 下将 44px `::before` 扩展至 `.btn-xs` 与 `.btn-sm`；
   - `SegmentedTabs.vue` 在 `@media (pointer: coarse)` 下直接提升选项 `min-height: var(--control-md)`，规避 `overflow-x: auto` 对 `::before` 的裁切；
   - 清理 `ReaderEndCard.vue` `.rec-detail-btn`、`ReaderSettingsPanel.vue` `.scope-jump-link`（改用 `variant="soft"`）与 `LibraryView.vue` `.camera-btn` 的冲突覆写。
5. **P1-5 `PageIndexGrid` 窄屏防截断**：
   - 移除 120px 窄折叠卡内重复的 `.fold-card-hint`，并恢复 `max-width: 680px` 下 `aspect-ratio: auto; min-height: 100%;`。
6. **P2 收口**：
   - `AppHeader.vue` 在 `1024px` 提前隐退 `.header-note` 并补齐 `aria-label`；
   - `GateSecretForm.vue` 补充 `.visually-hidden` `<label for="gate-secret">`；
   - `DiscoveryCard.vue` 对齐 `var(--z-card-stamp)` 并补全 `@media (hover: hover)` 与 `prefers-reduced-motion`；
   - `CreateComicView.vue` 清除 `Local Workshop / 自建工坊` 英文 Eyebrow 与字段英文括号后缀。
