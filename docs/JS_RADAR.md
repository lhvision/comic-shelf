# JavaScript 前瞻技术雷达（JavaScript Foresight Radar）

> **用途**：纸间（Paper Room）项目的 JavaScript / Web API 现代特性追踪文档。记录已落地用法、降级方案与尚在草案中的特性，供下一次迭代直接查阅，无需重复阅读 MDN、Can I Use 或频繁翻阅技术博客与 TC39 规范草案。
>
> **维护约定**：每次引入新 JS 特性或发现规范升级时，更新对应条目的 **状态** 与 **用法片段**。坚守零外部侵入性 Polyfill、零实验性 Babel 宏插件的工程底线。

---

## 目录

1. [兼容性快查表](#1-兼容性快查表)
2. [已落地特性（Shipped）](#2-已落地特性shipped)
   - [2.1 `Promise.withResolvers()` — 异步承诺与状态解耦控制（Baseline 2024）](#21-promisewithresolvers--异步承诺与状态解耦控制baseline-2024)
   - [2.2 `Promise.try()` — 统一同步与异步错误边界（Baseline 2025）](#22-promisetry--统一同步与异步错误边界baseline-2025)
   - [2.3 `AbortSignal.any()` 与 `AbortSignal.timeout()` — 原生复合取消信号管线（Baseline 2024）](#23-abortsignalany-与-abortsignaltimeout--原生复合取消信号管线baseline-2024)
   - [2.4 `HTMLImageElement.prototype.decode()` — 异步离屏图片解码管线（Baseline 2020）](#24-htmlimageelementprototypedecode--异步离屏图片解码管线baseline-2020)
   - [2.5 `Set.prototype` 原生集合运算 — 零分配标签过滤体系（Baseline 2024）](#25-setprototype-原生集合运算--零分配标签过滤体系baseline-2024)
   - [2.6 `Map.groupBy` / `Object.groupBy` — 声明式多维数据聚合（Baseline 2024）](#26-mapgroupby--objectgroupby--声明式多维数据聚合baseline-2024)
3. [渐进增强特性（Progressive Enhancement & Newly Available）](#3-渐进增强特性progressive-enhancement--newly-available)
   - [3.1 Iterator Helpers — 生成器流式管道与惰性求值（Baseline 2025）](#31-iterator-helpers--生成器流式管道与惰性求值baseline-2025)
   - [3.2 Explicit Resource Management（`using` / `Symbol.dispose`）— 声明式 RAII 作用域资源清理](#32-explicit-resource-managementusing--symboldispose--声明式-raii-作用域资源清理)
   - [3.3 `Temporal API` — 新一代不可变高精度时间与时区系统（Stage 3-4）](#33-temporal-api--新一代不可变高精度时间与时区系统stage-3-4)
   - [3.4 Import Attributes（`with { type: 'json' }`）— 声明式静态模块导入属性（Baseline 2024 / ES2025）](#34-import-attributeswith--type-json--声明式静态模块导入属性baseline-2024--es2025)
4. [实验草案特性（Experimental / Stage 1-2 Proposals）](#4-实验草案特性experimental--stage-1-2-proposals)
   - [4.1 模式匹配（Pattern Matching: `match / when`）](#41-模式匹配pattern-matching-match--when)
   - [4.2 管道运算符（Pipeline Operator: `\|>` 与 Topic `%`）](#42-管道运算符pipeline-operator--与-topic-)
   - [4.3 不可变复合类型（Record & Tuple: `#{}` 与 `#[]`）](#43-不可变复合类型record--tuple--与-)
   - [4.4 高精度进位数值类型（Decimal: `0.1m`）](#44-高精度进位数值类型decimal-01m)
   - [4.5 安全赋值操作符与 Try 表达式（Safe Assignment `?=`）](#45-安全赋值操作符与-try-表达式safe-assignment-)
5. [升级路线图（Roadmap）](#5-升级路线图roadmap)
6. [参考资源（MDN & 博客专栏）](#6-参考资源mdn--博客专栏)

---

## 1. 兼容性快查表

> 数据来源：MDN BCD (Browser Compatibility Data) + Can I Use，更新于 2026-09。

| 特性 / API                              | Chrome | Firefox | Safari |   规范状态 / Baseline   |                              本项目落地状态                               |
| :-------------------------------------- | :----: | :-----: | :----: | :---------------------: | :-----------------------------------------------------------------------: |
| **`Promise.withResolvers()`**           |  119+  |  121+   | 17.4+  |    ✅ Baseline 2024     |       ✅ 已落地（`useViewTransition` / `router` / IDB 清理 / 单测）       |
| **`Promise.try()`**                     |  128+  |  134+   | 18.2+  |    ✅ Baseline 2025     |             ✅ 已落地（`useViewTransition.ts` 安全执行门面）              |
| **`AbortSignal.any()`**                 |  116+  |  124+   | 17.4+  |    ✅ Baseline 2024     |                 ✅ 已落地（`api/client.ts` 复合超时取消）                 |
| **`AbortSignal.timeout()`**             |  124+  |  100+   |  16+   |    ✅ Baseline 2024     | ⚠️ 架构决策（因无法提前取消定时器，短命 RPC 采用受控定时器 + 原生 `any`） |
| **`Set` 集合运算 (`intersection` 等)**  |  122+  |  127+   |  17+   |    ✅ Baseline 2024     |             ✅ 已落地（`TagFilterBar` / `useLibraryFilter`）              |
| **`Map.groupBy` / `Object.groupBy`**    |  117+  |  119+   | 17.4+  |    ✅ Baseline 2024     |                ✅ 已落地（漫画多章节切片与 Provider 分组）                |
| **`HTMLImageElement.decode()`**         |  65+   |   68+   |  11+   |    ✅ Baseline 2020     |              ✅ 已落地（`HtmlCanvasSurface.vue` / 预载管道）              |
| **Import Attributes (`with { type }`)** |  125+  |  137+   | 17.2+  |    ✅ Baseline 2024     |                📋 路线图（模块化 JSON 元数据与多语言字典）                |
| **Iterator Helpers (`.map()/.take()`)** |  122+  |  131+   | 18.4+  |    ✅ Baseline 2025     |                📋 路线图（IndexedDB 游标与分批上传流水线）                |
| **`using` (Explicit Resource Mgmt)**    |  134+  |  141+   |   TP   | 🔶 Newly Available 2025 |              📋 路线图（Canvas Context / ObjectURL 作用域）               |
| **`Temporal API`**                      |  144+  |  139+   |   TP   | 🔶 Newly Available 2026 |              ⚠️ 审慎评估（待 iOS 稳定版就绪前暂不全量采用）               |
| **模式匹配 (`match / when`)**           |   ❌   |   ❌    |   ❌   |       🧪 Stage 1        |                      🚫 严禁引入转译插件，纯草案观测                      |
| **管道运算符 (`\|>`)**                  |   ❌   |   ❌    |   ❌   |       🧪 Stage 2        |                      🚫 严禁引入转译插件，纯草案观测                      |
| **`Record & Tuple` (`#{} / #[]`)**      |   ❌   |   ❌    |   ❌   |       🧪 Stage 2        |                      🚫 严禁引入转译插件，纯草案观测                      |
| **`Decimal` (`0.1m`)**                  |   ❌   |   ❌    |   ❌   |       🧪 Stage 1        |                     🚫 纸间无浮点货币场景，纯草案观测                     |
| **安全赋值 (`?=`) / Try 表达式**        |   ❌   |   ❌    |   ❌   |       🧪 Stage 1        |                         🚫 语法尚未定稿，暂不采用                         |

**图例**：✅ 已落地 · 🔶 部分/最新可用 · 🧪 实验草案 · ❌ 未原生支持 · 🚫 本项目不采用

---

## 2. 已落地特性（Shipped）

### 2.1 `Promise.withResolvers()` — 异步承诺与状态解耦控制（Baseline 2024）

**MDN**：[Promise.withResolvers()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/withResolvers)  
**Baseline**：2024 · Chrome 119+ · Firefox 121+ · Safari 17.4+ · Node.js 22.0+ · Bun 1.0+  
**参考**：[张鑫旭 Promise.try()和Promise.withResolvers()作用速览](https://www.zhangxinxu.com/wordpress/2026/01/promise-try-withresolvers/)  
**本项目落地位置**：

- `src/utils/promise.ts`（全仓统一单源收敛工具：`withResolvers<T>()` 与 `promiseTry<T>()`）
- `src/composables/useViewTransition.ts`（过渡生命周期与返回值解耦）
- `src/router/index.ts`（路由级 View Transition 异步推进契约）
- `src/composables/useOfflineStorage.ts`（IndexedDB 批量清理与 1.5s 兜底定时器）
- `src/components/HtmlCanvasSurface.vue`（子树图片加载完成与离屏解码协调）
- `src/__tests__/useImageSearch.spec.ts`（单测请求插桩与按需完成控制）

#### 核心原理与解决的反模式

传统 JavaScript 中，若要在 Promise 构造器外部根据事件流或异步回调触发状态解决，必须先在作用域外部声明变量，再在构造器回调内闭包逃逸赋值：

```ts
// ❌ 经典反模式：逃逸变量、外部可变状态、非空类型断言
let resolveFetch!: (res: Response) => void
const pendingPromise = new Promise<Response>((resolve) => {
  resolveFetch = resolve
})
```

采用 `withResolvers()`（优先原生 `Promise.withResolvers()`，平滑降级）后，Promise 实例与其控制函数以单源元组形式一次性返回：

```ts
// ✅ 纸间标准范式（src/utils/promise.ts）：一行搞定，解构即用，不可变且具备单次落地保障
import { withResolvers } from '@/utils/promise'

const { promise: pendingPromise, resolve: resolveFetch } = withResolvers<Response>()
```

#### 实战样板 A：`useViewTransition.ts` 消除可变结果与非空断言

在视图过渡包装函数中，旧代码通过 `let result: T` 与 `return result!` 强行捕获过渡快照内部的返回值。重构后，生命周期管理极其干净：

```ts
import { withResolvers, promiseTry } from '@/utils/promise'

const { promise, resolve, reject } = withResolvers<T>()

const transition = doc.startViewTransition(async () => {
  const task = promiseTry(callback)
  task.then(resolve, reject)
  await task.catch(() => {}) // 内部吃掉异常防止过渡管线崩溃，由外层 promise 抛出
})

transition?.ready?.catch(() => {})
transition?.updateCallbackDone?.catch(() => {})
await transition?.finished?.catch(() => {})

return await promise // 获得强类型返回值或捕获真正业务异常
```

#### 实战样板 B：`useOfflineStorage.ts` 优雅竞争定时器

IndexedDB 在连接未彻底断开时执行 `deleteDatabase` 极易触发 `blocked` 挂死。通过 `withResolvers` 绑定 1.5s 兜底定时器，消灭了原先手写的 `let settled = false` 标记位（利用了 Promise 原生具备的幂等兑现特性）：

```ts
const { promise, resolve } = withResolvers<void>()
const timer = setTimeout(resolve, 1500)

const openReq = indexedDB.open(dbName)
openReq.onsuccess = () => {
  // 业务处理完成直接 resolve，即便 1.5s 超时后触发也不会产生二次执行副作用
  resolve()
}
```

---

### 2.2 `Promise.try()` — 统一同步与异步错误边界（Baseline 2025）

**MDN**：[Promise.try()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/try)  
**Baseline**：2025 · Chrome 128+ · Firefox 134+ · Safari 18.2+ · Node.js 23.0+ · Bun 1.1+  
**参考**：[张鑫旭 Promise.try()和Promise.withResolvers()作用速览](https://www.zhangxinxu.com/wordpress/2026/01/promise-try-withresolvers/)  
**本项目落地位置**：

- `src/utils/promise.ts`（全仓统一单源收敛工具：`promiseTry<T>()`）
- `src/composables/useViewTransition.ts`（门面回调安全封装）

#### 核心原理与设计哲学

当一个高阶函数接受由使用者传入的回调 `callback: () => T | Promise<T>` 时，传统 `new Promise(resolve => resolve(callback()))` 存在隐患：如果 `callback` 在同步阶段直接 `throw new Error()`，在缺乏顶层 `try/catch` 的调用点会直接导致未捕获异常抛出，中断主调用链。

`Promise.try(callback)` 的语义为：

1. 立即执行 `callback`；
2. 若同步抛出错误，直接返回 rejected Promise，错误不会逸出为未捕获异常；
3. 若同步返回普通值，封装为 resolved Promise；
4. 若返回已有的 Promise，平滑连缀到下游。

#### 张鑫旭专栏关键勘误与纸间守则

1. **宏任务错误不可捕获**：`Promise.try` **不能**捕获脱离上下文的宏任务内部错误（如 `setTimeout(() => { throw err }, 100)`）。宏任务必须在自身内部包裹 Promise；
2. **纯 async/await 下无需滥用**：在普通线性 `async function` 中，原生 `try/catch` 结构更为直观高效；`Promise.try` 的主战场在于**公共门面库、生命周期 Hook 触发器、Composable 外部注入函数隔离**。

#### 纸间单源统一收敛（`src/utils/promise.ts`）

为杜绝在各业务组件中重复手写兼容胶水，全仓统一收敛为标准工具函数（严格遵循 TC39 / MDN 规范，支持可选参数直接透传，消除外层多余闭包）：

```ts
// src/utils/promise.ts
export function promiseTry<T, Args extends unknown[]>(
  fn: (...args: Args) => T | PromiseLike<T>,
  ...args: Args
): Promise<Awaited<T>> {
  if (typeof Promise.try === 'function') {
    return Promise.try(fn, ...args)
  }
  return new Promise<Awaited<T>>((resolve) => resolve(fn(...args) as Awaited<T>))
}
```

---

### 2.3 `AbortSignal.any()` 与受控生命周期超时 — 原生复合取消信号管线（Baseline 2024）

**MDN**：[AbortSignal.any()](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/any_static) · [AbortSignal.timeout()](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static)  
**Baseline**：2024 · Chrome 124+ · Firefox 124+ · Safari 17.4+ · Node.js 20.3+  
**本项目落地位置**：`src/api/client.ts`（底层 HTTP 请求拦截与主动/超时联合取消）

#### 为什么不裸用 `AbortSignal.timeout()`？（MDN 警示与架构权衡）

MDN 官方文档与 W3C DOM 规范明确警示：

> _"AbortSignal.timeout() does not provide a way to cancel its timeout. Finishing the operation early... does not cancel the timeout... If resources are constrained and you want to definitively cancel timeouts early, use an AbortController with setTimeout() instead, and call clearTimeout() when the operation finishes."_

在日常高频短生命周期 RPC（如搜索防抖请求、封面懒加载、章节状态拉取）中，请求通常在数十毫秒内即兑现。若直接裸用 `AbortSignal.timeout(15000)`，该定时器在请求结束后仍会在浏览器引擎内部挂满 15 秒并持有引用，在频繁页面切换或热重载时会导致大量悬空定时器堆积，阻碍垃圾回收（GC）。

#### 纸间最佳架构实践：受控定时器 + 原生 `AbortSignal.any()`

纸间采取两者优势结合的工程范式：

1. **可控超时生命周期**：采用 `AbortController` + `setTimeout`，并在请求 `finally` 阶段立即执行 `clearTimeout(timer)`，杜绝无意义定时器空转；
2. **零胶水复合信号合成**：当调用方传入 `callerSignal` 时，直接通过原生 `AbortSignal.any([controller.signal, callerSignal])` 交由引擎底层合成，**彻底消除手写 `addEventListener('abort')` 与 `removeEventListener` 的样板胶水与闭包泄漏风险**；
3. **一致的异常模型**：超时发生时保持统一的人性化 `TimeoutError: 请求超时，请重试` 提示；
4. **平滑降级**：在不支持 `AbortSignal.any` 的老旧宿主中无缝退回单次事件监听机制。

```ts
// ✅ 纸间现代复合信号标准（src/api/client.ts）
function combineSignals(
  timeoutMs: number,
  callerSignal?: AbortSignal | null,
): { signal: AbortSignal; cleanup: () => void } {
  const controller = new AbortController()
  const timer = setTimeout(() => {
    controller.abort(new DOMException('请求超时，请重试', 'TimeoutError'))
  }, timeoutMs)

  const cleanup = () => {
    clearTimeout(timer)
  }

  if (!callerSignal) {
    return { signal: controller.signal, cleanup }
  }

  if (callerSignal.aborted) {
    clearTimeout(timer)
    controller.abort(callerSignal.reason)
    return { signal: controller.signal, cleanup }
  }

  // 现代环境：原生复合信号合成，由引擎底层调度
  if (typeof AbortSignal !== 'undefined' && 'any' in AbortSignal) {
    return {
      signal: AbortSignal.any([controller.signal, callerSignal]),
      cleanup,
    }
  }

  // 旧版降级：传统一次性事件监听
  const onAbort = () => {
    clearTimeout(timer)
    controller.abort(callerSignal.reason)
  }
  callerSignal.addEventListener('abort', onAbort, { once: true })

  return {
    signal: controller.signal,
    cleanup: () => {
      clearTimeout(timer)
      callerSignal.removeEventListener('abort', onAbort)
    },
  }
}
```

---

### 2.4 `HTMLImageElement.prototype.decode()` — 异步离屏图片解码管线（Baseline 2020）

**MDN**：[HTMLImageElement.decode()](https://developer.mozilla.org/en-US/docs/Web/API/HTMLImageElement/decode)  
**Baseline**：2020 · 全主流浏览器通用  
**本项目落地位置**：`src/components/HtmlCanvasSurface.vue` 与漫画预载逻辑

#### 核心痛点与优化

在漫画阅读器渲染超大分辨率跨页或 HTML Canvas 进行节点栅格化绘制时，如果直接把已下载的 `<img>` 塞入 DOM 或 Canvas，浏览器主线程会在栅格化（Rasterization）帧同步阶段执行昂贵的图片解码计算，导致 16ms 丢帧卡死。

`img.decode()` 将图像解码调度到后台合成线程：

```ts
// 等待子树所有图片解码就绪，彻底杜绝 Canvas 绘制白屏与主线程卡顿
await Promise.all(
  images.map(async (img) => {
    if (img.complete) return
    try {
      await img.decode()
    } catch {
      // 容错：遇到损坏图片不阻塞整体绘制
    }
  }),
)
```

---

### 2.5 `Set.prototype` 原生集合运算 — 零分配标签过滤体系（Baseline 2024）

**MDN**：[Set methods](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Set#set_composition_methods)  
**Baseline**：2024 · Chrome 122+ · Firefox 127+ · Safari 17+ · Node.js 22.0+  
**主要 API**：`setA.intersection(setB)` / `setA.union(setB)` / `setA.difference(setB)` / `setA.isSubsetOf(setB)`

#### 纸间标签系统实战场景（`TagFilterBar.vue` & `useLibraryFilter.ts`）

漫画书架具备多标签交集筛选（“既包含标签 A 又包含标签 B”）与差集过滤（“排除标签 C”）：

```ts
// 传统写法：反复通过 Array.from 与 filter 生成临时数组，大书架场景 GC 频繁
const activeSet = new Set(selectedTags)
const matches = comics.filter((comic) => [...activeSet].every((t) => comic.tagSet.has(t)))

// ✅ 现代原生集合写法：0 临时中间数组，引擎级 C++ 极速哈希比对
const selectedTagsSet = new Set(selectedTags)
const hasAllTags = selectedTagsSet.isSubsetOf(comic.tagSet)
const hasExcludedTags = comic.tagSet.intersection(excludedTagsSet).size > 0
```

---

### 2.6 `Map.groupBy` / `Object.groupBy` — 声明式多维数据聚合（Baseline 2024）

**MDN**：[Map.groupBy()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Map/groupBy) · [Object.groupBy()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/groupBy)  
**Baseline**：2024 · Chrome 117+ · Firefox 119+ · Safari 17.4+ · Node.js 21.0+

#### 纸间多章节切片实战

在详情页和阅读器目录树中，需要将拍平的 `pages`（1..N）按章节 ID 或分卷聚合：

```ts
// 传统写法：手写 reduce 样板代码，并需要防御性创建空数组
const byChapter = pages.reduce<Record<string, Page[]>>((acc, p) => {
  ;(acc[p.chapterId] ??= []).push(p)
  return acc
}, {})

// ✅ 现代标准写法：语义清晰，单次扫描完成分组
const pagesByChapter = Map.groupBy(pages, (page) => page.chapterId)
```

---

## 3. 渐进增强特性（Progressive Enhancement & Newly Available）

### 3.1 Iterator Helpers — 生成器流式管道与惰性求值（Baseline 2025）

**MDN**：[Iterator](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Iterator)  
**Baseline**：2025 · Chrome 122+ · Firefox 131+ · Safari 18.4+ · Node.js 22.0+

#### 核心价值

允许在任意生成器或迭代器上直接链式调用 `.map()`、`.filter()`、`.take(N)`、`.drop(N)`、`.toArray()`，无需将成千上万项元素先全量转换为中间 Array。

**纸间落地蓝图（`useUploadQueue.ts` / IndexedDB 惰性切片）**：

```ts
// 面对单行本数百张图片的批量上传，无需 slice 大数组，流式按需分批：
function* fileGenerator(files: File[]) {
  for (const f of files) yield f
}

const batch = fileGenerator(allFiles).drop(completedOffset).take(batchSize).toArray()
```

---

### 3.2 Explicit Resource Management（`using` / `Symbol.dispose`）— 声明式 RAII 作用域资源清理

**MDN**：[using statement](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/using)  
**支持**：Chrome 134+ · Firefox 141+ · Safari TP · Node.js 24+ · TypeScript 5.2+

#### 解决的痛点

在处理 Blob 预览地址、临时 Canvas、Worker 连接或事件订阅时，传统代码充斥着繁琐的 `try...finally { URL.revokeObjectURL(url) }`。

`using` 提供类似 C++ / Rust 的 RAII（Resource Acquisition Is Initialization）作用域守卫：

```ts
class TempBlobUrl implements Disposable {
  constructor(public readonly url: string) {}
  [Symbol.dispose]() {
    URL.revokeObjectURL(this.url)
  }
}

// 块级作用域退出时（无论正常结束还是抛出异常），自动调用 [Symbol.dispose] 撤销 URL
{
  using blobRef = new TempBlobUrl(URL.createObjectURL(file))
  await drawPreview(blobRef.url)
} // 立即释放内存
```

---

### 3.3 `Temporal API` — 新一代不可变高精度时间与时区系统（Stage 3-4）

**MDN**：[Temporal](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Temporal)  
**支持**：Firefox 139+ · Chrome 144+ · Safari Preview · Node.js 26+

#### 为什么是现代基建的未来

旧版 `Date` 存在三大历史原罪：

1. **对象可变（Mutable）**：调用 `date.setDate(...)` 直接篡改原对象，极易引发隐藏竞态 Bug；
2. **时区地狱**：计算跨时区（如漫画源所在服务器时区）极其繁琐；
3. **月份 0-indexed 诡异设计**：`getMonth() === 0` 代表一月。

`Temporal` 全量不可变，支持高精度微秒运算：

```ts
const lastReadTime = Temporal.Now.instant()
const elapsed = lastReadTime.since(comic.updatedAt)
console.log(elapsed.total({ unit: 'hours' })) // 精确计算时差
```

**纸间落地决策**：由于移动端 iOS Safari 稳定版尚未全量实装，现阶段保持关注，避免在包体积中捆绑庞大的 polyfill。

---

### 3.4 Import Attributes（`with { type: 'json' }`）— 声明式静态模块导入属性（Baseline 2024 / ES2025）

**MDN**：[import with](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Statements/import/with)  
**Baseline**：2024 · Chrome 125+ · Safari 17.2+ · Firefox 137+ · Node.js 22.0+

#### 核心价值与安全防御

过去在 JavaScript 中直接 `import data from './data.json'` 存在安全风险：如果远端服务被攻击返回了恶意可执行脚本，浏览器若仅凭后缀推断 MIME 类型，可能执行恶意代码。

`with { type: 'json' }` 语法在浏览器引擎解析阶段提供强制静态断言：

```ts
// 静态导入断言（若服务器返回的 MIME 类型不是 application/json，引擎立即阻断执行）
import packageMeta from '../package.json' with { type: 'json' }

// 动态条件导入断言
const themeConfig = await import(`./themes/${themeName}.json`, {
  with: { type: 'json' },
})
```

**纸间落地决策**：在 Vite+ 工具链与 Node 24+ 环境中完全就绪，后续在引入静态 JSON 元数据或本地多语言字典时作为标准范式采用。

---

## 4. 实验草案特性（Experimental / Stage 1-2 Proposals）

> ⚠️ **纸间工程铁律**：严禁在生产构建工具链中安装 Babel 实验性插件或 Babel Macro 来提前使用 Stage 1-2 草案语法。此类特性仅作前瞻记录，等待 TC39 推进至 Stage 4 及主流引擎支持。

### 4.1 模式匹配（Pattern Matching: `match / when`）

- **阶段**：Stage 1
- **展望**：为复杂的 API 状态码、路由分支、漫画状态提供如 Rust/OCaml 般强类型解构匹配，取代庞杂的 `switch` 嵌套。

### 4.2 管道运算符（Pipeline Operator: `|>` 与 Topic `%`）

- **阶段**：Stage 2 (Hack-style)
- **展望**：将深层嵌套的函数调用链 `f(g(h(x)))` 转换为左向右流式流水线 `x |> h(%) |> g(%) |> f(%)`，提升数据加工可读性。

### 4.3 不可变复合类型（Record & Tuple: `#{}` 与 `#[]`）

- **阶段**：Stage 2
- **展望**：原生深层基于值的不可变结构，`#{ a: 1 } === #{ a: 1 }` 直接判定为 `true`，彻底消除前端框架深层比较的计算开销。

### 4.4 高精度进位数值类型（Decimal: `0.1m`）

- **阶段**：Stage 1-2
- **展望**：消除 IEEE 754 浮点精度缺陷（`0.1 + 0.2 === 0.3m`）。本项目非金融场景，关注即可。

### 4.5 安全赋值操作符与 Try 表达式（Safe Assignment `?=`）

- **阶段**：Stage 1
- **展望**：将 `const [err, data] ?= await fetch(...)` 直接收敛在语法层，省去手写包装函数。

---

## 5. 升级路线图（Roadmap）

- [x] **Phase 1: 异步基建安全闭环（2026-09 已完成）**
  - 在 `src/api/client.ts` 落地原生 `AbortSignal.any` + `AbortSignal.timeout`；
  - 在 `useViewTransition.ts`、`router/index.ts`、`useOfflineStorage.ts` 及单元测试插桩中全面实装 `Promise.withResolvers` 与 `Promise.try`；
  - 确立 `env.d.ts` 全局标准契约，确保 `pnpm type-check` 与 `vp check` 0 报错。
- [ ] **Phase 2: 标签与聚合运算下沉（2026-Q4）**
  - 将 `TagFilterBar.vue` 与 `useLibraryFilter.ts` 中的多标签交并集重构为原生 `Set.prototype.intersection` / `difference`；
  - 将目录树和书架分组重构为 `Map.groupBy`。
- [ ] **Phase 3: 流式管道与资源作用域（2027 展望）**
  - 在大批量漫画离线下载与 IndexedDB 分页查询中引入 `Iterator Helpers`；
  - 待 Safari 稳定版正式支持 `using` 后，在图片 Blob 与 Canvas 渲染中采用 RAII 资源守卫。

---

## 6. 参考资源（MDN & 博客专栏）

- [张鑫旭 — Promise.try()和Promise.withResolvers()作用速览 (2026-01)](https://www.zhangxinxu.com/wordpress/2026/01/promise-try-withresolvers/)
- [大知闲闲 — JavaScript还能这样写？！ES2025新语法让代码优雅到极致](https://juejin.cn/post/7566929798098944015)
- [MDN Web Docs — Promise.withResolvers()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/withResolvers)
- [MDN Web Docs — Promise.try()](https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Promise/try)
- [MDN Web Docs — AbortSignal.any()](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/any_static)
- [MDN Web Docs — AbortSignal.timeout()](https://developer.mozilla.org/en-US/docs/Web/API/AbortSignal/timeout_static)
- [TC39 Proposals Repository](https://github.com/tc39/proposals)
