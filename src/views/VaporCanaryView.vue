<script setup lang="ts">
/**
 * @file VaporCanaryView.vue
 * @description Vue 3.6 Vapor Mode 基准跑分与局部探针沙盒视图。
 *
 * 遵循红线 4（视图轻量化，脚本 ≤150 行）与红线 5（Composable 顶层精准解构）。
 */
import { ref } from 'vue'
import { RouterLink } from 'vue-router'
import { useTimeoutFn } from '@vueuse/core'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import VaporBenchItem from '@/components/canary/VaporBenchItem.vue'
import VdomBenchItem from '@/components/canary/VdomBenchItem.vue'
import { useVaporBenchmark } from '@/composables/useVaporBenchmark'

const {
  mode,
  itemCount,
  items,
  isRunning,
  isPatching,
  mountDuration,
  patchAvgDuration,
  patchFps,
  unmountDuration,
  heapUsedMb,
  history,
  hasResults,
  runMountTest,
  runPatchTest,
  runUnmountTest,
  runFullSuite,
  copyReport,
} = useVaporBenchmark()

const copied = ref(false)
const { start: startCopiedReset } = useTimeoutFn(
  () => {
    copied.value = false
  },
  2000,
  { immediate: false },
)

async function handleCopy() {
  const ok = await copyReport()
  if (ok) {
    copied.value = true
    startCopiedReset()
  }
}
</script>

<template>
  <div class="canary-view">
    <header class="canary-header">
      <div class="canary-header-nav">
        <RouterLink to="/" class="canary-back-link">
          <AppIcon name="arrow-left" size="sm" />
          <span>返回书架</span>
        </RouterLink>
        <span class="canary-tag">Vue 3.6 探针</span>
      </div>
      <h1 class="canary-title">无虚树直驱基准沙盒</h1>
      <p class="canary-subtitle">
        Vue 3.6 Vapor Mode（无虚拟 DOM 直接编译）与标准 VDOM 在海量节点下的毫秒级性能横向对比。
      </p>
    </header>

    <section class="canary-panel surface">
      <div class="panel-controls">
        <div class="control-group">
          <span class="control-label">渲染引擎</span>
          <div class="engine-tabs">
            <button
              type="button"
              class="engine-tab"
              :class="{ 'is-active': mode === 'vapor' }"
              @click="mode = 'vapor'"
            >
              Vapor 直驱
            </button>
            <button
              type="button"
              class="engine-tab"
              :class="{ 'is-active': mode === 'vdom' }"
              @click="mode = 'vdom'"
            >
              VDOM 虚树
            </button>
          </div>
        </div>

        <div class="control-group">
          <span class="control-label">节点规模</span>
          <div class="engine-tabs">
            <button
              v-for="cnt in [500, 1000, 2000, 3000]"
              :key="cnt"
              type="button"
              class="engine-tab"
              :class="{ 'is-active': itemCount === cnt }"
              @click="itemCount = cnt"
            >
              {{ cnt }}
            </button>
          </div>
        </div>

        <div class="panel-actions">
          <AppButton
            variant="primary"
            size="sm"
            icon="play"
            type="button"
            :disabled="isRunning"
            @click="runFullSuite"
          >
            {{ isRunning ? '测试中…' : '一键全流程跑分' }}
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            type="button"
            :disabled="isRunning"
            @click="runMountTest"
          >
            挂载节点
          </AppButton>
          <AppButton
            variant="secondary"
            size="sm"
            type="button"
            :disabled="isRunning || items.length === 0"
            @click="() => runPatchTest(60)"
          >
            {{ isPatching ? '高频更新中…' : '60 帧补丁压测' }}
          </AppButton>
          <AppButton
            variant="ghost"
            size="sm"
            type="button"
            :disabled="isRunning || items.length === 0"
            @click="runUnmountTest"
          >
            卸载清空
          </AppButton>
        </div>
      </div>

      <!-- 实时仪表盘 -->
      <div class="metrics-grid">
        <div class="metric-card">
          <span class="metric-name">初始挂载耗时</span>
          <span class="metric-value">
            {{ mountDuration !== null ? `${mountDuration} ms` : '—' }}
          </span>
          <span class="metric-hint">DOM 树构建与首帧提交</span>
        </div>
        <div class="metric-card">
          <span class="metric-name">高频补丁单帧</span>
          <span class="metric-value">
            {{ patchAvgDuration !== null ? `${patchAvgDuration} ms` : '—' }}
          </span>
          <span class="metric-hint">
            {{ patchFps !== null ? `理论计算 ~${patchFps} FPS` : '状态原地响应' }}
          </span>
        </div>
        <div class="metric-card">
          <span class="metric-name">节点卸载耗时</span>
          <span class="metric-value">
            {{ unmountDuration !== null ? `${unmountDuration} ms` : '—' }}
          </span>
          <span class="metric-hint">DOM 树清除与作用域注销</span>
        </div>
        <div class="metric-card">
          <span class="metric-name">JS 堆内存用量</span>
          <span class="metric-value">
            {{ heapUsedMb !== null ? `${heapUsedMb} MB` : 'N/A' }}
          </span>
          <span class="metric-hint">Chromium 堆内存采样</span>
        </div>
      </div>

      <div v-if="hasResults" class="history-section">
        <div class="history-head">
          <h3 class="history-title">测试记录明细 ({{ history.length }})</h3>
          <AppButton
            variant="ghost"
            size="xs"
            :icon="copied ? 'check' : 'copy'"
            type="button"
            @click="handleCopy"
          >
            {{ copied ? '已复制 Markdown' : '复制跑分结果' }}
          </AppButton>
        </div>
        <div class="history-table-wrap">
          <table class="history-table">
            <thead>
              <tr>
                <th>时间</th>
                <th>模式</th>
                <th>数量</th>
                <th>挂载</th>
                <th>微粒补丁</th>
                <th>卸载</th>
                <th>堆内存</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="(h, idx) in history" :key="idx">
                <td>{{ h.timestamp }}</td>
                <td>
                  <span class="badge-stamp" :class="h.mode === 'vapor' ? 'is-vapor' : 'is-vdom'">
                    {{ h.mode.toUpperCase() }}
                  </span>
                </td>
                <td>{{ h.itemCount }}</td>
                <td>{{ h.mountMs }} ms</td>
                <td>{{ h.patchAvgMs }} ms ({{ h.patchFps }} fps)</td>
                <td>{{ h.unmountMs }} ms</td>
                <td>{{ h.heapMb ? `${h.heapMb} MB` : '—' }}</td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </section>

    <!-- 动态节点网格 -->
    <section v-if="items.length > 0" class="canvas-grid-section">
      <div class="grid-status-bar">
        <span>已渲染 {{ items.length }} 个节点 · 模式：{{ mode.toUpperCase() }}</span>
      </div>
      <div class="items-grid">
        <template v-if="mode === 'vapor'">
          <VaporBenchItem
            v-for="item in items"
            :key="item.id"
            :id="item.id"
            :title="item.title"
            :progress="item.progress"
            :active="item.active"
          />
        </template>
        <template v-else>
          <VdomBenchItem
            v-for="item in items"
            :key="item.id"
            :id="item.id"
            :title="item.title"
            :progress="item.progress"
            :active="item.active"
          />
        </template>
      </div>
    </section>
  </div>
</template>

<style scoped>
.canary-view {
  max-width: 76rem;
  margin: 0 auto;
  padding: var(--space-6) var(--space-4) var(--space-12);
}

.canary-header {
  margin-bottom: var(--space-6);
}

.canary-header-nav {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.canary-back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-sm);
  color: var(--ink-2);
  text-decoration: none;
  transition: color var(--duration-1) var(--ease-out);
}

.canary-back-link:hover {
  color: var(--ink-0);
}

.canary-tag {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--accent);
  background: color-mix(in oklab, var(--accent) 12%, transparent);
  border: 1px solid color-mix(in oklab, var(--accent) 25%, transparent);
  padding: 0 var(--space-2);
  border-radius: var(--radius-pill);
}

.canary-title {
  font-family: var(--font-display);
  font-size: var(--text-2xl);
  color: var(--ink-0);
  margin: 0 0 var(--space-1);
}

.canary-subtitle {
  font-size: var(--text-sm);
  color: var(--ink-2);
  margin: 0;
  max-width: 46rem;
  line-height: var(--leading-relaxed);
}

.canary-panel {
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  padding: var(--space-5);
  margin-bottom: var(--space-6);
}

.panel-controls {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--line);
}

.control-group {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.control-label {
  font-size: var(--text-xs);
  color: var(--ink-2);
  font-weight: 500;
}

.engine-tabs {
  display: inline-flex;
  background: var(--paper-2);
  border-radius: var(--radius-1);
  padding: 2px;
  gap: 2px;
}

.engine-tab {
  font-size: var(--text-xs);
  padding: var(--space-1) var(--space-2-5);
  border: none;
  background: transparent;
  color: var(--ink-2);
  border-radius: var(--radius-1);
  cursor: pointer;
  transition:
    background-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.engine-tab.is-active {
  background: var(--paper-0);
  color: var(--ink-0);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}

.panel-actions {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: var(--space-2);
  margin-left: auto;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(13rem, 1fr));
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.metric-card {
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  padding: var(--space-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.metric-name {
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.metric-value {
  font-family: var(--font-display);
  font-size: var(--text-xl);
  font-weight: 700;
  color: var(--accent);
}

.metric-hint {
  font-size: var(--text-xs);
  color: var(--ink-3);
}

.history-section {
  margin-top: var(--space-5);
  padding-top: var(--space-4);
  border-top: 1px solid var(--line);
}

.history-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-2);
}

.history-title {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-0);
  margin: 0;
}

.history-table-wrap {
  overflow-x: auto;
}

.history-table {
  width: 100%;
  border-collapse: collapse;
  font-size: var(--text-xs);
  font-family: var(--font-mono);
}

.history-table th,
.history-table td {
  padding: var(--space-2);
  text-align: left;
  border-bottom: 1px solid var(--line);
}

.history-table th {
  color: var(--ink-2);
  font-weight: 500;
}

.history-table td {
  color: var(--ink-1);
}

.badge-stamp {
  display: inline-block;
  padding: 1px 6px;
  border-radius: 999px;
  font-size: 10px;
  font-weight: 700;
}

.badge-stamp.is-vapor {
  background: color-mix(in oklab, var(--accent) 15%, transparent);
  color: var(--accent);
}

.badge-stamp.is-vdom {
  background: var(--paper-2);
  color: var(--ink-2);
}

.canvas-grid-section {
  margin-top: var(--space-4);
}

.grid-status-bar {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin-bottom: var(--space-2);
}

.items-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(11rem, 1fr));
  gap: var(--space-2);
}
</style>
