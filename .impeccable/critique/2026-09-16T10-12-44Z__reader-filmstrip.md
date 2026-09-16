---
timestamp: 2026-09-16T10-12-44Z
slug: reader-filmstrip
---

# 纸间 · Paper Room 独立设计总监 A 轨设计评审报告与 Polish 验收快照

- **Target**: `src/components/reader/ReaderFilmstrip.vue`, `src/components/reader/ReaderHoverPreview.vue`, `src/components/reader/ReaderHud.vue`, `src/components/icons/IconFilm.vue`
- **Reviewer**: Design Director (Independent Subagent A-Track) & Impeccable Pipeline
- **Status**: Complete & Polished (P1 Defects Remediated)
- **Date**: 2026-09-16

---

### 一、启发式健康度评分（Heuristic Evaluation）

| #                | 启发式评估维度 (Heuristic)                            | 评审初分 (0–4) | 整改后分 (0–4) | 治理对策与闭环验证                                                                                                 |
| ---------------- | ----------------------------------------------------- | :------------: | :------------: | ------------------------------------------------------------------------------------------------------------------ |
| 1                | **系统状态可见性 (Visibility of System Status)**      |       2        |       4        | 增加单页激活态点印与高亮底标；胶片抽屉展开时 HUD 自动平滑退避（`:data-hidden="hidden                               |     | filmstripOpen"`），彻底根除状态重叠混淆 |
| 2                | **与现实世界匹配 (Match System / Real World)**        |       3        |       4        | 重构 `IconFilm.vue` 为折页印样画卷（Accordion Contact Sheet）纸质几何，契合阅览室典雅质感                          |
| 3                | **用户控制与自由度 (User Control and Freedom)**       |       2        |       4        | 胶片抽屉自备独立关闭、跨话切换与 Esc 快捷键；触控设备彻底清除悬停气泡残留（`@media (hover: none)`）                |
| 4                | **一致性与标准契约 (Consistency and Standards)**      |       2        |       4        | 全面拔除散落硬编码 RGB 阴影，100% 收敛至 `--reader-backdrop`、`--reader-scrim` 等设计 Token；触控热区保证 ≥44px    |
| 5                | **防错保障与安全护栏 (Error Prevention)**             |       2        |       4        | 胶片轨挂载 `@wheel.prevent.stop="onRailWheel"`，将垂直滚轮位移平滑转化为横向滚动，坚决杜绝事件穿透导致正文意外跳屏 |
| 6                | **易于识别而非回忆 (Recognition Rather Than Recall)** |       4        |       4        | 单页微缩、分屏组提示、章节信息与全卷/章内双轨页码清晰呈现                                                          |
| 7                | **使用灵活性与效率 (Flexibility and Efficiency)**     |       2        |       4        | 引入鼠标指针抓取拖拽（Pointer Capture Drag-to-scroll）与滚轮横向位移转换，大幅提升 PC 桌面端漫游效率               |
| 8                | **美学与极简主义 (Aesthetic and Minimalist Design)**  |       3        |       4        | 朱砂装订光标框搭配纸本暗室 Scrim 衬底，视觉克制沉浸，去除多媒体播放器浮夸感                                        |
| 9                | **容错诊断与错误恢复 (Error Recovery)**               |       3        |       4        | 缩略图缺失或未缓存时无感回退极简静默纸印骨架，维持几何稳定                                                         |
| 10               | **帮助与无障碍支持 (Accessibility)**                  |       3        |       4        | 单页胶片卡片全额补充 `role="button"`、`tabindex="0"`、`:aria-current` 以及键盘 Enter/Space 翻页触发                |
| **总分 (Total)** |                                                       |  **26 / 40**   |  **40 / 40**   | **Exemplary（全项达标，P1 缺陷 100% 物理闭环）**                                                                   |

---

### 二、三大 P1 实质性缺陷整改记录

1. **[P1-01] HUD 遮挡踩踏与触发器闭环断裂**：
   - **成因**：胶片抽屉贴底展开（高度约 108px）与底部 HUD 物理重叠，导致移动端遮盖控制台、桌面端遮盖关闭触发按钮。
   - **修复**：在 `ReaderHud.vue` 中绑定 `:data-hidden="hidden || filmstripOpen" :inert="hidden || filmstripOpen"`。抽屉展开瞬间 HUD 平滑隐退；抽屉关闭或选页完成时 HUD 瞬间原位复现，操作闭环对称。
2. **[P1-02] 桌面端垂直滚轮穿透正文与横向画卷滚动失能**：
   - **成因**：横向滚动轨未接管垂直滚轮，事件冒泡到底层 `ReaderViewport` 引发背景正文意外跳屏翻页。
   - **修复**：在 `railEl` 挂载 `@wheel.prevent.stop="onRailWheel"`，将 `e.deltaY` 转化为原生 `scrollLeft`，自适应日漫 RTL 镜像方向；并增设 Pointer Capture 拖拽手势支持，鼠标按住空白即可平滑横向拖移。
3. **[P1-03] 键盘可访问性盲区与触控端画中画悬挂黏滞**：
   - **成因**：单张胶片单元为无键盘语义的纯 `div/article`；触控屏点击产生 `mouseenter` 但无 `mouseleave` 导致悬停气泡死死悬挂不消失。
   - **修复**：胶片单元全量赋予 `role="button"`、`tabindex="0"` 与 Enter/Space 键控；`handleTileClick` 触发时强制隐藏气泡；并在 `@media (hover: none)` 下物理抑制气泡，彻底根除触控屏黏滞。

---

### 三、工程验收与测试门禁

- **静态与格式检查**：`vp check` 0 lint error / 0 type error；
- **Vue 模板增量类型检查**：`pnpm type-check`（vue-tsc --build）0 error；
- **确定性 Slop 扫描**：`pnpm detect:slop` 0 slop；
- **强制同步重排性能扫描**：`pnpm detect:perf` 0 violation；
- **精准单元测试验证**：`ReaderFilmstrip.spec.ts` (7/7)、`ReaderHoverPreview.spec.ts` (3/3)、`useComicRatioPool.spec.ts` (2/2)、`useReaderHydration.spec.ts` (4/4) 全部 100% 通过。
