<script setup lang="ts">
/**
 * @file ChapterGroupsModal.vue
 * @description 单本漫画章节分组管理对话框（Chapter Groups Management Modal）。
 *
 * 核心机制：
 * 1. 默认展示并锁定主连载正文分组（default），避免单行本等衍生分组产生重复画页；
 * 2. 呈现作品提供的全部可用分组（available_groups），支持勾选收录或取消收录；
 * 3. 勾选新分组将增量拉取对应章节信息并追加至全书末尾；
 * 4. 取消已有分组需二次确认知悉，确认后安全裁剪章节并物理清理磁盘已缓存画页以释放空间。
 */

import { computed, ref, watch } from 'vue'
import Modal from '@/components/Modal.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { ComicGroupSummary } from '@/types'

const props = defineProps<{
  open: boolean
  source: string
  sourceId: string
  availableGroups: ComicGroupSummary[]
  selectedGroups: string[]
}>()

const emit = defineEmits<{
  cancel: []
  updated: []
}>()

const { toast } = useToast()

const selected = ref<string[]>([])
const initialSelected = ref<string[]>([])
const saving = ref(false)
const ackRemove = ref(false)

watch(
  () => props.open,
  (isOpen) => {
    if (isOpen) {
      const active = props.selectedGroups?.length ? props.selectedGroups : ['default']
      selected.value = [...active]
      initialSelected.value = [...active]
      ackRemove.value = false
    }
  },
  { immediate: true },
)

/** 被用户取消勾选的已有分组 */
const removedGroups = computed(() => {
  return initialSelected.value.filter((k) => !selected.value.includes(k))
})

/** 是否存在需要裁剪并清理本地磁盘的分组 */
const hasRemoved = computed(() => removedGroups.value.length > 0)

/** 是否有变更 */
const hasChanges = computed(() => {
  if (selected.value.length !== initialSelected.value.length) return true
  return selected.value.some((k) => !initialSelected.value.includes(k))
})

/** 获取分组显示名称 */
function getGroupName(key: string): string {
  const g = props.availableGroups.find((item) => item.key === key)
  return g?.name || key
}

function toggleGroup(key: string) {
  if (key === 'default') {
    // 默认主连载组不可取消
    return
  }
  if (selected.value.includes(key)) {
    if (selected.value.length === 1) {
      toast('至少需要保留一个章节分组', 'info')
      return
    }
    selected.value = selected.value.filter((k) => k !== key)
  } else {
    selected.value.push(key)
  }
}

async function handleSave() {
  if (saving.value) return
  if (hasRemoved.value && !ackRemove.value) {
    toast('请先确认已知晓移除章节画页操作', 'info')
    return
  }

  saving.value = true
  try {
    // 确保 default 分组始终在所选列表中（若可用分组包含 default）
    const finalSelected = [...selected.value]
    if (
      props.availableGroups.some((g) => g.key === 'default') &&
      !finalSelected.includes('default')
    ) {
      finalSelected.unshift('default')
    }

    await api.updateComicGroups(props.source, props.sourceId, finalSelected)
    toast('章节分组已更新')
    emit('updated')
  } catch (err) {
    toast(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <Modal :open="open" title="章节分组管理" size="md" @cancel="emit('cancel')">
    <div class="groups-manager">
      <div class="groups-hint">
        <AppIcon name="info" class="hint-icon" />
        <div class="hint-text">
          默认仅收录正文连载，避免收录 100% 重复的单行本。如需收录衍生分组，可在此勾选追加。
        </div>
      </div>

      <div class="groups-list" role="list">
        <div
          v-for="g in availableGroups"
          :key="g.key"
          class="group-item"
          :class="{
            'is-default': g.key === 'default',
            'is-checked': selected.includes(g.key),
          }"
          @click="toggleGroup(g.key)"
        >
          <label class="group-checkbox-wrap" @click.stop>
            <input
              type="checkbox"
              class="group-checkbox"
              :checked="selected.includes(g.key)"
              :disabled="g.key === 'default' || (selected.length === 1 && selected.includes(g.key))"
              @change="toggleGroup(g.key)"
            />
          </label>

          <div class="group-info">
            <div class="group-title-row">
              <span class="group-name">{{ g.name }}</span>
              <span v-if="g.key === 'default'" class="group-badge main-badge">
                <AppIcon name="lock" class="badge-icon" />
                正文连载（主分组）
              </span>
            </div>
            <div class="group-meta">共 {{ g.count }} 话 / 卷</div>
          </div>
        </div>
      </div>

      <!-- 移除分组时的危险确认提示区 -->
      <Transition name="fade">
        <div v-if="hasRemoved" class="danger-warning-box">
          <div class="warning-header">
            <AppIcon name="trash" class="warning-icon" />
            <span class="warning-title">即将移除章节与清理磁盘</span>
          </div>
          <div class="warning-desc">
            取消勾选「{{
              removedGroups.map(getGroupName).join('、')
            }}」后，相关章节将从全书中剔除，且该分组已下载的本地画页与缩略图将被<strong>物理永久删除</strong>以释放空间。
          </div>
          <label class="ack-checkbox-row">
            <input v-model="ackRemove" type="checkbox" class="ack-checkbox" />
            <span class="ack-text">我已知晓并确认移除这些章节画页（不可撤销）</span>
          </label>
        </div>
      </Transition>
    </div>

    <template #footer>
      <div class="modal-actions">
        <AppButton variant="secondary" :disabled="saving" @click="emit('cancel')"> 取消 </AppButton>
        <AppButton
          variant="primary"
          :loading="saving"
          :disabled="saving || !hasChanges || (hasRemoved && !ackRemove)"
          @click="handleSave"
        >
          保存更改
        </AppButton>
      </div>
    </template>
  </Modal>
</template>

<style scoped>
.groups-manager {
  display: flex;
  flex-direction: column;
  gap: var(--space-4, 1rem);
}

.groups-hint {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2, 0.5rem);
  padding: var(--space-3, 0.75rem);
  border-radius: var(--radius-md, 0.5rem);
  background: var(--color-bg-subtle, rgba(0, 0, 0, 0.03));
  border: 1px solid var(--color-border-subtle, rgba(0, 0, 0, 0.08));
  font-size: var(--font-size-xs, 0.75rem);
  color: var(--color-text-muted, #666);
  line-height: 1.5;
}

.hint-icon {
  font-size: 1rem;
  color: var(--color-text-muted, #666);
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.groups-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2, 0.5rem);
}

.group-item {
  display: flex;
  align-items: center;
  gap: var(--space-3, 0.75rem);
  padding: var(--space-3, 0.75rem) var(--space-4, 1rem);
  border-radius: var(--radius-md, 0.5rem);
  border: 1px solid var(--color-border-subtle, rgba(0, 0, 0, 0.1));
  background: var(--color-bg-card, #fff);
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
}

.group-item:hover {
  border-color: var(--color-border-main, rgba(0, 0, 0, 0.2));
  background: var(--color-bg-hover, rgba(0, 0, 0, 0.02));
}

.group-item.is-default {
  cursor: default;
  background: var(--color-bg-subtle, rgba(0, 0, 0, 0.02));
}

.group-checkbox-wrap {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.group-checkbox {
  width: 1.125rem;
  height: 1.125rem;
  accent-color: var(--color-primary, #1e293b);
  cursor: pointer;
}

.group-checkbox:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.group-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
  flex: 1;
}

.group-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
}

.group-name {
  font-size: var(--font-size-sm, 0.875rem);
  font-weight: 600;
  color: var(--color-text-main, #1e293b);
}

.group-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  font-size: var(--font-size-xs, 0.75rem);
  padding: 0.125rem 0.375rem;
  border-radius: var(--radius-xs, 0.25rem);
}

.main-badge {
  background: var(--color-bg-subtle, rgba(0, 0, 0, 0.06));
  color: var(--color-text-muted, #64748b);
  font-size: 0.7rem;
}

.badge-icon {
  font-size: 0.75rem;
}

.group-meta {
  font-size: var(--font-size-xs, 0.75rem);
  color: var(--color-text-muted, #64748b);
}

/* 危险提示区 */
.danger-warning-box {
  display: flex;
  flex-direction: column;
  gap: var(--space-2, 0.5rem);
  padding: var(--space-3, 0.75rem);
  border-radius: var(--radius-md, 0.5rem);
  background: rgba(239, 68, 68, 0.08);
  border: 1px solid rgba(239, 68, 68, 0.25);
  margin-top: var(--space-1, 0.25rem);
}

.warning-header {
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
  color: var(--color-danger, #ef4444);
  font-weight: 600;
  font-size: var(--font-size-sm, 0.875rem);
}

.warning-icon {
  font-size: 1rem;
}

.warning-desc {
  font-size: var(--font-size-xs, 0.75rem);
  color: var(--color-text-main, #333);
  line-height: 1.5;
}

.ack-checkbox-row {
  display: flex;
  align-items: center;
  gap: var(--space-2, 0.5rem);
  cursor: pointer;
  margin-top: 0.25rem;
}

.ack-checkbox {
  width: 1rem;
  height: 1rem;
  accent-color: var(--color-danger, #ef4444);
  cursor: pointer;
}

.ack-text {
  font-size: var(--font-size-xs, 0.75rem);
  font-weight: 500;
  color: var(--color-danger, #ef4444);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2, 0.5rem);
}

.fade-enter-active,
.fade-leave-active {
  transition:
    opacity 0.2s ease,
    transform 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
  transform: translateY(-4px);
}
</style>
