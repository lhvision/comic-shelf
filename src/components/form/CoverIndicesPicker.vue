<script setup lang="ts">
/**
 * @file CoverIndicesPicker.vue
 * @description 本地收录与元数据编辑用的 4 槽封面页码选择器。直接以 `modelValue` 为唯一数据源。
 *
 * Props：
 * - `maxPage`：已知画页总数时封顶；`null` 或省略表示页数未知，只校验 ≥ 1。
 * - `hint`：自定义说明；为空时按是否封顶显示默认文案。
 *
 * Model：
 * - `modelValue`：长度为 4 的 1-based 页码数组。
 */
import { computed } from 'vue'

const COVER_SLOT_LABELS = ['第 1 张 (主封)', '第 2 张', '第 3 张', '第 4 张'] as const

const modelValue = defineModel<number[]>({ default: () => [1, 2, 3, 4] })

const props = withDefaults(
  defineProps<{
    /** 画页上限；`null` 表示不封顶 */
    maxPage?: number | null
    /** 覆盖默认说明文案 */
    hint?: string
  }>(),
  {
    maxPage: null,
    hint: '',
  },
)

/** 已知页数时的上限；未知页数时为 `null`。 */
const maxPageCap = computed<number | null>(() =>
  props.maxPage == null ? null : Math.max(1, props.maxPage),
)
const inputMax = computed(() => maxPageCap.value ?? undefined)
const coverHint = computed(() => {
  if (props.hint) return props.hint
  const cap = maxPageCap.value
  if (cap == null) {
    return '服务器目录导入时页数未知，请按实际画页填写页码（最小为 1）；超出实际页数的封面在收录后不会生效。'
  }
  return `指定 1 ~ ${cap} P 的页码序号（超出或小于 1 会自动恢复有效序号），书架与详情页轮播将按此顺序展示这 4 页作为封面。`
})

function slotFallback(slot: number): number {
  const cap = maxPageCap.value
  return cap == null ? slot : Math.min(slot, cap)
}

function normalizeCover(index: number) {
  const list = modelValue.value ?? []
  const cap = maxPageCap.value
  const fallback = slotFallback(index + 1)
  const val = Number(list[index])
  let next: number
  if (Number.isNaN(val) || val < 1 || !Number.isFinite(val)) {
    next = index === 0 ? 1 : fallback
  } else if (cap != null && val > cap) {
    next = fallback
  } else {
    next = Math.floor(val)
  }
  const slots = [
    list[0] ?? 1,
    list[1] ?? slotFallback(2),
    list[2] ?? slotFallback(3),
    list[3] ?? slotFallback(4),
  ]
  slots[index] = next
  modelValue.value = slots
}
</script>

<template>
  <div class="cover-indices-picker">
    <div class="covers-grid">
      <div v-for="(label, index) in COVER_SLOT_LABELS" :key="label" class="cover-slot">
        <span class="cover-slot__label">{{ label }}</span>
        <input
          v-model.number="modelValue[index]"
          class="field-input cover-input"
          type="number"
          min="1"
          :max="inputMax"
          @blur="normalizeCover(index)"
          @change="normalizeCover(index)"
        />
      </div>
    </div>
    <span class="covers-hint">{{ coverHint }}</span>
  </div>
</template>

<style scoped>
.cover-indices-picker {
  display: grid;
  gap: var(--space-1-5);
}

.covers-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: var(--space-2);
}

.cover-slot {
  display: grid;
  gap: var(--space-1);
}

.cover-slot__label {
  font-size: 0.72rem;
  color: var(--ink-2);
  white-space: nowrap;
}

.cover-input {
  text-align: center;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  color: var(--ink-0);
  transition: border-color var(--duration-1) var(--ease-out);
}

.cover-input:focus {
  outline: none;
  border-color: var(--accent);
}

.covers-hint {
  font-size: 0.72rem;
  color: var(--ink-2);
  line-height: 1.4;
}

@media (max-width: 640px) {
  .covers-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
