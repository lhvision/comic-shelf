---
target: src/views/ReaderView.vue
total_score: 32
max_score: 40
na_heuristics:
p0_count: 0
p1_count: 1
timestamp: 2026-08-17T20-26-08Z
slug: src-views-readerview-vue
---

# Impeccable Critique — ReaderView 自动切换功能（初版）

Method: ⚠️ DEGRADED: single-context (本会话未暴露 sub-agent/Task 工具，按 skill 规则不允许声称 dual-agent)

Target: `src/views/ReaderView.vue`
Live URL: `http://127.0.0.1:5173/comic/jm/1242163/read/1`

## Design Health Score

| #         | Heuristic                       | Score     | Key Issue                                                  |
| --------- | ------------------------------- | --------- | ---------------------------------------------------------- |
| 1         | Visibility of System Status     | 4         | 倒计时 pill 持续可见，页码同步更新，开启/暂停/到底状态明确 |
| 2         | Match System / Real World       | 4         | “下一屏”“秒后切换”“已到最后一屏”符合漫画阅读器语言         |
| 3         | User Control and Freedom        | 4         | 手动翻页会重置倒计时，设置面板打开时暂停，可随时关闭       |
| 4         | Consistency and Standards       | 2         | 新增 switch/countdown 仍用散落 rgba、0.4/0.7rem 等硬编码   |
| 5         | Error Prevention                | 3         | 4 档间隔避免失控；但键盘按 Space 会在设置面板内误翻页      |
| 6         | Recognition Rather Than Recall  | 3         | 倒计时自解释；快捷键入口仍缺失                             |
| 7         | Flexibility and Efficiency      | 3         | 自动切换是可保留的效率功能；但所有模式下行为未差异化       |
| 8         | Aesthetic and Minimalist Design | 4         | 倒计时与页码指示器同语言、同材质，不打扰画面               |
| 9         | Error Recovery                  | 3         | 到末屏停住、手动返回可恢复；图片错误沿用旧重试             |
| 10        | Help and Documentation          | 2         | 无快捷键/手势说明入口                                      |
| **Total** |                                 | **32/40** | **良好，新增功能方向对，键盘路径有 P1 级缺口**             |

## Design Specificity Verdict

这个功能仍然属于“私人阅览室”而不是通用 slideshow：倒计时采用 mono 数字语言，和页码指示器使用同一套暗色 pill 材质，间隔选项克制在 5/10/15/30 秒四档，不会把阅读器变成 PPT 遥控器。设计特异性成立。

**LLM assessment**: 自动切换的交互模型是对的——启用后底部 HUD 常驻、倒计时位于页码上方、手动操作重置计时、设置面板打开即暂停、到最后一屏停止。主要缺陷在实现层：键盘事件穿透设置面板，新增样式继续制造颜色/间距漂移，移动端命中区沿用旧问题。

**Deterministic scan**: `detect.mjs --json src/views/ReaderView.vue` 返回 `[]`，无机械缺陷。

**Visual overlays**: 本会话无可见 `[Human]` 浏览器页签，未注入 overlay；改用 Playwright headless 做了桌面 1280×900 / 手机 390×844 的 DOM、computed style 与真实计时行为测量。

## Overall Impression

功能一次跑通：5 秒档在桌面和手机上都能从 1/39 翻到 2/39，倒计时与页码间距 8px，localStorage 持久化正确，设置打开时倒计时显示“设置中 · 已暂停”。最大的问题不是自动切换本身，而是它把全局键盘处理器的旧债暴露得更严重了。

## What's Working

- **状态可见性完整**：启用后 HUD 不再随 chrome 隐藏，倒计时常驻；设置中显示“已暂停”，末屏显示“已到最后一屏”，没有静默失败。
- **计时语义正确**：手动翻页、滚轮、触摸滚动都会重置倒计时；设置面板打开和页面切后台会暂停，回到前台重新从完整间隔开始。
- **持久化与迁移兼容**：旧 `localStorage` 数据缺省自动补 `autoTurn:false` 和 `autoTurnInterval:10`，不会破坏现有用户设置。

## Priority Issues

- **[P1] 键盘 Space 穿透设置面板，破坏按钮且误翻页**
  - **Why it matters**: 实测在设置面板中聚焦 switch 按 Space，`aria-checked` 不变，但背后的页面从 1/39 翻到 2/39。所有设置按钮的键盘激活（Space）都被全局快捷键劫持，键盘用户无法可靠操作设置。
  - **Fix**: `onKeydown` 在 `settingsOpen` 时只处理 `Escape`，其余按键直接 return；设置面板内让原生 button 行为接管。
  - **Suggested command**: `$impeccable polish src/views/ReaderView.vue`

- **[P2] 新增样式继续用硬编码颜色和零散 rem**
  - **Why it matters**: `.auto-turn-countdown`、`.switch` 新增了 `rgb(255 255 255 / 16%)`、`0.4rem 0.7rem`、`1.5rem` 等值，和 tokens.css 的 4pt 间距体系、纸墨 token 继续漂移；和既有 `.reader-page-indicator` 的问题叠加。
  - **Fix**: 在 ReaderView 顶部建立 `--reader-line/--reader-surface/--reader-control-h` 等局部语义变量，所有颜色/间距/字号收敛到 `var(--space-*)`、`var(--text-*)`、`var(--radius-*)`。
  - **Suggested command**: `$impeccable polish src/views/ReaderView.vue`

- **[P2] 移动端命中区不达标**
  - **Why it matters**: 实测 390×844 下 switch 是 44×24，页码翻页按钮只有 28.8×28.8，都低于 44px 触控标准；用户抱怨“点不到”会比抱怨“没有自动翻页”更早出现。
  - **Fix**: switch 用 padding 扩到至少 44×44 的命中区（视觉轨道保持 44×24）；页码按钮和 chrome-toggle 同理，用 `::before` 或加大尺寸扩热区。
  - **Suggested command**: `$impeccable adapt src/views/ReaderView.vue`

- **[P3] 自动切换未尊重 `prefers-reduced-motion`**
  - **Why it matters**: 自动切屏使用 `scrollTo({ behavior: 'smooth' })`，对动效敏感用户在横/竖向翻页模式下每 5–30 秒被强制观看一次平滑滚动。
  - **Fix**: 自动切换路径在 `prefers-reduced-motion: reduce` 时使用 `behavior: 'auto'`，手动翻页可保留平滑。
  - **Suggested command**: `$impeccable polish src/views/ReaderView.vue`

- **[P3] 设置面板关闭后 chrome 可能停在展开态**
  - **Why it matters**: 页面加载后立刻打开设置，2.6s 隐藏计时器会在面板打开期间被跳过，关闭面板后没有重新调度，顶部栏会一直压住内容；自动切换常驻底部 HUD 时这个不协调更明显。
  - **Fix**: `watch(settingsOpen)` 关闭分支同时调用 `scheduleChromeHide()`。
  - **Suggested command**: `$impeccable polish src/views/ReaderView.vue`

## Persona Red Flags

**Alex（Power User）**: 自动切换对他有用，但会试图用 Tab 到 switch 后按 Space 开启；当前 Space 会翻到下一页，设置面板里的选项完全无法用 Space 激活，效率路径直接失效。

**Jordan（First-Timer）**: 能看到“开启后按设定间隔自动翻到下一屏”，也能看懂倒计时；但找不到快捷键说明，且设置面板中按方向键会听到/看到页面在面板后跳动，容易以为功能坏了。

**Mina（Mobile Reader）**: 手机 390px 宽度下倒计时与页码能完整落进 HUD，没有溢出；但页码箭头只有 28.8px，switch 高度只有 24px，拇指误触率高，自动切换开着时想暂停会先点错。

## Minor Observations

- 倒计时字号 12px，在手机上属于临界值；保持 mono 风格但可提到 `--text-sm` 并缩短 padding。
- `role="timer"` 的 `aria-label` 是静态“自动切换倒计时”，屏幕阅读器不会逐秒播报，这是对的；无需改。
- 自动切换在竖向连续、竖向翻页、横向翻页三种模式下行为一致，尚未按模式解释差异（连续模式实际是“下一屏”而非“下一页”）。
- 设置面板宽度 `min(42rem, 100%)` 在 320px 横屏仍需验证（归入 adapt）。

## Questions to Consider

- 自动切换开启时，是否应该把底部 HUD 收成只读倒计时，而不是保留两个 28.8px 的翻页按钮？
- 倒计时最后 3 秒是否值得用 accent 色或轻微呼吸提示，而不是只靠文本？
- 连续模式下“下一屏”与用户理解的“下一页”是否需要在设置里换措辞？
