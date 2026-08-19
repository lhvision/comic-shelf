---
target: 多章节支持的详情页 / 章节切换 / 阅读器章节标注评审
total_score: 35
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 2
timestamp: 2026-08-19T16-02-40Z
slug: src-views-comicdetailview-vue-multichapter
---

# Impeccable Critique — 纸间多章节详情页（critique → polish → adapt）

Target: `ComicDetailView` + `detail/ChapterSwitcher.vue` + `detail/PageIndexGrid.vue`

- `MetadataPanel`（章节行）+ `reader/ReaderTopBar`（章节标注）+ 后端 `ComicMeta.chapters` 模型
  Method: 切换专业设计评审视角（A/B 双 agent），只针对“多章节”这一增量设计，不做全站回归。
  Live URL: 本地 Vite dev（未做浏览器注入；以代码 + tokens + 已有基线为准）

## 评审结论（critique）

多章节增量设计延续了“私人阅览室 / 卡片目录”的语言：章节切换条像一卷书脊、
页码对照表放在每话之前，全局页码拍平让“继续阅读 / 封面 / 阅读器页码”不用改心智。
总体健康分 **35/40（Good）**；本轮新增的两个 P1 已随 polish/adapt 一并修掉。

| #   | Heuristic                       | Score | Key Issue                                                                                          |
| --- | ------------------------------- | ----- | -------------------------------------------------------------------------------------------------- |
| 1   | Visibility of System Status     | 4     | 章节高亮、已显示 X/Y 页、阅读器顶栏章节标注都有；切换后会滚回本段顶部                              |
| 2   | Match System / Real World       | 4     | “第 N 話 + 标题 + 页数”的三段 chip 贴近阅读器里“第 N 話”的说法；“继续阅读”带章节定位               |
| 3   | User Control and Freedom        | 4     | 左右方向键可在章节间跳转；回到上次阅读章节；鼠标点击/键盘都可用                                    |
| 4   | Consistency and Standards       | 4     | 全部 token（`--space-*`/`--control-md`/`--text-caption`/`--accent-soft`）、mono 页码、朱砂强调沿用 |
| 5   | Error Prevention                | 4     | 单章节不渲染切换条、不显示章节行；缺省落到第 1 话；章节 id 全局唯一                                |
| 6   | Recognition Rather Than Recall  | 3     | 多章节时“已显示页数”不带章节上下文，用户在长书里容易丢位置 → 已在 page-count-note 前缀章节         |
| 7   | Flexibility and Efficiency      | 3     | 键盘方向键；无“跳转下一话”快捷阅读，留作 ticket                                                    |
| 8   | Aesthetic and Minimalist Design | 5     | 章节 chip 用序数圆 + mono 页数，克制；无新增紫色渐变/卡片套卡片                                    |
| 9   | Error Recovery                  | 4     | 章节切换只改聚合视图，不碰持久化状态；“移除本地”沿用既有内联确认                                   |
| 10  | Help and Documentation          | 4     | 空章节标题回落“第 N 話”；metadata 补充“章节”行；CHANGELOG/spec 已更新                              |

## P1 问题（本轮发现）

- **[P1] 章节 chip 组缺少键盘方向键导航、语义用了 role=tablist 却没有 tabpanel（ChapterSwitcher）**
  - Why: 屏幕阅读器把 `role=tablist` 当标签页语义时，没有对应 `tabpanel` 会误报；
    键盘用户无法用左右方向键在章节间快速移动。
  - Fix: 改用 `role="group"` + `aria-pressed` 的切换按钮组，并监听左右方向键
    （`useEventListener`，符合 VueUse 约定）在章节间移动并聚焦。
  - Suggested command: $impeccable harden

- **[P1] 多章节下“已显示 X / Y 页”缺少章节上下文；章节数徽标对比度偏弱（PageIndexGrid / ChapterSwitcher）**
  - Why: 长合集切到中段话时，只看“第 34/220 页”无法确认自己在哪话；`chapter-count` 用
    `--ink-2` 在 `--paper-1` 上对比度偏低。
  - Fix: `PageIndexGrid` 的计数行前缀当前章节（`第 2 話 · …`），`chapter-count` 提升到
    `--ink-1`，选中态叠加朱砂浅底。
  - Suggested command: $impeccable typeset

## What's Working

- **“全局页码 + 章节切片”这一结构决策**：后端把多章作品拍平成一张全局页码表，
  阅读器、继续阅读、封面轮播、缓存进度全部沿用旧语义，只有详情页的“页面索引”按章切片。
  这是把“多章节”这种第二维复杂度收敛到最小扩散面的做法。
- **单章节零回归**：`chapters` 为空时，详情页不出现切换条、metadata 显示“单话”，
  页码范围就是全书，与旧版完全一致。
- **VueUse 合理使用**：`useScroll` 平滑居中当前 chip、`useEventListener` 做键盘、既有的
  `useIntersectionObserver` 增量加载，无手写浏览器样板。
- **后端向前兼容**：`PageRecord.chapter` 与 `ComicMeta.chapters` 都是带默认值的新字段，
  旧 `album.json` 无需迁移；存储层同时支持旧的扁平 `pages/` 与新的 `pages/<chapter>/` 两种布局。

## polish（对齐设计系统）

- 新增的章节切换条、章节行、阅读器章节标注全部走既有 token，无新增色值/字号/间距；
- `chapter-count` 角标 `--ink-2 → --ink-1`，选中态叠加 `accent` 浅底，保证角标在暖纸上的对比；
- `ChapterSwitcher` 圆角、间距、`--control-md` 触控高度与 PageTile / DetailActionBar 保持同一套；
- mono 字体族贯穿章节序数圆、页数徽标、页码对照表，不引入新的字体层级。

## adapt（适配）

- 桌面：章节条横向铺开，chip 含“序数 + 标题 + 页数”三段；
- 平板/手机（<=640px）：章节条改为可横向滚动胶囊条（`overflow-x: auto` + `scrollbar-width: thin`），
  边距对齐 `--space-4`，选中 chip 用 `useScroll` 平滑滚进视野中心；
- 阅读器顶栏章节标注在窄屏仍保留（`text-overflow: ellipsis`，不换行）；
- 触控：chip 整块 min-height 44px（`--control-md`），内部序数圆为装饰元素不单独是点击目标。
