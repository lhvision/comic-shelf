<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useLibraryStore } from '@/stores/library'
import AppButton from '@/components/AppButton.vue'
import AppChip from '@/components/AppChip.vue'
import AppIcon from '@/components/AppIcon.vue'

const currentTags = defineModel<string[]>({ default: () => [] })

const props = withDefaults(
  defineProps<{
    maxSuggestions?: number
  }>(),
  {
    maxSuggestions: 15,
  },
)

const store = useLibraryStore()
const newTagInput = ref('')

onMounted(() => {
  if (!store.facets) {
    void store.loadFacets()
  }
})

const popularTags = computed(() => {
  // 优先直接使用后端聚合好的全馆最热门标签池（突破分页限制，覆盖全馆万本真实数据）
  if (store.facets?.top_tags && store.facets.top_tags.length > 0) {
    return store.facets.top_tags
      .map(([t]) => t)
      .filter((t) => !currentTags.value.includes(t))
      .slice(0, props.maxSuggestions)
  }
  // 降级兜底：从当前 store.items 提取
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
      <AppChip
        v-for="(tag, idx) in currentTags"
        :key="tag"
        removable
        :remove-aria-label="`删除标签 ${tag}`"
        @remove="removeTag(idx)"
      >
        {{ tag }}
      </AppChip>
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
      <span class="popular-title">
        <AppIcon name="search" size="xs" />
        <span>热门快选：</span>
      </span>
      <div class="popular-chips">
        <AppChip v-for="popTag in popularTags" :key="popTag" @click="addTag(popTag)">
          + {{ popTag }}
        </AppChip>
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
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
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

.muted-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
}
</style>
