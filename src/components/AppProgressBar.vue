<script setup lang="ts">
/**
 * @file AppProgressBar.vue
 * @description 纸间设计系统标准原子进度条组件。
 *
 * 核心特性：
 * - 纯 CSS 变量驱动（`--progress: 0~1` / `--percent: 0%~100%`），无缝兼容未来原生 CSS `progress()` 函数；
 * - GPU 合成层加速：采用 `transform: scaleX(...)` 搭配 `transform-origin` 渲染，零 Reflow 重排开销；
 * - 拟真非线性加载（Inspired by 前端侦探 xboxyan）：支持 `indeterminate` 模式，基于 `--ease-progress` (cubic-bezier(.08, .81, .29, .99)) 实现先快后慢的真实感进度模拟；
 * - 多形态变体：`track`（3px 药丸槽）、`line`（3px 贴边极细线）、`gauge`（6px 标尺刻度槽）；
 * - 多色彩语意：`accent`（朱砂红）、`success`（松石绿）、`warning`（赭石黄）、`danger`（警示红）、`reader`（暗室专用）；
 * - 完备无障碍：内置 `role="progressbar"`、`aria-valuenow`（确定态）、`aria-valuemin`、`aria-valuemax`、`aria-valuetext`、`aria-label`；
 * - 动效与无障碍降级：支持 `animated`（流光扫描动效）并在 `prefers-reduced-motion: reduce` 下静默降级。
 */

import { computed } from 'vue'

const props = withDefaults(
  defineProps<{
    /** 当前进度值（数值，通常 0~100 或与 max 配合使用） */
    value?: number
    /** 进度最大值，默认为 100 */
    max?: number
    /** 0~1 范围的进度比例（若传入则优先于 value/max 计算） */
    progress?: number
    /** 是否处于未知进度的乐观/占位等待模拟模式（先快后慢拟真进度） */
    indeterminate?: boolean
    /** 外观形态：track (药丸槽 3px), line (极细贴边线 3px), gauge (带边框刻度槽 6px) */
    variant?: 'track' | 'line' | 'gauge'
    /** 色彩语意：accent (朱砂红), success (松石绿), warning (赭石黄), danger (警示红), reader (阅读器暗室) */
    color?: 'accent' | 'success' | 'warning' | 'danger' | 'reader'
    /** 是否启用进行中呼吸/条纹扫描流光动效 */
    animated?: boolean
    /** 是否从右向左反向生长（日漫 RTL 横向阅读模式） */
    invert?: boolean
    /** 无障碍标签文本（aria-label） */
    label?: string
    /** 无障碍数值说明文本（aria-valuetext） */
    valueText?: string
  }>(),
  {
    value: 0,
    max: 100,
    progress: undefined,
    indeterminate: false,
    variant: 'track',
    color: 'accent',
    animated: false,
    invert: false,
    label: '进度',
    valueText: undefined,
  },
)

const fraction = computed(() => {
  if (props.indeterminate) return 0
  if (typeof props.progress === 'number') {
    if (Number.isNaN(props.progress)) return 0
    return Math.min(1, Math.max(0, props.progress))
  }
  const rawMax = typeof props.max === 'number' && !Number.isNaN(props.max) ? props.max : 100
  const safeMax = Math.max(rawMax, 0.0001)
  const rawVal = typeof props.value === 'number' && !Number.isNaN(props.value) ? props.value : 0
  const safeValue = Math.max(0, rawVal)
  return Math.min(1, safeValue / safeMax)
})

const percent = computed(() =>
  Number.isNaN(fraction.value) ? 0 : Math.round(fraction.value * 100),
)

// 动态通过 CSS v-bind 响应式注入，零内联 DOM 胶水代码，零 !important
const scaleTransform = computed(() =>
  props.indeterminate ? undefined : `scaleX(${fraction.value})`,
)
const transformOrigin = computed(() => (props.invert ? '100% 50%' : '0 50%'))

const progressStyle = computed(() => {
  const rawMax = typeof props.max === 'number' && !Number.isNaN(props.max) ? props.max : 100
  const safeMax = Math.max(rawMax, 0.0001)
  const safeValue =
    typeof props.progress === 'number' && !Number.isNaN(props.progress)
      ? fraction.value * safeMax
      : Math.max(0, typeof props.value === 'number' && !Number.isNaN(props.value) ? props.value : 0)
  return {
    '--progress': fraction.value,
    '--percent': `${percent.value}%`,
    '--value': safeValue,
    '--max': safeMax,
  }
})
</script>

<template>
  <div
    class="app-progress-bar"
    :class="[
      `app-progress-bar--${variant}`,
      `app-progress-bar--${color}`,
      {
        'is-animated': animated,
        'is-rtl': invert,
        'is-indeterminate': indeterminate,
      },
    ]"
    role="progressbar"
    :aria-valuenow="indeterminate ? undefined : percent"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-valuetext="indeterminate ? '正在加载…' : valueText || `${percent}%`"
    :aria-label="label"
    :style="progressStyle"
  >
    <span class="app-progress-bar__fill" />
  </div>
</template>

<style scoped>
.app-progress-bar {
  position: relative;
  width: 100%;
  overflow: hidden;
  contain: paint;
}

/* 变体 1：track 药丸槽（3px 高度，圆角胶囊） */
.app-progress-bar--track {
  height: 3px;
  border-radius: 999px;
  background: var(--paper-2);
}

/* 变体 2：line 极细贴边线（3px 高度，无圆角，阅读器专用） */
.app-progress-bar--line {
  height: 3px;
  border-radius: 0;
  background: var(--reader-surface-strong);
}

/* 变体 3：gauge 标尺刻度槽（6px 高度，带 1px 装订线边框） */
.app-progress-bar--gauge {
  height: 6px;
  border-radius: var(--radius-1);
  background: var(--paper-2);
  border: 1px solid var(--line);
}

/* 填充条基底：通过 Vue 3 SFC v-bind 注入 CSS 变量与 transform 驱动 */
.app-progress-bar__fill {
  display: block;
  width: 100%;
  height: 100%;
  border-radius: inherit;
  transform: v-bind(scaleTransform);
  transform-origin: v-bind(transformOrigin);
  transition: transform var(--duration-2) var(--ease-out);
  will-change: transform;
}

/* 原生 CSS progress() 渐进增强层（同在 CSS 级联规则中自然覆盖，零 !important） */
@supports (transform: scaleX(progress(1, 0, 10))) {
  .app-progress-bar:not(.is-indeterminate) .app-progress-bar__fill {
    transform: scaleX(progress(var(--value, 0), 0, var(--max, 100)));
  }
}

.app-progress-bar.is-rtl .app-progress-bar__fill {
  transform-origin: 100% 50%;
}

/* 色彩变体 */
.app-progress-bar--accent .app-progress-bar__fill {
  background: var(--accent);
}

.app-progress-bar--success .app-progress-bar__fill {
  background: var(--success);
}

.app-progress-bar--warning .app-progress-bar__fill {
  background: var(--warning);
}

.app-progress-bar--danger .app-progress-bar__fill {
  background: var(--danger);
}

.app-progress-bar--reader {
  background: var(--reader-surface-strong);
}

.app-progress-bar--reader .app-progress-bar__fill {
  background: var(--accent);
}

/* 运行中流光动效（克制斜纹扫描） */
.app-progress-bar.is-animated .app-progress-bar__fill::after {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    100deg,
    transparent 20%,
    color-mix(in oklab, var(--paper-0) 55%, transparent) 50%,
    transparent 80%
  );
  translate: -100% 0;
  animation: app-progress-shimmer 1.6s var(--ease-out) infinite;
}

/* 拟真非线性加载（先快后慢模拟等待） */
.app-progress-bar.is-indeterminate .app-progress-bar__fill {
  animation: app-progress-simulate 10s var(--ease-progress, cubic-bezier(0.08, 0.81, 0.29, 0.99))
    forwards;
}

@keyframes app-progress-simulate {
  0% {
    transform: scaleX(0);
  }
  20% {
    transform: scaleX(0.38);
  }
  50% {
    transform: scaleX(0.68);
  }
  80% {
    transform: scaleX(0.88);
  }
  100% {
    transform: scaleX(0.96);
  }
}

@keyframes app-progress-shimmer {
  to {
    translate: 100% 0;
  }
}

/* 减弱动态无障碍体验 */
@media (prefers-reduced-motion: reduce) {
  .app-progress-bar__fill {
    transition: none !important;
    animation: none !important;
  }
  .app-progress-bar.is-animated .app-progress-bar__fill::after {
    animation: none !important;
  }
}
</style>
