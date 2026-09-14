# ADR 0022 — 依赖固化切片与权限视图按需分流架构

- **日期**：2026-09-14
- **状态**：Accepted
- **关联**：演进 `vite.config.ts`、`src/App.vue`、`src/components/AppHeader.vue` 与 `src/views/LibraryView.vue`，对齐 `CONTEXT.md` 基础设施哲学与 ADR 0005（PWA 离线存储）

## 背景

纸间（Paper Room）定位于「本地优先的个人漫画收藏夹与典藏阅览室」。前端技术栈采用 Vite+（基于 Vite 8 与 Rolldown 1.2.5）+ Vue 3 SPA。在早期的演进中，项目保持了极度轻量的生产依赖（仅 Vue、Vue Router、Pinia、VueUse 四大核心包），构建速度维持在 1.7~2.0 秒。

然而，通过对生产构建产物进行深度审计，发现了以下三项影响长效缓存命中率与读者首屏纯净度的细节瓶颈：

1. **框架与业务混包导致缓存雪崩（Cache Invalidation Coupling）**：`vite.config.ts` 未配置 `manualChunks`，Vue 核心三件套与业务逻辑共同打包入单个 `index.js`（92.8 kB gzip）。当开发者仅修改一个通用业务组件或样式时，整个 92.8 kB 入口哈希全部重算，迫使所有读者重新拉取几乎从不变更的 Vue/Pinia/Router 底层运行时；
2. **权限管理与门禁视图污染读者首屏（Curator Code Leakage）**：
   - 访客借阅时不需要的通行证管理抽屉（`GuestModal.vue`）被静态导入至顶栏 `AppHeader.vue`；
   - 仅馆长可见的作品收录面板（`ImportPanel.vue`）被静态导入至书架主视图 `LibraryView.vue`；
   - 已登录或局域网免密状态下永远不会渲染的门禁大门（`GateView.vue`）被静态导入至根组件 `App.vue`；
   - 这些低频/权限隔离的代码占用了普通读者首屏的解析与带宽开销；
3. **实验性 CSS 语法引发构建噪音**：Chrome 135+ 原生 CSS Carousel 实验特性（`::scroll-marker`）在底层构建工具链（LightningCSS 1.33）早期草案 AST 校验下触发了伪类/伪元素警告。

## 方案论证与权衡（Grilling Analysis）

团队围绕长效缓存生命周期、PWA 预缓存预算与异步按需加载展开了深度论证：

### 1. 框架切片粒度决策（Vendor Splitting Boundary）

- **路线 A（激进碎片化拆包）**：按每个 npm package 拆散为 10+ 个细碎 chunk。
  - _否决理由_：在 HTTP/2 多路复用下，过多微型 chunk（<5 kB）会显著拉长模块解析调用链并破坏 Rolldown 的内联优化。
- **路线 B（宽泛全量 node_modules 打包）**：将所有第三方依赖统一归入单一 `vendor.js`。
  - _否决理由_：未来一旦引入构建伴生库或微调辅助工具，仍会导致巨型 vendor 整体失效。
- **路线 C（全站基石四大件固化切片，采纳）**：
  - 精准将全站每个页面均必不可少的四大核心运行时（`@vue/`, `vue`, `pinia`, `vue-router`, `@vueuse/core`）固化为命名高度自解释的 `vue-core.js`（约 53 kB gzip）；
  - 业务入口 `index.js` 骤降至 23.5 kB gzip；
  - 框架依赖享受服务器 `Cache-Control: public, max-age=31536000, immutable` 永久强缓存，实现月度/年度级别的零重复网络开销。

### 2. PWA 预缓存预算决策（Precache Scope Budget）

- **权衡考量**：在将权限视图转为异步组件后，是否将非核心组件从 PWA Service Worker 预缓存中剔除？
- **最终决策**：**维持 981 KiB 全量预缓存预算不变**。
  - 纸间定位是「本地优先典藏室」，整站静态资产仅约 980 KiB（不及一张单页漫画原图大小）；
  - 全量预缓存使 `GateView`、`GuestModal`、`ImportPanel` 在后台静默就绪；
  - 异步组件在被馆长点击唤起时，100% 毫秒级命中 Cache Storage，彻底杜绝了异步加载常见的网络闪烁与骨架等待，兼顾了读者端精简与馆长端秒开。

### 3. 异步组件切分清单（Async Component Targets）

| 组件              | 原宿主            | 触发时机                           | 优化后收益                                 |
| :---------------- | :---------------- | :--------------------------------- | :----------------------------------------- |
| `GateView.vue`    | `App.vue`         | 仅未认证/口令保护状态挂载          | 已登录读者与内网免密环境 0 字节            |
| `GuestModal.vue`  | `AppHeader.vue`   | 仅馆长点击顶栏「通行证」按钮挂载   | 普通访客/未点击馆长 0 字节（减负 ~21 kB）  |
| `ImportPanel.vue` | `LibraryView.vue` | 仅馆长（`canWrite`）进入书架时挂载 | 普通访客首屏直接减负 ~13 kB JS + 12 kB CSS |

## 核心实现规约

### 1. `vite.config.ts` Manual Chunks 配置

```ts
build: {
  rollupOptions: {
    output: {
      manualChunks(id) {
        if (id.includes('node_modules')) {
          if (
            id.includes('/vue/') ||
            id.includes('/@vue/') ||
            id.includes('/vue-router/') ||
            id.includes('/pinia/') ||
            id.includes('/@vueuse/')
          ) {
            return 'vendor-core'
          }
        }
      },
    },
  },
},
```

### 2. 权限视图与重型弹窗异步导入范式

在 Vue SFC 中统一采用 `defineAsyncComponent` 并搭配 `v-if` 门禁：

```vue
<!-- AppHeader.vue -->
<script setup lang="ts">
import { defineAsyncComponent } from 'vue'
const GuestModal = defineAsyncComponent(() => import('@/components/curator/GuestModal.vue'))
</script>

<template>
  <!-- 仅馆长具有操作权限时才挂载该异步组件 -->
  <GuestModal v-if="canWrite" />
</template>
```

## 成果与指标对比

在同一物理环境下执行 `vp build` 的关键产物指标变化：

| 产物项                      | 优化前 (Raw / Gzip)  | 优化后 (Raw / Gzip)          | 变化幅度                              |
| :-------------------------- | :------------------- | :--------------------------- | :------------------------------------ |
| 业务主入口 `index.js`       | 267.95 kB / 92.77 kB | **65.56 kB / 23.57 kB**      | 📉 **体积缩减 74.6%**                 |
| 全局主样式 `index.css`      | 96.17 kB / 14.96 kB  | **57.50 kB / 10.08 kB**      | 📉 **体积缩减 32.6%**                 |
| 书架主视图 `LibraryView.js` | 66.14 kB / 22.68 kB  | **54.54 kB / 18.84 kB**      | 📉 **减负 ~12 kB**                    |
| 框架核心包 `vue-core.js`    | 无（与业务混包）     | **141.25 kB / 53.76 kB**     | 🛡️ **固化强缓存**                     |
| 构建耗时（Rolldown）        | 1.69s                | **1.55s ~ 1.63s**            | ⚡ **极速无衰减**                     |
| CSS Carousel 前瞻渐进增强   | 6 条非致命提示       | **规范保留（零 JS 轮播点）** | 🎯 **按需保留前瞻特性（非致命告警）** |

## 避坑与防退化红线

1. **严禁在 `manualChunks` 中引入业务目录路径**：`vue-core` 必须仅限稳定公共底层库，严禁将 `src/stores/` 或 `src/composables/` 强制放入 vendor，防范循环引用与模块死锁；
2. **严禁将核心阅读链路组件过度异步化**：阅读器视口（`ReaderViewport`）、翻页胶囊（`ReaderChapterBanners`）等必须坚守同步加载，杜绝翻页阅读心流中产生网络分片延迟；
3. **坚守 PWA 全量预缓存底线**：新增通用视图或组件时，必须确保其包含在 Service Worker 预缓存模式中，杜绝因脱网导致异步组件 Chunk 加载失败。
