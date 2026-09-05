<script setup lang="ts">
import { ref, watch } from 'vue'
import Tooltip from '@/components/Tooltip.vue'

/**
 * 文本多行自适应截断组件（AppTextClamp）。
 *
 * 业务职责：
 * - 对单行/多行超长文本进行 CSS line-clamp 截断与优雅打点；
 * - 结合现代浮层体系（HTML Popover API + CSS Anchor Positioning），提供暖纸质感悬停气泡查阅全文；
 * - 性能与鲁棒性架构（JIT 纯按需测量）：
 *   1. 默认仅渲染基础语义标签，绝不挂载多余的 Tooltip DOM 节点；
 *   2. 首屏挂载与初始渲染阶段执行 0 次 DOM 尺寸测量，彻底消除微任务队列中的 Forced Reflow 掉帧瓶颈；
 *   3. 几何探测推迟至读者意图触发时刻（光标进入 pointerenter、触碰 touchstart、键盘聚焦 focusin）；
 *   4. 文案更新时仅重置截断标记（isTruncated = false），下次交互时自动 JIT 重算；
 *   5. 仅当文案真实发生溢出打点（isTruncated）时才动态激活气泡，短文本 0 弹窗、0 误打扰；
 *   6. 离开后即时休眠，全局 window 滚动监听器保持 0 占用。
 */

interface Props {
  /** 待展示与截断的完整文本文案 */
  text?: string
  /** 语义化 HTML 标签类型（如 span, p, h2, dd 等，默认 'span'） */
  as?: string
  /** 最大允许展示行数（超出即截断打点，默认 1） */
  lines?: number
  /** 气泡浮层宽度上限（默认 '24rem'） */
  tooltipWidth?: string
  /** 气泡浮层最大高度（超出开启内部水墨细滚动条，默认 '16rem'） */
  tooltipMaxHeight?: string
  /** 气泡弹层方位（默认 'top'） */
  tooltipSide?: 'top' | 'right' | 'bottom' | 'left'
  /** 气泡对齐方式（默认 'start'） */
  tooltipAlign?: 'start' | 'center' | 'end'
  /** 气泡唤起延迟 (ms，默认 120ms，卡片密集区建议 350ms) */
  delay?: number
  /** 气泡关闭缓冲延迟 (ms，默认 250ms) */
  hideDelay?: number
  /** 是否作为块级容器撑满父级宽度（默认 true） */
  block?: boolean
  /** 是否启用等宽字体渲染（如车号、页码、日期） */
  mono?: boolean
  /** 强制禁用 Tooltip 气泡提示 */
  disabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  text: '',
  as: 'span',
  lines: 1,
  tooltipWidth: '24rem',
  tooltipMaxHeight: '16rem',
  tooltipSide: 'top',
  tooltipAlign: 'start',
  delay: 120,
  hideDelay: 250,
  block: true,
  mono: false,
  disabled: false,
})

const tooltipRef = ref<InstanceType<typeof Tooltip> | null>(null)
const textRef = ref<HTMLElement | null>(null)
const isTruncated = ref(false)

/**
 * 几何尺寸探测：检查容器是否存在纵向高度截断或横向宽度截断
 * 严格遵循 JIT（Just-In-Time）按需原则，仅在读者交互瞬间执行单次单元素读取
 */
function checkTruncation(): boolean {
  if (props.disabled) {
    isTruncated.value = false
    return false
  }
  const el = textRef.value
  if (!el) return false

  // 1px 容差消除次像素渲染舍入抖动
  const hasVerticalOverflow = el.scrollHeight > el.clientHeight + 1
  const hasHorizontalOverflow = el.scrollWidth > el.clientWidth + 1
  const truncated = hasVerticalOverflow || hasHorizontalOverflow
  isTruncated.value = truncated
  return truncated
}

/**
 * 移动端触碰交互感知：探测溢出并在截断时主动唤起 Tooltip
 */
function handleTouchStart() {
  const truncated = checkTruncation()
  if (truncated && !props.disabled) {
    tooltipRef.value?.show()
  }
}

// 文案更新时重置截断状态，下一次交互时自动按需重新探测，杜绝非交互态下触发布局重排
watch(
  () => props.text,
  () => {
    isTruncated.value = false
  },
)
</script>

<template>
  <Tooltip
    ref="tooltipRef"
    class="app-text-clamp-wrapper"
    :class="{ 'is-block': block }"
    :tip="text"
    :width="tooltipWidth"
    :max-height="tooltipMaxHeight"
    :side="tooltipSide"
    :align="tooltipAlign"
    :disabled="!isTruncated || disabled"
    :delay="delay"
    :hide-delay="hideDelay"
    @pointerenter.capture="checkTruncation"
    @focusin.capture="checkTruncation"
    @touchstart.passive="handleTouchStart"
  >
    <component
      :is="as"
      ref="textRef"
      class="app-text-clamp"
      :class="[`line-clamp-${lines}`, { 'is-mono': mono, 'is-truncated': isTruncated }]"
      :tabindex="isTruncated ? 0 : undefined"
      :role="isTruncated ? 'note' : undefined"
      :aria-label="isTruncated ? text : undefined"
      @pointerenter="checkTruncation"
      @focusin="checkTruncation"
      @touchstart.passive="handleTouchStart"
    >
      <slot>{{ text }}</slot>
    </component>
    <template v-if="$slots.tooltip" #content>
      <slot name="tooltip" />
    </template>
  </Tooltip>
</template>

<style scoped>
.app-text-clamp-wrapper {
  display: inline-flex;
  max-width: 100%;
  vertical-align: middle;
}

.app-text-clamp-wrapper.is-block {
  display: flex;
  width: 100%;
  min-width: 0;
}

.app-text-clamp {
  display: -webkit-box;
  -webkit-box-orient: vertical;
  overflow: hidden;
  word-break: break-word;
  overflow-wrap: anywhere;
  max-width: 100%;
  min-width: 0;
  font-size: inherit;
}

.app-text-clamp-wrapper.is-block .app-text-clamp {
  width: 100%;
}

.app-text-clamp.line-clamp-1 {
  -webkit-line-clamp: 1;
  text-overflow: ellipsis;
}

.app-text-clamp.line-clamp-2 {
  -webkit-line-clamp: 2;
}

.app-text-clamp.line-clamp-3 {
  -webkit-line-clamp: 3;
}

.app-text-clamp.is-mono {
  font-family: var(--font-mono);
}

.app-text-clamp.is-truncated {
  cursor: help;
}

.app-text-clamp:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
  border-radius: var(--radius-1);
}
</style>
