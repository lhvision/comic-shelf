# ADR 0009 — PWA Prompt 更新模式与 SSE 单向系统事件流

- **日期**：2026-09-01
- **状态**：Accepted

## 背景

纸间在生产环境中以 PWA（渐进式 Web 应用）形式运行。在早期版本中，Service Worker 采用 `autoUpdate` 自动接管模式。然而在实际阅览与部署中暴露出两项痛点：

1. **自动强行刷新或陈旧状态打断阅读**：当新前端版本打包上线时，`autoUpdate` 模式会静默调用 `skipWaiting()`，若用户正在沉浸翻页，突兀的刷新或资源失步可能打断阅读体验；
2. **缺乏零轮询的高效实时通知机制**：传统前端轮询 `/api/version` 会频繁唤醒 CPU、产生大量无意义的 HTTP 握手与数据库查询开销。未来纸间需要引入 AI 流式解析、后台异步入库与任务进度广播，亟需一条极轻量、0 轮询的单向通信通道。

## 决策

1. **VitePWA 切换为 Prompt 提示模式（`registerType: 'prompt'`）**：
   - 由前端 Service Worker 状态机（`usePwaUpdate.ts`）精准捕获 `onNeedRefresh`（新 SW 进入 `waiting` 状态）；
   - 提供非侵入式的双重视觉反馈：
     - 浮动胶囊横幅（`<UpdateToast />`）：在屏幕边缘优雅提示「📜 纸间已有新卷本装订就绪」，包含「立即装订 (刷新)」与「稍后」；
     - 沉浸阅读自动避让：当读者处于阅读器全屏阅览时，横幅自动隐退，不遮挡画卷；
     - 顶栏设备徽标联动：若读者选择稍后装订，顶栏设备微件（`<StoragePopover />`）保留醒目的朱砂角标与面板装订卡片。

2. **后端单向系统事件流（SSE, `/api/events/stream`）**：
   - 基于 FastAPI 异步协程与 `asyncio.Queue` 构建多路复用单向广播通道；
   - **0% CPU 挂起**：连接空闲时仅在内存中挂起协程队列，不产生任何计算与磁盘 IO 开销；
   - 承载三类核心事件：
     - `event: ping`（初始连通握手与 25s keepalive 保活）；
     - `event: system_version`（新构建发布广播，秒级触发前端 `registration.update()`）；
     - `event: library_changed`（后台藏书增删与缓存变动广播）；
     - `event: ai_task_progress`（为后续 AI 流式任务与进度条预留）。

3. **视口激活与网络自愈双重回源探测（Visibility & Network Wakeup Sync）**：
   - 利用 VueUse `useDocumentVisibility` 与 `useNetwork`：
     - 当读者从其他标签页切回纸间（Tab Inactive ⇄ Active）时，静默触发一次 `registration.update()`；
     - 当设备从离线弱网切回连线状态时，自动重连 SSE 并触发 SW 比对；
     - 比对完全基于 HTTP 304 头部与字节比对（<5ms，0 业务接口负载）。

4. **智能按需生命周期与休眠编排（Smart On-Demand Lifecycle & Deep Sleep）**：
   - **阅读器主动断开避让（Reader Detachment）**：当读者切入全屏阅读器（`/read/...`）沉浸翻阅时，自动斩断 SSE 长连接，将内网 HTTP/1.1 仅有的 6 个 TCP 槽位与全部网络带宽完整倾斜给漫画画页并发加载；
   - **后台视口即断（Tab Inactive Teardown）**：当标签页离开视口（`document.visibilityState === 'hidden'`）时，立即断开连接，消除后台无意义的 25s keepalive 心跳唤醒与 DevTools 悬挂连接；切回前台时 0 延迟自愈重连；
   - **深度闲置超时休眠（10-min Idle Sleep）**：借助 VueUse `useIdle(10min)` 探测用户交互。连续 10 分钟无操作自动切断长连接进入深睡，任意触控或键鼠操作瞬时唤醒；
   - **唤醒静默对齐（Reconciliation on Wakeup）**：重连握手成功后，自动且静默地触发书架刷新（`libraryStore.load(true)`）与版本比对（`checkForUpdate()`），彻底消除长连接断开期间可能遗漏的事件盲区。

## 后果

- **正面收益**：
  - 读者拥有对应用装订更新的完整控制权，阅读器内绝不被打扰；
  - 彻底杜绝了前端定时轮询，服务器在待机状态下保持 0 CPU 开销；
  - 智能按需生命周期使阅读器独占全部内网并发连接，解决局域网 HTTP/1.1 下 6 个 TCP 连接被长连接霸占的问题；
  - 后台与闲置自动断开，大幅削减移动端电量唤醒与网络面板长连接挂起心理负担；
  - 统一的 SSE 通道为未来的 AI 任务与流式输出提供了现成的基础设施支撑。
- **注意事项**：
  - 局域网内直接通过明文 HTTP IP（如 `http://<IP>:8000`）访问时，因浏览器 Secure Context 规范限制，Service Worker 不会注册，属于正常降级表现；线上 HTTPS 域名下全量生效。
