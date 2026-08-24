<script setup lang="ts">
import { computed, ref, watch } from 'vue'

const props = withDefaults(
  defineProps<{
    modelValue?: number[]
    maxPage?: number
    hint?: string
  }>(),
  {
    modelValue: () => [1, 2, 3, 4],
    maxPage: 1,
    hint: '',
  },
)

const emit = defineEmits<{
  'update:modelValue': [indices: number[]]
}>()

const cover1 = ref(1)
const cover2 = ref(2)
const cover3 = ref(3)
const cover4 = ref(4)

const effectiveMax = computed(() => Math.max(1, props.maxPage || 1))

watch(
  () => props.modelValue,
  (val) => {
    const list = val || []
    const next1 = list[0] ?? 1
    const next2 = list[1] ?? Math.min(2, effectiveMax.value)
    const next3 = list[2] ?? Math.min(3, effectiveMax.value)
    const next4 = list[3] ?? Math.min(4, effectiveMax.value)

    if (
      cover1.value !== next1 ||
      cover2.value !== next2 ||
      cover3.value !== next3 ||
      cover4.value !== next4
    ) {
      cover1.value = next1
      cover2.value = next2
      cover3.value = next3
      cover4.value = next4
    }
  },
  { immediate: true, deep: true },
)

function emitChange() {
  emit('update:modelValue', [cover1.value, cover2.value, cover3.value, cover4.value])
}

watch([cover1, cover2, cover3, cover4], () => {
  emitChange()
})

function normalizeCover(slot: 1 | 2 | 3 | 4) {
  const maxP = effectiveMax.value
  const defaultSlotVal = Math.min(slot, maxP)
  const refMap = { 1: cover1, 2: cover2, 3: cover3, 4: cover4 }
  const r = refMap[slot]
  const val = Number(r.value)

  if (isNaN(val) || val < 1 || !Number.isFinite(val)) {
    r.value = slot === 1 ? 1 : defaultSlotVal
  } else if (val > maxP) {
    r.value = defaultSlotVal
  } else {
    r.value = Math.floor(val)
  }

  emitChange()
}
</script>

<template>
  <div class="cover-indices-picker">
    <div class="covers-grid">
      <div class="cover-slot">
        <span class="cover-slot__label">第 1 张 (主封)</span>
        <input
          v-model.number="cover1"
          class="field-input cover-input"
          type="number"
          min="1"
          :max="effectiveMax"
          @blur="normalizeCover(1)"
          @change="normalizeCover(1)"
        />
      </div>
      <div class="cover-slot">
        <span class="cover-slot__label">第 2 张</span>
        <input
          v-model.number="cover2"
          class="field-input cover-input"
          type="number"
          min="1"
          :max="effectiveMax"
          @blur="normalizeCover(2)"
          @change="normalizeCover(2)"
        />
      </div>
      <div class="cover-slot">
        <span class="cover-slot__label">第 3 张</span>
        <input
          v-model.number="cover3"
          class="field-input cover-input"
          type="number"
          min="1"
          :max="effectiveMax"
          @blur="normalizeCover(3)"
          @change="normalizeCover(3)"
        />
      </div>
      <div class="cover-slot">
        <span class="cover-slot__label">第 4 张</span>
        <input
          v-model.number="cover4"
          class="field-input cover-input"
          type="number"
          min="1"
          :max="effectiveMax"
          @blur="normalizeCover(4)"
          @change="normalizeCover(4)"
        />
      </div>
    </div>
    <span class="covers-hint">
      {{
        hint ||
        `指定 1 ~ ${effectiveMax} P 的页码序号（超出或小于 1 会自动恢复有效序号），书架与详情页轮播将按此顺序展示这 4 页作为封面。`
      }}
    </span>
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
