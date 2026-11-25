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
  <Modal
    :open="open"
    title="章节分组管理"
    size="md"
    :prevent-close="saving"
    @cancel="!saving && emit('cancel')"
  >
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
        <AppButton variant="secondary" :disabled="saving" @click="!saving && emit('cancel')">
          取消
        </AppButton>
        <AppButton
          variant="primary"
          :loading="saving"
          :disabled="saving || !hasChanges || (hasRemoved && !ackRemove)"
          @click="handleSave"
        >
          {{ saving ? '保存中…' : '保存更改' }}
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
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-2);
  background: var(--paper-1);
  border: 1px solid var(--line);
  font-size: var(--text-xs);
  color: var(--ink-2);
  line-height: var(--leading-normal);
}

.hint-icon {
  font-size: 1rem;
  color: var(--ink-2);
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.groups-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.group-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-2);
  border: 1px solid var(--line);
  background: var(--paper-0);
  cursor: pointer;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
  user-select: none;
}

.group-item:hover {
  border-color: var(--line-strong);
  background: color-mix(in oklab, var(--paper-1) 60%, var(--paper-0));
}

.group-item.is-default {
  cursor: default;
  background: var(--paper-1);
}

.group-checkbox-wrap {
  display: flex;
  align-items: center;
  cursor: pointer;
}

.group-checkbox {
  width: 1.125rem;
  height: 1.125rem;
  accent-color: var(--accent);
  cursor: pointer;
}

.group-checkbox:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

.group-info {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  flex: 1;
}

.group-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.group-name {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-0);
}

.group-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  padding: var(--space-0-5) var(--space-1-5);
  border-radius: var(--radius-1);
}

.main-badge {
  background: var(--paper-1);
  color: var(--ink-2);
  font-size: var(--text-caption);
}

.badge-icon {
  font-size: var(--text-xs);
}

.group-meta {
  font-size: var(--text-xs);
  color: var(--ink-2);
}

/* 危险提示区 */
.danger-warning-box {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-3);
  border-radius: var(--radius-2);
  background: var(--danger-soft);
  border: 1px solid color-mix(in oklab, var(--danger) 30%, transparent);
  margin-top: var(--space-1);
}

.warning-header {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--danger);
  font-weight: 600;
  font-size: var(--text-sm);
}

.warning-icon {
  font-size: 1rem;
}

.warning-desc {
  font-size: var(--text-xs);
  color: var(--ink-1);
  line-height: var(--leading-normal);
}

.ack-checkbox-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  margin-top: var(--space-1);
}

.ack-checkbox {
  width: 1rem;
  height: 1rem;
  accent-color: var(--danger);
  cursor: pointer;
}

.ack-text {
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--danger);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
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
