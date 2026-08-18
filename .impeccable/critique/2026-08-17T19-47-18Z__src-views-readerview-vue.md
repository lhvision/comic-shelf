---
score: 31/40
p0: 0
p1: 0
p2: 3
p3: 2
target: src/views/ReaderView.vue
timestamp: 2026-08-17T19-47-18Z
slug: src-views-readerview-vue
---

# Impeccable Critique — ReaderView 阅读器（竖向连续/竖向翻页修复后）

Method: ⚠️ DEGRADED: single-context (本会话未暴露 sub-agent/Task 工具，按 skill 规则不允许声称 dual-agent)

Target: `src/views/ReaderView.vue`
Live URL: `http://127.0.0.1:5173/comic/jm/1242163/read/1`

## Design Health Score

| #         | Heuristic                       | Score     | Key Issue                                                 |
| --------- | ------------------------------- | --------- | --------------------------------------------------------- |
| 1         | Visibility of System Status     | 3         | 有页码、滚动进度、loading，但设置保存没有反馈             |
| 2         | Match System / Real World       | 4         | “页/屏/上一页/下一页/设置”语言符合漫画阅读器心智          |
| 3         | User Control and Freedom        | 3         | 可返回、全屏、切换模式；竖向翻页改为 proximity 后不再卡死 |
| 4         | Consistency and Standards       | 3         | 大体使用 tokens，但阅读器内部仍有散落 rgba/#0d0e0c 硬编码 |
| 5         | Error Prevention                | 3         | 页数只允许 1/2，旧 4 页迁移为 1，边界按钮禁用             |
| 6         | Recognition Rather Than Recall  | 3         | 按钮多为文字+符号；键盘快捷键完全不可发现                 |
| 7         | Flexibility and Efficiency      | 3         | 键盘/全屏可用，但亮度、主题、书签等阅读器效率功能缺失     |
| 8         | Aesthetic and Minimalist Design | 4         | 暗色阅读器克制，不抢漫画内容，层级清晰                    |
| 9         | Error Recovery                  | 3         | 图片失败可重试、可返回详情；滚动卡住问题本次修复          |
| 10        | Help and Documentation          | 2         | 没有快捷键/手势说明入口                                   |
| **Total** |                                 | **31/40** | **良好，接近专业阅读器仍有细节债**                        |

## Design Specificity Verdict

这是一个“私人阅览室”阅读器，不是通用图片查看器：暖纸色品牌 token 在阅读器里被正确切换为暗色阅读场，页码、屏、横向日漫方向等概念是漫画阅读器的专属语言。设计特异性成立。

**LLM assessment**: 整体方向对，暗色沉浸感、克制的 chrome、滚动驱动进度都是对的。主要问题不是视觉世界，而是工程细节：硬编码颜色开始漂移、触控目标偏小、设置项没有按模式折叠、快捷键没有入口。

**Deterministic scan**: `detect.mjs --json src/views/ReaderView.vue` 返回 `[]`，无机械缺陷。

**Visual overlays**: 本环境未注入 `[Human]` overlay；使用 Playwright 做了 DOM/ComputedStyle 测量作为浏览器证据。

## Overall Impression

修复后的阅读器终于稳定了：翻页不再被 mandatory snap 卡住，PC 连续模式与翻页模式尺寸一致，移动端连续模式不再每页空一屏。剩下的是“手感层”问题：触控目标、快捷键可发现性、颜色 token 收敛。

## What's Working

- **滚动稳定性修复到位**：`vertical-paged` 从 `y mandatory + scroll-behavior:smooth` 改为 `y proximity` 后，快速滚轮从卡在 100px 附近变为持续滚动，20 次 wheel 连续推进到 9077px。
- **尺寸一致性**：PC 1280×900 下，`vertical-continuous` 与 `vertical-paged` 的 page-frame 都是 802px；连续模式不再按原图高度堆出 1712px 的巨页。
- **移动端页间节奏**：390×844 下，连续模式后续 spread 从 844px 降至 550px（1 页）和 289px（2 页），页间空白问题消除。

## Priority Issues

- **[P2] 阅读器颜色开始脱离 token**：`#0d0e0c`、`#11120f`、`rgb(255 255 255 / 14%)` 等散落在 ReaderView。长期会与 tokens.css 的纸色/墨色体系漂移。
  - **Fix**: 在 `tokens.css` 增加 `--reader-bg/-ink/-muted/-line`，ReaderView 只消费变量。
  - **Suggested command**: `$impeccable extract src/views/ReaderView.vue`

- **[P2] 移动端触控目标过小**：`.reader-chrome-toggle` 高度只有 1rem，`.reader-page-indicator button` 只有 1.8rem，低于 44px 触控标准；手机上容易点不到。
  - **Fix**: 移动端把 toggle 和翻页按钮命中区扩到至少 2.75rem，并用 padding 扩大热区。
  - **Suggested command**: `$impeccable adapt src/views/ReaderView.vue`

- **[P2] 键盘快捷键不可发现**：支持方向键/空格/Home/End/F 全屏，但 UI 没有任何提示；新用户完全不知道。
  - **Fix**: 设置面板增加“键盘快捷键”折叠说明，或首次进入时短暂显示 `↑↓ 翻页 · F 全屏`。
  - **Suggested command**: `$impeccable clarify src/views/ReaderView.vue`

- **[P3] 设置项没有按模式收敛**：竖向连续时仍显示“横向阅读方向”，横向时仍显示“竖向连续适配”，增加认知噪音。
  - **Fix**: 按当前 mode 只显示相关 setting-group，或对不适用项加 disabled + 原因。
  - **Suggested command**: `$impeccable layout src/views/ReaderView.vue`

- **[P3] 设置保存没有反馈**：点击页数/模式后 localStorage 立即写，但用户不知道已持久化。
  - **Fix**: 设置面板底部加一行轻量状态文字“已自动保存到本机”。
  - **Suggested command**: `$impeccable polish src/views/ReaderView.vue`

## Persona Red Flags

**Alex（Power User）**: 知道阅读器可能支持键盘，但找不到快捷键说明；设置面板每次都要手动开关；没有“上一本/下一本”。效率低于预期。

**Jordan（First-Timer）**: 第一次进阅读器，除页码外不知道滚轮/方向键规则；图片加载失败后“重试”在页面内但未解释离线/缓存概念。容易在设置面板里误触横向方向。

**Mina（Mobile Reader）**: 手机宽度下 chrome toggle 太小，页码指示器两个按钮也不足 44px；误触率高。连续模式修复后节奏已经很好，但横向 2 页在手机上仍偏小，考虑移动端默认 1 页。

## Minor Observations

- 桌面垂直滚动条未隐藏，和沉浸式暗色阅读器略有冲突；可 `scrollbar-width: thin` 或自定义暗色滚动条。
- `.reader-spread` 仍使用 `content-visibility:auto`，移动端 intrinsic size 与真实高度有差异，长书滚动条会轻微伸缩；可给 `data-pages=1/2` 设定更接近的 intrinsic 值。
- settings-panel 的 `max-height: min(44rem, ...)` 在横屏手机上可能过高；可加 `dvh`。
- PageDown/Space 的行为是“下一屏”，但没有给触控板用户等价手势提示。

## Questions to Consider

- 如果阅读器只保留 1/2 页，是否移动端应该强制 1 页、平板才开放 2 页？
- 进度条已经有 scroll-driven 动画，是否值得让页码指示器也随滚动更早消失？
- 全屏后是否应该自动隐藏系统光标？
- 可不可以把“亮度”做成最轻量的一个滑块，而不引入完整阅读器设置？

## Run Notes

- target slug: `src-views-readerview-vue`
- ignore list: 不存在 `.impeccable/critique/ignore.md`
- assessment independence: DEGRADED，单上下文顺序执行
- CLI detector: 通过，0 findings
- browser visibility: 使用 Playwright 测量桌面/移动端尺寸与滚动行为；未注入 overlay
- YAML test: 未能在当前沙箱执行 `pnpm test:yaml`（pnpm store 只读 + Puppeteer Chrome cache 缺失）；已写 `e2e/yaml/panel-not-covered.yaml`，用户环境跑 `pnpm test:yaml`
- live server cleanup: 无新增常驻服务
- temp files: 已清理 dist/test-results/midscene_run
