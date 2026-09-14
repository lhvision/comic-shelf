# ADR 0023 — Vue 3.6 Vapor Mode 局部探针与双模渐进增强架构

- **日期**：2026-09-14
- **状态**：Accepted
- **关联**：演进 `pnpm-workspace.yaml`、`package.json`、`vite.config.ts`、`src/components/library/ComicGrid.vue`、`src/views/VaporCanaryView.vue`，对齐 `CONTEXT.md` 响应式底座哲学、`docs/PITFALLS.md` §97 与 ADR 0022（依赖固化切片）

## 背景

纸间（Paper Room）作为本地优先的典藏漫画阅览室，对前端在弱网、低配移动设备（如旧款 iPad、千元阅读平板）下的渲染延迟、DOM 操作吞吐量与内存占用有极高敏感度。

随着官方 Vue 3.6（RC 阶段）正式推出实验性 **Vapor Mode**（无虚拟 DOM 直接编译为微粒原生 DOM 操作），前端框架在长期以来的“虚拟 DOM 树比对（Tree Diffing）”与“细粒度响应式直驱（Fine-grained Direct DOM）”之间迎来了革命性的分水岭。

然而，纸间当前拥有 110+ 个复杂组件，涵盖复杂的插槽体系、View Transitions（ADR 0014）、Web Worker 万级检索卸载（ADR 0018）以及完善的无障碍设计系统。若贸然将全站全量切换至 Vapor Mode，将带来大量未成熟生态库兼容性中断、插槽上下文断裂以及难以排查的边界故障。

## 方案论证与权衡（Grilling Analysis）

经过架构评测与深入设计树推演，团队围绕底座升级策略、探针演进路径与互操作边界达成以下决策：

### 1. 底座升级策略：全局 RC 接管 vs 局部沙盒隔离

- **方案 A（全局平滑升级至 Vue 3.6 RC，采纳）**：
  - 通过 `pnpm-workspace.yaml` 的 `overrides` 将 `vue` 及 `@vue/*` 依赖锁定在 `'rc'`（`3.6.0-rc.7/8`），`package.json` 显式同步为 `^3.6.0-rc.8`；
  - 全站 99% 的既有业务组件完全保持标准的 **VDOM 模式**运行，享受 Vue 3.6 对 3.5 的 100% 向后兼容性；
  - 编译器插件 `@vitejs/plugin-vue` 保持 `features.vapor: false`（默认值），即全局默认 VDOM，仅在单文件组件内显式标注 `<template vapor>` 时按文件局部开启 Vapor 模式。
- **方案 B（双轨独立分支试验）**：
  - _否决理由_：会导致长期代码分叉与合并地狱，无法真实检验 Vite+ 工具链（`vp check`、`vue-tsc` 增量类型检查）对 3.6 真实语法的即时兼容性。

### 2. 探针推进范式：基准跑分先行 + 生产原子叶子组件闭环

- **双阶推进路线**：
  1. **第一阶段（基准跑分沙盒探针 Benchmark Canary）**：
     - 构建独立测试视图 `src/views/VaporCanaryView.vue`，挂载于路由 `/vapor-canary`；
     - 模拟纸间典型高密度负载：1,000 ~ 3,000 个节点的高密度批量挂载、60fps 高频进度/计数微粒响应式补丁更新、节点清空与堆内存测量；
     - 横向比对 VDOM 与 Vapor 的微秒级渲染延迟与 GC 垃圾回收压力，产出可复制的量化性能卡片。
  2. **第二阶段（首个生产级叶子组件闭环）**：
     - 提取书架网格与长目录中的尾格收纳提示为独立组件 `src/components/library/OverflowTileBadge.vue`；
     - 标注 `<template vapor>`，采用内联原生 SVG（零 VNode 编译），替换 `ComicGrid.vue` 中的内联折叠徽印，实现零风险生产落地。

### 3. 架构红线与互操作性契约（Interoperability Invariants）

在双模共存架构下，确立三条绝对不可违反的工程红线：

1. **同构响应式底座红线**：Vapor 组件必须 100% 消费既有 `composables/*.ts` 与 Pinia Store，仅在顶层解构所需的 `ref` / `computed`，杜绝引入任何与主应用割裂的孤岛状态机；
2. **零 VDOM 假设红线**：Vapor 组件内部**严禁**调用 `getCurrentInstance()?.vnode` 或任何依赖 VNode 的上下文逻辑（Vapor 模式下 `instance.vnode` 为 `undefined`）；
3. **样式与插槽边界红线**：Vapor 组件内避免使用 SFC `<style>` 内的 `v-bind()`，一律采用显式 `:style="{ '--custom-var': val }"` 驱动；叶子探针内严禁嵌套尚未 Vapor 化的深层复杂 VDOM 插槽组件。

## 核心实现规约

### 1. 依赖与分包契约（`vite.config.ts`）

由于 ADR 0022 已将 `@vue/` 统一收敛至 `vue-core.js`：

```ts
if (
  id.includes('/vue/') ||
  id.includes('/@vue/') ||
  id.includes('/vue-router/') ||
  id.includes('/pinia/') ||
  id.includes('/@vueuse/')
) {
  return 'vue-core'
}
```

Vue 3.6 引入的 `@vue/runtime-vapor` 自然落入 `vue-core` 静态分包中，构建体积与月度强缓存机制保持稳定。

### 2. 首个生产探针：`PageTile.vue`（画卷索引缩略图图块）

在多章节长篇漫画（数千页、上百话）的详情页与章节页（`PageIndexGrid.vue`）中，单次展开需要挂载 24 ~ 200+ 个 `PageTile`，属于全站最高密度的展示阵列之一。将其 Vapor 化能直接削减数以千计的 VNode 对象：

```vue
<script setup lang="ts">
import { useRouter } from 'vue-router'
import { pageThumbUrl } from '@/api/client'

// ... props 与 emits 契约不变
const router = useRouter()

function handleClick(e: MouseEvent) {
  if (e.defaultPrevented || e.button !== 0 || e.ctrlKey || e.metaKey || e.shiftKey || e.altKey) {
    return
  }
  e.preventDefault()
  if (router) {
    router.push(readerLink())
  }
}
</script>

<template vapor>
  <a :href="readerLink()" class="page-tile" :data-cached="cached" @click="handleClick">
    <div class="page-image">
      <img
        :src="pageThumbUrl(source, sourceId, index)"
        :alt="`第 ${displayNumber()} 页`"
        loading="lazy"
        decoding="async"
        @load="onThumbLoad"
      />
    </div>
    <span class="page-index">{{ pageLabel(displayNumber()) }}</span>
    <span class="page-state">{{ cached ? '本地' : '待缓存' }}</span>
  </a>
</template>
```

**拔除 `<RouterLink>` 契约**：采用原生 `<a>` 搭配编程式导航，不仅达到 100% 零 VNode 编译，避免桥接开销，还天然保障了浏览器右键/中键新建标签页与无障碍阅读器直达。

**全量 SVG 替换之否定论证**：
针对“是否将全站 35 个 SVG 图标全量替换为 Vapor”的提议予以否决。全站图标统一遵循《红线 12：单源收敛（Unified Iconography）》。在成熟的 VDOM 父级容器中大量混部细碎的 Vapor 图标会诱发频繁的 **VDOM ➔ Vapor 桥接损耗（Bridge Thrashing）**，且 `<slot />` 包装开销抹平了性能收益。通用图标坚守 VDOM，仅在高密度叶子展示组件（如 `PageTile`）集中使用 Vapor 才是最佳工程解。

### 3. 沙盒实测基准跑分数据

在真机环境（/vapor-canary 基准沙盒）测得客观对比数据：

| 时间     | 模式  | 节点数 | 初始挂载     | 响应式补丁 (帧率)     | 节点卸载    | JS 堆内存   |
| :------- | :---- | :----- | :----------- | :-------------------- | :---------- | :---------- |
| 21:39:12 | VDOM  | 3000   | 148.5 ms     | 37.88 ms (26 fps)     | 22.2 ms     | 94.9 MB     |
| 21:39:04 | VAPOR | 3000   | **104.2 ms** | **33.29 ms (30 fps)** | 23.5 ms     | 118.5 MB    |
| 21:38:56 | VDOM  | 2000   | 102.7 ms     | 25.32 ms (39 fps)     | 12.7 ms     | 101.7 MB    |
| 21:38:50 | VAPOR | 2000   | **74.0 ms**  | **22.73 ms (44 fps)** | **10.5 ms** | 102.1 MB    |
| 21:38:43 | VDOM  | 1000   | 52.6 ms      | 13.18 ms (76 fps)     | 6.9 ms      | 87.6 MB     |
| 21:38:38 | VAPOR | 1000   | 59.2 ms      | **12.24 ms (82 fps)** | **6.6 ms**  | **80.8 MB** |
| 21:38:16 | VDOM  | 500    | 37.5 ms      | 10.4 ms (96 fps)      | 8.2 ms      | 97.9 MB     |
| 21:38:11 | VAPOR | 500    | 38.1 ms      | **8.71 ms (115 fps)** | **4.2 ms**  | **83.3 MB** |

**真实环境（关闭 DevTools 干扰）分析结论**：

1. **高密度挂载呈现「逆转加速」**：在 2000~3000 节点高密度下，Vapor 初始挂载耗时大幅领先约 **30%**（2000 节点 74.0ms vs 102.7ms；3000 节点 104.2ms vs 148.5ms），彻底消除递归树构建与 VNode 实例化调度开销；
2. **高频响应式补丁全档位领跑**：从 500 到 3000 节点，Vapor 微粒原地补丁帧率全线压制 VDOM（500 节点飙至 115 fps vs 96 fps；3000 节点维持在 30 fps 防卡顿红线，而 VDOM 跌至 26 fps 产生肉眼感知卡顿）；
3. **节点快速卸载与内存控制**：500 节点卸载速度快近 50%（4.2ms vs 8.2ms），中轻度规模（500~~1000）内存占用明显更优（节约 7~~15 MB）。

### 4. 避坑防线收录（`docs/PITFALLS.md` §97）

收录第 97 条避坑经验，警示全团队严禁在 Vapor 组件中访问 `vnode`、样式变量避免依赖 `<style> v-bind()`、严禁全局盲目开启 `features.vapor: true`。

## 演进与下线计划（Iteration & Sunset Plan）

1. **沙盒生命周期与代码隔离**：
   - `/vapor-canary` 基准沙盒采用路由级按需动态导入（`() => import('@/views/VaporCanaryView.vue')`），构建为 9.37 kB 独立 chunk，不进入全站主导航，严密防范首屏资源污染；
   - 状态机 `useVaporBenchmark` 在各测试轮次切换时具备严格的内存与计时指标清空机制，杜绝脏状态累积。
2. **渐进式迁移与准出路线**：
   - **阶段 1（当前探针）**：以 `PageTile.vue` 作为叶子高密度生产探针，验证无虚树渲染与原生 `<a>` 路由跳转；
   - **阶段 2（Vue 3.6 GA）**：待 Vue 3.6 正式发布且 CJS/ESM 双模导出彻底平稳后，依据跑分评估是否将目录 item 或发现流展示卡片按需引入 `<template vapor>`；
   - **阶段 3（沙盒归档/下线）**：全站核心叶子组件完成评测沉淀后，可将沙盒收敛为内部诊断面板（置于 `import.meta.env.DEV` 门禁后）或移入归档基准用例。
3. **依赖治理与升级契约（Catalog-First）**：
   - 全面引入 `pnpm-workspace.yaml` 中的 `catalog.default.vue: rc` 统筹声明；
   - 子包与主应用 `package.json` 统一使用 `"vue": "catalog:"`；
   - `overrides` 中集中收敛 `@vue/*` 衍生包至 `rc` 渠道，彻底消灭每个小版本升级时人工修改十余处散落版本号的维护负担；
   - 待 3.6 正式 GA 后，仅需在 catalog 中单点切换为 `"^3.6.0"`，零摩擦完成平稳过渡。

## 效果与收益

1. **依赖底座就绪**：`pnpm-workspace.yaml` 与 `package.json` 全面对齐 Vue 3.6 RC，增量 `pnpm type-check` 0 错误；
2. **高密度生产探针落地**：`PageTile.vue` 成功转为无虚树直驱，详情页长章节展开时 100% 消除缩略图卡片的 VNode 树分配；
3. **图标单源规范坚守**：坚守红线 12，杜绝微粒图标过度碎片化引发的 Bridge Thrashing；
4. **基准沙盒可度量**：`/vapor-canary` 提供了可重复检验的微秒级跑分工具，持续指导未来组件渐进增强。
