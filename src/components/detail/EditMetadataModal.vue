<script setup lang="ts">
import { ref, watch } from 'vue'
import Modal from '@/components/Modal.vue'
import TagManager from '@/components/form/TagManager.vue'
import CoverIndicesPicker from '@/components/form/CoverIndicesPicker.vue'
import { useLibraryStore } from '@/stores/library'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { ComicMeta } from '@/types'

const props = defineProps<{
  open: boolean
  meta: ComicMeta
}>()

const emit = defineEmits<{
  cancel: []
  saved: [meta: ComicMeta]
}>()

const store = useLibraryStore()
const { toast } = useToast()

const title = ref('')
const works = ref('')
const authors = ref('')
const actors = ref('')
const uploader = ref('')
const description = ref('')
const tags = ref<string[]>([])
const coverIndices = ref<number[]>([1, 2, 3, 4])
const saving = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen && props.meta) {
      title.value = props.meta.title || ''
      works.value = (props.meta.works || []).join(' / ')
      authors.value = (props.meta.authors || []).join(' / ')
      actors.value = (props.meta.actors || []).join(' / ')
      uploader.value = props.meta.uploader || ''
      description.value = props.meta.description || ''
      tags.value = [...(props.meta.tags || [])]

      const pCount = Math.max(1, props.meta.page_count || 1)
      const existing = props.meta.cover_indices || []
      coverIndices.value = [
        existing[0] ?? 1,
        existing[1] ?? Math.min(2, pCount),
        existing[2] ?? Math.min(3, pCount),
        existing[3] ?? Math.min(4, pCount),
      ]
    }
  },
  { immediate: true },
)

function parseList(str: string): string[] {
  return str
    .split(/[/,，、]/)
    .map((s) => s.trim())
    .filter(Boolean)
}

async function save() {
  if (!title.value.trim()) {
    toast('作品标题不能为空', 'error')
    return
  }

  saving.value = true
  try {
    const updated = await api.updateMetadata(props.meta.source, props.meta.source_id, {
      title: title.value.trim(),
      works: parseList(works.value),
      authors: parseList(authors.value),
      actors: parseList(actors.value),
      uploader: uploader.value.trim() || undefined,
      description: description.value.trim(),
      tags: tags.value,
      cover_indices: coverIndices.value,
    })
    await store.load()
    toast('资料与封面页码已更新', 'info')
    emit('saved', updated.meta)
  } catch (err) {
    toast(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Modal :open="open" title="编辑典藏资料与标签" @cancel="emit('cancel')">
    <form class="edit-meta-form" @submit.prevent="save">
      <div class="field-group">
        <label class="form-label" for="edit-title">作品标题 *</label>
        <input
          id="edit-title"
          v-model="title"
          class="field-input field-input--lg"
          type="text"
          required
          placeholder="作品标题"
        />
      </div>

      <div class="grid-2">
        <div class="field-group">
          <label class="form-label" for="edit-works">原作 / 企划</label>
          <input
            id="edit-works"
            v-model="works"
            class="field-input"
            type="text"
            placeholder="如：东方Project（多个用 / 分隔）"
          />
        </div>

        <div class="field-group">
          <label class="form-label" for="edit-authors">创作者 / 绘师 / 社团</label>
          <input
            id="edit-authors"
            v-model="authors"
            class="field-input"
            type="text"
            placeholder="如：自制 / 社团名"
          />
        </div>
      </div>

      <div class="grid-2">
        <div class="field-group">
          <label class="form-label" for="edit-actors">登场人物</label>
          <input
            id="edit-actors"
            v-model="actors"
            class="field-input"
            type="text"
            placeholder="如：博丽灵梦 / 雾雨魔理沙"
          />
        </div>

        <div class="field-group">
          <label class="form-label" for="edit-uploader">上传 / 整理者</label>
          <input
            id="edit-uploader"
            v-model="uploader"
            class="field-input"
            type="text"
            placeholder="如：馆长 / 佚名"
          />
        </div>
      </div>

      <div class="field-group">
        <label class="form-label">封面展示页码 (Cover Pages · 轮播 4 张)</label>
        <CoverIndicesPicker v-model="coverIndices" :max-page="meta?.page_count || 1" />
      </div>

      <div class="field-group">
        <label class="form-label">分类标签 (Tags)</label>
        <TagManager v-model="tags" />
      </div>

      <div class="field-group">
        <label class="form-label" for="edit-desc">叙述 / 备注</label>
        <textarea
          id="edit-desc"
          v-model="description"
          class="field-textarea"
          rows="3"
          placeholder="可填写该图集或拆帧系列的简介、说明或来源备注…"
        />
      </div>
    </form>

    <template #footer>
      <button class="btn btn-ghost" type="button" :disabled="saving" @click="emit('cancel')">
        取消
      </button>
      <button
        class="btn btn-primary"
        type="button"
        :disabled="saving || !title.trim()"
        @click="save"
      >
        {{ saving ? '保存中…' : '保存修改' }}
      </button>
    </template>
  </Modal>
</template>

<style scoped>
.edit-meta-form {
  display: grid;
  gap: var(--space-4);
}

.field-group {
  display: grid;
  gap: var(--space-1-5);
}

.form-label {
  font-family: var(--font-body);
  font-size: var(--text-xs);
  font-weight: 600;
  letter-spacing: 0.04em;
  color: var(--ink-1);
}

.field-input,
.field-textarea {
  width: 100%;
  padding: var(--space-2) var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  color: var(--ink-0);
  font-size: var(--text-sm);
  font-family: inherit;
  transition: border-color var(--duration-1) var(--ease-out);
}

.field-input:focus,
.field-textarea:focus {
  outline: none;
  border-color: var(--accent);
}

.field-input--lg {
  font-size: var(--text-md);
  font-family: var(--font-display);
}

.grid-2 {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: var(--space-3);
}

@media (max-width: 640px) {
  .grid-2 {
    grid-template-columns: 1fr;
  }
}
</style>
