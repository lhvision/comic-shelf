<script setup lang="ts">
/**
 * 阅读器底部 HUD —— 自动切换倒计时 + 上一屏/页码/下一屏指示器。
 * 纯展示组件：倒计时刻度和页码都由 ReaderView 计算后通过 props 传入，
 * 交互统一以 emit 上抛（切换暂停 / 翻页）。
 */
import AppIcon from '@/components/AppIcon.vue'

const props = defineProps<{
  /** 自动切换是否已启用（启用时 HUD 常驻不隐藏） */
  autoTurn: boolean
  /** 是否已在最后一屏 */
  atLastGroup: boolean
  /** 自动切换是否被用户暂停 */
  autoTurnPaused: boolean
  /** 设置面板是否打开（打开时倒计时应显示"设置中已暂停"） */
  settingsOpen: boolean
  /** 距离自动切换的剩余秒数 */
  autoTurnRemaining: number
  /** 当前屏页码文案，如 "1–2" */
  currentGroupLabel: string
  /** 总页数 */
  total: number
  prevSymbol: string
  nextSymbol: string
  /** 上一屏/下一屏是否被禁用（边界情况） */
  canPrev: boolean
  canNext: boolean
  /** 是否隐藏（用户清空工具栏且未开启自动切换） */
  hidden: boolean
}>()

const emit = defineEmits<{
  toggleAutoTurnPause: []
  prev: []
  next: []
}>()

const autoTurnCountdownAriaLabel = () => {
  if (props.settingsOpen) return '自动切换倒计时，设置中已暂停'
  if (props.atLastGroup) return '已到最后一屏'
  if (props.autoTurnPaused) return '自动切换已暂停，点击继续'
  if (props.autoTurnRemaining <= 1) return '即将切换，点击暂停'
  return `${props.autoTurnRemaining} 秒后切换，点击暂停`
}

const autoTurnActionLabel = () => (props.autoTurnPaused || props.settingsOpen ? '继续' : '暂停')
</script>

<template>
  <div class="reader-hud" :data-hidden="hidden" :inert="hidden">
    <button
      v-if="autoTurn && !atLastGroup"
      class="auto-turn-countdown"
      type="button"
      :data-paused="autoTurnPaused || settingsOpen"
      :aria-label="autoTurnCountdownAriaLabel()"
      @click="emit('toggleAutoTurnPause')"
    >
      <span class="auto-turn-display">
        <span v-if="!autoTurnPaused && !settingsOpen" class="auto-turn-count" aria-hidden="true">
          {{ autoTurnRemaining }}
        </span>
        <span v-else class="auto-turn-icon" aria-hidden="true">
          <AppIcon name="pause" size="xs" />
        </span>
      </span>
      <span class="auto-turn-action" aria-hidden="true">{{ autoTurnActionLabel() }}</span>
    </button>

    <div class="reader-page-indicator">
      <button type="button" aria-label="上一屏" @click="emit('prev')" :disabled="!canPrev">
        {{ prevSymbol }}
      </button>
      <span>{{ currentGroupLabel }} / {{ total }}</span>
      <button type="button" aria-label="下一屏" @click="emit('next')" :disabled="!canNext">
        {{ nextSymbol }}
      </button>
    </div>
  </div>
</template>

<style scoped>
.reader-hud {
  position: absolute;
  right: max(var(--space-4), env(safe-area-inset-right));
  bottom: max(var(--space-5), env(safe-area-inset-bottom));
  z-index: 6;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--space-2);
  transition:
    opacity var(--duration-2) var(--ease-out),
    translate var(--duration-2) var(--ease-out),
    visibility 0s;
}

.reader-hud[data-hidden='true'] {
  opacity: 0;
  translate: 0 var(--space-2);
  pointer-events: none;
  visibility: hidden;
  transition:
    opacity var(--duration-2) var(--ease-out),
    translate var(--duration-2) var(--ease-out),
    visibility 0s var(--duration-2);
}

.reader-page-indicator {
  display: grid;
  justify-items: center;
  gap: var(--space-1);
  padding: var(--space-2);
  border: 1px solid var(--reader-line-strong);
  border-radius: 999px;
  background: var(--reader-scrim);
  backdrop-filter: blur(10px);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
}

.reader-page-indicator button {
  width: var(--control-md);
  height: var(--control-md);
  display: grid;
  place-items: center;
  border-radius: 50%;
  background: var(--reader-surface-strong);
  color: var(--reader-ink);
  font-size: var(--text-sm);
}

.reader-page-indicator button:disabled {
  opacity: 0.35;
  cursor: default;
}

/* 倒计时只显示数字；hover/focus 时同位置切换成"暂停/继续" */
.auto-turn-countdown {
  width: 100%;
  min-height: var(--control-sm);
  display: grid;
  place-items: center;
  padding: 0 var(--space-2);
  border: 1px solid var(--reader-line-strong);
  border-radius: 999px;
  background: var(--reader-scrim);
  backdrop-filter: blur(10px);
  color: var(--reader-ink);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.06em;
  cursor: pointer;
  transition:
    background-color var(--duration-1) var(--ease-out),
    border-color var(--duration-1) var(--ease-out);
}

.auto-turn-display,
.auto-turn-action {
  grid-area: 1 / 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.auto-turn-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  color: var(--accent);
}

.auto-turn-action {
  opacity: 0;
}

.auto-turn-countdown:focus-visible .auto-turn-display {
  opacity: 0;
}

.auto-turn-countdown:focus-visible .auto-turn-action {
  opacity: 1;
}

.auto-turn-countdown[data-paused='true'] {
  border-color: var(--accent);
  background: var(--reader-backdrop);
}

@media (hover: hover) {
  .auto-turn-countdown:hover {
    border-color: var(--accent);
    background: var(--reader-backdrop);
  }

  .auto-turn-countdown:hover .auto-turn-display {
    opacity: 0;
  }

  .auto-turn-countdown:hover .auto-turn-action {
    opacity: 1;
  }
}

@media (max-width: 680px), (max-height: 560px) {
  .reader-hud {
    flex-direction: row;
    align-items: center;
  }

  .reader-page-indicator {
    grid-auto-flow: column;
    grid-template-columns: auto auto auto;
    align-items: center;
    gap: var(--space-2);
    padding: var(--space-1) var(--space-2);
  }

  .reader-page-indicator button {
    width: var(--control-md);
    height: var(--control-md);
  }

  /* 移动端：倒计时做成页码左边的小圆，不再与页码器等宽；
     触控区保持 --control-md（44px）以满足移动端命中标准 */
  .auto-turn-countdown {
    width: var(--control-md);
    height: var(--control-md);
    min-height: 0;
    padding: 0;
    border-radius: 50%;
  }
}

@media (max-height: 560px) {
  .reader-hud {
    gap: var(--space-1);
  }
}
</style>
