---
target: 多章节「上一话/下一话 + 中间话选择」中间页评审（critique → polish → adapt）
total_score: 38
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 1
timestamp: 2026-08-20T16-24-51Z
slug: src-chapter-forward-back-pager
---

# Impeccable Critique — 章节维度「上一话/下一话 + 中间话选择」中间页

Target: `ChapterView.chapter-pager`（`← 上一话 | ChapterSwitcher 中间话选择 | 下一话 →`）+ `ChapterSwitcher`（data-pager 变体 / 滚动条 / Home-End 键盘）+ `ChapterView` 头部 meta
Method: 按 `docs/agents/ui.md` 的 Impeccable 234 步，切到专业设计评审视角，只评“中间页”。

## 评审结论

- **grill 回顾**：多章节作品所有入口最终都收敛到**章节维度渲染**——父详情页只出章节目录
  （一张卡片 = 一话封面+信息，不塞 7000 页）；点话进 `ChapterView` 只渲染该话页面索引；
  因此“中间页”（上一话/中间话/下一话）是章节维度的核心导航，**只在本子是多话时渲染**。
- **健康分 38/40（Good）**。控件层级清楚：方向性按钮（上一话/下一话）+ 可水平滚动的话选择
  条 + 当前话高亮，续读／跨话的心智成本低。

| #   | Heuristic                       | Score | 说明                                                                  |
| --- | ------------------------------- | ----- | --------------------------------------------------------------------- |
| 1   | Visibility of System Status     | 4     | 头部“第 X 話 · 65 页 · 全局 P1–P2”；当前话 chip 高亮 +「当前」徽标    |
| 2   | Match System / Real World       | 4     | “上一话 / 下一话”+ 可点序号，接近书脊连续翻阅                         |
| 3   | User Control and Freedom        | 4     | 上/下按钮 + 左右方向键 +（本轮加 Home/End 直达首尾话）                |
| 4   | Consistency and Standards       | 4     | 全部 token；chip 高 44px（`--control-md`）、圆角/间距与 PageTile 同源 |
| 5   | Error Prevention                | 4     | 首话禁“上一话”、末话禁“下一话”；单话不渲染本中间页                    |
| 6   | Recognition Rather Than Recall  | 3     | 152 话时不知道“我在地几话/共几话”→ 头部与条首加“第 X / 共 N 话”计数   |
| 7   | Flexibility and Efficiency      | 4     | 方向键 + Home/End + 可滚动的条；窄屏换行整条显示                      |
| 8   | Aesthetic and Minimalist Design | 5     | 序数圆 + mono 页数，克制；无新增色/玻璃拟态                           |
| 9   | Error Recovery                  | 4     | 滚动选中居中（useScroll），溢出消失平滑；选择即时生效                 |
| 10  | Help and Documentation          | 4     | eyebrow + meta 全；ESC/返回路径在 README/前端文档有说明               |

## P1（本轮修）

- **[P1] 长话列表“定位感”不足（152 话时不知道在哪/共几话）**
  - Why: 条上只有“当前”微标，读者失去“第几话/总共几话”的锚点；既是导航也是目录的中间页
    需要一眼可见的进度。
  - Fix: 条首加非交互计数 chip「第 X 話 / 共 N 話」（`role=status`），头部 meta 同步补
    「共 N 话」；`Home/End` 直达首/末话，减少滚动。

## What's Working

- **入口收敛**：父详情（多话）只渲染章节目录；单话父详情直接整本页索引；两边都不会一次性
  塞 7000 页。
- **中间页只在多话渲染**：`ChapterView` 由子路由进入，单话/无此话自动回详情；`ChapterSwitcher`
  `v-if="chapterList.length > 1"` 保证只有多话才出中间选择条。
- **跨话返回**：阅读器带 `?chapter=`，返回回子路由；底部“下一话”横幅 + `N/P` 快捷键全走全局页码。
- **可访问性**：Tab 焦点圈闭、方向键移动、当前话 `aria-pressed` + `data-state`。

## polish（对齐设计系统）

- 计数 chip（`第 X / 共 N 话`）走 `--text-caption` + `--paper-1` 底 + `--ink-1` 字；
- 序数圆直径收敛到 `calc(var(--control-md) - var(--space-4))`（即 44px − 16px），不再裸写 1.75rem；
- 滚动条、圆角、间距、动效全部 `--space-*` / `--radius-*` / `--duration-*` / `--accent-*`；
- 按钮沿用 `--control-md` 触控高，危险/强调只用朱砂系。

## adapt（适配）

- 桌面：`[←上一话][中间话选择条][下一话→]` 一行，条 `flex:1 1 auto` 可滚动；
- ≤720px：两按钮换行在上一行（各占一半），中间条整行换到下一行；
- 触控：chip 与按钮高度恒 `--control-md`（≥44px）；滚动条细（6px）且有 hover 强调；
- 长话列表：Home/End + 计数 chip，移动端滚动不吃力。
