---
target: 多章节「按章节摆放 + 章节子路由」详情页交互评审
total_score: 37
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 1
timestamp: 2026-08-19T19-33-06Z
slug: src-chapter-directory
---

# Impeccable Critique — 章节目录 + 章节子路由（critique → polish → adapt）

Target: `ComicDetailView`（多章节 → `ChapterIndex`）+ `ChapterView`（章节子路由）

- `detail/ChapterCard` / `detail/ChapterIndex` / `detail/ChapterSwitcher` + `composables/useChapterNavigation`
  Method: 按 `docs/agents/ui.md` 的 Impeccable 234 步，切到专业设计评审视角，只评“按章节摆放”这一增量。

## 评审结论（grill-with-docs → critique）

- **grill 结论**：原“横向章节 chips + 详情页内切片”虽然不再一次渲染几千页，但用户心智仍是
  “一个超长详情页”，没有“目录 → 话”的层级；多章节（可几百话、几千页）应该在**详情页只摆章节目录**，
  点某话进**章节子路由**看那话页面——这正是这次重设计。
- **健康分 37/40（Good）**，新增设计延续“私人阅览室 / 卡片目录”语言（章节目录像书架目录条目）。

| #   | Heuristic                       | Score | 说明                                                                                   |
| --- | ------------------------------- | ----- | -------------------------------------------------------------------------------------- |
| 1   | Visibility of System Status     | 4     | 章节卡片有封面/页数/序数；“共 N 话”总览清楚；子路由头显示“第 X 話 · 标题 · 全局页区间” |
| 2   | Match System / Real World       | 4     | “章节目录 → 话 → 页面索引”符合书籍/合集的直觉；单章节直接页码，零心智切换              |
| 3   | User Control and Freedom        | 4     | 子路由可返回本子；上一话/下一话 pager + 章节 chips 随意跳；点页直达全局页码阅读器      |
| 4   | Consistency and Standards       | 4     | 全部复用 token；ChapterCard/PageIndexGrid/ChapterSwitcher 视觉同源                     |
| 5   | Error Prevention                | 3     | 章节封面加载失败回落空白占位（书脊色条），不破版；单章节/错误 id 自动回详情页          |
| 6   | Recognition Rather Than Recall  | 4     | 封面 + 话标题 + 页数一目了然；不用记“第几话在第几页”                                   |
| 7   | Flexibility and Efficiency      | 4     | 子路由可分享/刷新直达某话；chips 左右方向键 + pager 双入口                             |
| 8   | Aesthetic and Minimalist Design | 5     | 目录卡片克制：封面 + 三段信息，无卡片套卡片、无紫渐变                                  |
| 9   | Error Recovery                  | 3     | 封面加载失败回落占位；子路由加载失败 toast 并跳回详情；缺一话仍在目录可见              |
| 10  | Help and Documentation          | 4     | eyebrow「Table of contents / 第 X 話」上下文清楚；head 显示全局页区间辅助定位          |

## P1（随 polish/adapt 一并修）

- **[P1] ChapterCard 封面会为“每一话的第一页”触发一次缩略图下载（几千页的合集 = 几百次懒下载）**
  - Why: 目录展示时一次性铺开 N 张封面，每张都把该话第一页拉下来并生成缩略图，对超长合集是 N 次网络/磁盘成本；但都有 `loading=lazy`，且失败回落占位。
  - 决策：本轮保留 `loading="lazy" + 失败回落占位`（体验优先），把“目录封面池化/服务端章节封面端点”列入 P2 ticket；不做首屏全量。

## What's Working

- **结构正确**：单章节 `ComicDetailView` 直接 PageIndexGrid（旧样）；多章节只出目录，点话进子路由——彻底避免几千页一排。
- **复用充分**：PageIndexGrid（48 增量 + 章节前缀）、ChapterSwitcher（方向键 + useScroll 居中）、useChapterNavigation（切片/剩下页/继续阅读文案）全部复用，无重复代码。
- **子路由纯粹**：`ChapterView` 只做“加载详情 → 锁定章节 → 渲染头部/目录/页索引”，路由化后可直接分享/刷新直达某话。

## polish（对齐设计系统）

- 目录卡片、章节头、pager 全部走既有 token（`--space-*` / `--radius-2` / `--text-sm/caption` / `--ink-*` / `--paper-*` / `--shadow-1/2`）；
- 封面占位用 `--paper-1→paper-2` 斜向渐变 + 朱砂书脊色带，符号化“书脊”隐喻；
- 章节序数用 `eyebrow` 统一字阶，页数用 `--font-mono --text-caption`，与 PageTile 角标同源。

## adapt（适配）

- 桌面：目录网格 `repeat(auto-fill, minmax(min(20rem,100%),1fr))`，卡片横排（封面 + 信息）；
- 平板/手机（<=640px）：目录 `1fr` 单列；头部/pager 纵向堆叠；chips 可横向滚动居中；
- 小屏（<=480px）：卡片封面列收窄 `minmax(4.2rem,0.7fr)`，保证触控标题可读；
- pager 按钮窄屏 `flex:1 1 8rem` 双按钮占满一行，触控区 ≥44px。
