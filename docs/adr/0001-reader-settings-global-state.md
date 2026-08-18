# ADR 0001 — 阅读器设置用 VueUse 全局状态 + localStorage，而非 Pinia

- **日期**：2026-08-19
- **状态**：Accepted

## 背景

迭代「拆分 ReaderView」时，阅读器设置对象（`settings`：阅读模式、每屏页数、
自动切换、方向、图片适配）需要同时被：

1. `ReaderView`（编排阅读会话）
2. `ReaderSettingsPanel`（设置面板组件，独立拆出后）
3. 跨路由重挂载仍保留（用户打开阅读器 A，读完去详情，再进阅读器 B，设置不丢）

旧实现把 `settings` 放在 `ReaderView` 内部 `reactive` + 手写 `localStorage`
读写 + 手写 `matchMedia` 监听。拆分后若把状态继续留在视图里，设置面板组件
要么被迫接收十几个 props，要么直接 import 视图内部状态——都会破坏拆分意图。

## 决策

阅读器设置收敛为一个共享组合式函数 `useReaderSettings`：

- 用 VueUse `createGlobalState` 提升为模块级单例；
- 用 `useLocalStorage`（key 固定为 `comic-shelf:reader-settings:v1`）做持久化；
- 用 `useMediaQuery(WIDE_VIEWPORT_QUERY)` 做窄屏判定（>680px 才允许 4 连页）；
- 读取时对旧存储值做归一化（非法枚举回落默认、窄屏钳制 `pagesPerView 4→2`）。

不用 Pinia store 的原因：

- 这是**单一对象、多读少写**，没有跨页派生/联动逻辑，Pinia 的 action/getter 都无用武之地；
- 项目已依赖 `@vueuse/core`，`useStorage`/`useMediaQuery` 比 store + 手写 raw
  JSON 读写更贴近"响应式 + 持久化"的声明式目标；
- 减少一个 store 便减少一个需要被测试与维护的抽象层。

## 后果

- **兼容性责任**：`SETTINGS_KEY` 必须永久保持
  `comic-shelf:reader-settings:v1`，已存用户的设置才能继续读到。
  改名或升级 key 需要显式迁移，不能悄悄改。
- **跨标签页同步**：`useLocalStorage` 默认监听 `storage` 事件，
  多个标签页同时开阅读器时会同步设置（旧代码没有）。这是行为增强。
- **回归风险**：阅读器键盘/自动切换逻辑仍留在 `ReaderView`，
  状态与行为分层（状态在 composable、编排在视图），改动设置模型时
  需要同时看这两处。

## 备选

- **Pinia store**：更"官方"，但为单一设置对象引入整个 store 抽象，收益不明显。
- **props/emits 全量下发**：设置面板需要 ~10 个 props + 对应 emit，拆的收益被钉死在视图。
