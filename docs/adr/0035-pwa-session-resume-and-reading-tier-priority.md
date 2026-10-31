# ADR 0035 — PWA 阅读会话恢复、案头在读时序置顶与视口偏好持久化

- **日期**：2026-10-31
- **状态**：Accepted

## 背景与问题

纸间定位于「本地优先的个人漫画收藏馆与私密阅览室」，在读者使用移动端或桌面 PWA 独立应用视口阅览漫画时，暴露出三处割裂日常阅览心智的问题：

1. **冷启动会话中断丢失**：读者在阅读器内部直接划掉退出应用或因系统杀后台休眠中断后，下次点击桌面图标启动（`start_url: '/'`）一律停留在书架首页，必须手动重新检索并点进本子才能接续；
2. **在读未完结藏书无法置顶**：书架默认排序 `recent`（最近收录）将未读与在读藏书统一放在同一梯队，且仅按作品初次入库时间（`imported_at`）倒序排布。读者刚刚中途退出的在读本子若入库较早，会被压在案头深处，违背了“刚合上的书就在案头手边”的心智；
3. **PWA 偏好失忆**：书架组合式函数 `useShelfState` 仅使用内存级 `ref`，读者选定的漫画源分区 Tab、排序规则 `sortBy`、阅读状态筛选 `readingStatus` 与只看喜欢 `favoritesOnly` 在 PWA 进程重建后立刻归零。

## 核心决策

### 一、案头在读时序置顶（Active Reading Priority）与四级梯队重构

重塑书架全貌 `query_library_index`（后端 SQLite 影子索引）与 `filterAndSortLibrary`（前端 Worker / 纯函数双轨）的默认排序规则：

- **Tier 0（追更更新）**：作品追加新章节且读者尚未翻阅（`ci.page_count > urp.total_pages`），按 `ci.mtime DESC` 保持最高置顶；
- **Tier 1（案头在读）**：读者已开卷但尚未读完（`0 < last_page < page_count`），严格按读者最后翻页时间戳 `urp.updated_at DESC` 排布。**读者退出前翻过的本子天然升至全库第 1 位**；
- **Tier 2（案头未读）**：尚未开卷的全新藏书（`last_page == 0`），按初次收录时间 `ci.imported_at DESC` 呈现新鲜感；
- **Tier 3（卷末归档）**：已完全读至全书末页的藏书（`last_page >= page_count`），按 `ci.imported_at DESC` 折叠收纳于案头底端。

在查询投影中，`query_library_index` 补齐透出 `COALESCE(urp.updated_at, 0) as read_updated_at`，与前端 `LibrarySummary` 强类型契约严格对齐。端侧 `setReadingProgressLocal` 本地乐观更新同步注入秒级 `read_updated_at`，并在开卷首屏第 1 页即刻激活在读打标，确保无需等待后端返回即可让翻阅作品即时置顶案头。

### 二、阅读会话恢复（Reading Session Resume）与极端退出防丢

1. **阅读器生命周期受控记录**：
   - 阅读器运行时通过 `@vueuse/core` 驱动 `comic-shelf:active-reading-session:v1`（包含 `source`, `sourceId`, `page`, `totalPages`, `updatedAt`, `active: boolean`）；
   - 当读者主动点击阅读器顶栏「返回书架/详情」或翻至全书末页读完全本时，显式标记 `active = false`；
   - 若读者在阅读过程中直接划掉应用、进程被系统回收或锁屏关闭，状态保留 `active = true`。
2. **冷启动直达与逃生通道**：
   - 统一由系统设置项「启动时自动恢复上次阅读」（`comic-shelf:resume-on-launch:v1`，默认开启）驱动，消除脆弱的 WebKit `navigator.standalone` 环境排他限制，移动端与 PWA 体验完全一致；
   - 探测到合法的未读完活跃会话且根路径无特定查询参数时，冷启动直接路由直达 `/comic/:source/:sourceId/read/:page`，并以朱砂轻提示弹出「已恢复上次在读：第 X 页」；读者点击阅读器顶栏返回按钮即可安全返回书架。
3. **多租户、鉴权前置与单本沙箱隔离**：
   - 全局认证未登录拦截：若全站开启鉴权且当前处于未认证状态（`authRequired && (!authenticated || role === 'unauthorized')`），严禁恢复任何在读会话，杜绝未登录者窥探馆长私密藏书；
   - 单本沙箱边界：单本限定通行证（`isDirectPass`）仅允许恢复对应限定作品，严防逃逸至全库其他画卷；
   - 实施双向归一化身份比对（`normalizeSessionUid`），馆长单人模式归一化为 `curator`；
   - 侦听 `userId` 真实切换或登出（`oldUid && oldUid !== newUid`），级联调用 `clearSession()` 彻底擦除 LocalStorage，杜绝共享设备上的在读信息残留；同时豁免冷启动异步水合阶段的误清空。
4. **移动端极端退出与防抖落盘保障**：
   - 原生 `keepalive: true`：在进度上报请求中注入原生 `keepalive: true`，即使移动端直接杀死应用，浏览器底层网络栈仍能保证完成上报；
   - 零延迟 Flush：在 `pagehide`、`beforeunload` 与作用域卸载时强制刷新 800ms 防抖队列；
   - LWW（Last-Write-Wins）时间戳双向对齐：摒弃粗暴的 `Math.max` 单调递增逻辑（消除读者从头重读第 1 页被旧云端进度锁死弹回的缺陷）；引入秒级复合时间戳比对（`comic-shelf:last-read:...:ts`）。云端更新晚于端侧则拉取云端，端侧更新晚于云端（如从头重读、刚离线翻页）则坚守端侧真实进度并向服务端补报。
   - 跨本状态解耦：切源或路由卸载时严格调用 `clearActiveComic()` 清理激活配置，杜绝上一部漫画残留 `currentPage` 跨本踩踏写入。

### 三、书架核心视口偏好记忆（Shelf Preferences Persistence）

1. **分级持久化边界**：
   - 将影响读者日常使用习惯的核心状态通过 `useLocalStorage` 隔离落盘（键名 `comic-shelf:shelf-preferences:v1`）：
     - 来源分区 `source`（上次停留的漫画图源 Tab）；
     - 排序模式 `sortBy`；
     - 阅读状态过滤 `readingStatus`；
     - 只看喜欢 `favoritesOnly`。
   - 检索关键词 `search` 与选中标签 `activeTags` 坚守内存瞬态，杜绝下次打开误以为藏书丢失。
2. **冷启动单向水合与切源重置解耦**：
   - 冷启动由根路径挂载恢复 `persistedSource` 并触发 `router.replace` 时，设置瞬态水合守卫（`isHydratingSource`），阻断 `watch(activeSource)` 误触发全局重置，确保先前持久化的排序、状态与只看喜欢完好无损；
   - 避免在重置流程中手动覆写落盘对象，完全由响应式单向流驱动落盘更新。
3. **Deep-Link 外部链接优先级防御**：
   - 当携带 `?source=...`、`?sort=...` 等显式查询参数直达或分享打开时，URL 参数享有瞬时最高优先级，不被本地记忆覆写，亦不冲掉读者的日常本地偏好；
   - 读者显式点击顶栏 Logo 或“全部藏书”时，提供干净的重置初态通道。

## 效果与收益

1. 读者在 PWA 独立窗口中获得媲美原生阅读 App 的沉浸接续体验，合上即走、打开即读；
2. 书架案头与读者实际注意力流向完全吻合，最近未读完作品始终触手可及；
3. 彻底消除 PWA 进程频繁回收导致的分区与排序失忆问题。
