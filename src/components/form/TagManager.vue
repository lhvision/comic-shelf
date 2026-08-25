<script setup lang="ts">
import { computed, ref } from 'vue'
import { useLibraryStore } from '@/stores/library'
import AppButton from '@/components/AppButton.vue'

const props = withDefaults(
  defineProps<{
    modelValue?: string[]
    maxSuggestions?: number
  }>(),
  {
    modelValue: () => [],
    maxSuggestions: 15,
  },
)

const emit = defineEmits<{
  'update:modelValue': [tags: string[]]
}>()

const store = useLibraryStore()
const newTagInput = ref('')

const currentTags = computed({
  get: () => props.modelValue || [],
  set: (val: string[]) => emit('update:modelValue', val),
})

const popularTags = computed(() => {
  const counts: Record<string, number> = {}
  for (const item of store.items) {
    for (const t of item.tags || []) {
      counts[t] = (counts[t] || 0) + 1
    }
  }
  return Object.entries(counts)
    .sort((a, b) => b[1] - a[1])
    .map(([t]) => t)
    .filter((t) => !currentTags.value.includes(t))
    .slice(0, props.maxSuggestions)
})

function removeTag(index: number) {
  const next = [...currentTags.value]
  next.splice(index, 1)
  currentTags.value = next
}

function addTag(tagText: string) {
  const trimmed = tagText.trim().replace(/^#/, '')
  if (trimmed && !currentTags.value.includes(trimmed)) {
    currentTags.value = [...currentTags.value, trimmed]
  }
  newTagInput.value = ''
}

function onTagKeyDown(e: KeyboardEvent) {
  if (e.key === 'Enter' || e.key === ',' || e.key === '，' || e.key === ' ') {
    e.preventDefault()
    addTag(newTagInput.value)
  }
}
</script>

<template>
  <div class="tag-manager">
    <div class="tag-chips">
      <span v-for="(tag, idx) in currentTags" :key="tag" class="tag-chip">
        <span class="tag-chip__text">{{ tag }}</span>
        <button
          class="tag-chip__del"
          type="button"
          :aria-label="`删除标签 ${tag}`"
          @click="removeTag(idx)"
        >
          <svg
            viewBox="0 0 16 16"
            width="10"
            height="10"
            stroke="currentColor"
            stroke-width="2"
            fill="none"
          >
            <line x1="3" y1="3" x2="13" y2="13" />
            <line x1="13" y1="3" x2="3" y2="13" />
          </svg>
        </button>
      </span>
      <span v-if="currentTags.length === 0" class="muted-hint">暂无标签</span>
    </div>

    <div class="tag-input-row">
      <input
        v-model="newTagInput"
        class="field-input tag-input-box"
        type="text"
        placeholder="+ 输入新标签，按 Enter 或空格添加…"
        @keydown="onTagKeyDown"
      />
      <AppButton
        variant="ghost"
        size="sm"
        type="button"
        :disabled="!newTagInput.trim()"
        @click="addTag(newTagInput)"
      >
        添加
      </AppButton>
    </div>

    <div v-if="popularTags.length > 0" class="popular-tags-bar">
      <span class="popular-title">💡 热门快选：</span>
      <div class="popular-chips">
        <button
          v-for="popTag in popularTags"
          :key="popTag"
          class="pop-tag-chip"
          type="button"
          @click="addTag(popTag)"
        >
          + {{ popTag }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.tag-manager {
  display: grid;
  gap: var(--space-2-5);
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-1) 40%, transparent);
}

.tag-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-height: 2rem;
  align-items: center;
}

.tag-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  background: var(--paper-0);
  font-size: var(--text-xs);
  line-height: 1.2;
  color: var(--ink-0);
}

.tag-chip__text {
  display: inline-block;
}

.tag-chip__del {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1rem;
  height: 1rem;
  margin-left: 0.1rem;
  padding: 0;
  border: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  transition:
    color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.tag-chip__del:hover {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.tag-input-row {
  display: flex;
  gap: var(--space-2);
}

.tag-input-box {
  flex: 1;
}

.popular-tags-bar {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding-top: var(--space-2-5);
  margin-top: var(--space-1);
  border-top: 1px dashed var(--line);
}

.popular-title {
  font-size: var(--text-xs);
  color: var(--ink-2);
  font-weight: 500;
}

.popular-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  row-gap: var(--space-2);
}

.pop-tag-chip {
  display: inline-flex;
  align-items: center;
  padding: 0.2rem 0.55rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  background: var(--paper-0);
  font-size: var(--text-xs);
  line-height: 1.2;
  color: var(--ink-1);
  cursor: pointer;
  transition:
    background-color var(--duration-1) var(--ease-out),
    border-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.pop-tag-chip:hover {
  background: var(--accent-soft);
  border-color: var(--accent);
  color: var(--accent-strong);
}

.muted-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
}
</style>
