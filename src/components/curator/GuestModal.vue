<script setup lang="ts">
/**
 * @file GuestModal.vue
 * @description 纸间 · 访客簿核心弹窗编排组件。
 *
 * 核心架构：
 * - 采用 Tab 编排模式连接「现存名册」与「登记印发」两个子面板；
 * - 状态机与 API 调度由 `useGuestPasses()` 统一驱动；
 * - 负责模态弹窗显隐与焦点自动流转。
 */

import { computed, nextTick, ref, useTemplateRef, watch } from 'vue'
import Modal from '@/components/Modal.vue'
import SegmentedTabs from '@/components/SegmentedTabs.vue'
import Tooltip from '@/components/Tooltip.vue'
import AppIcon from '@/components/AppIcon.vue'
import GuestRosterTab from './guest/GuestRosterTab.vue'
import GuestIssueTab from './guest/GuestIssueTab.vue'
import { useGuestPasses } from '@/composables/useGuestPasses'
import type { TabItem } from '@/components/SegmentedTabs.vue'
import type { GuestPass } from '@/types'

const { passes, loading, fetchError, modalVisible, fetchPasses, closeModal } = useGuestPasses()

/** 选项卡类型键 */
type TabKey = 'roster' | 'issue'

/** 当前激活的选项卡 */
const activeTab = ref<TabKey>('roster')
/** 刚刚印发成功的通行证（用于印发表单与凭证卡视图切换） */
const justCreatedPass = ref<GuestPass | null>(null)
/** 印发表单组件 Ref */
const issueTabRef = useTemplateRef<InstanceType<typeof GuestIssueTab>>('issueTabRef')

const tabs = computed<TabItem<TabKey>[]>(() => [
  { key: 'roster', label: '现存名册', sub: String(passes.value.length) },
  { key: 'issue', label: '登记印发' },
])

function onPassCreated(pass: GuestPass) {
  justCreatedPass.value = pass
}

watch(modalVisible, (visible) => {
  if (visible) {
    justCreatedPass.value = null
    if (passes.value.length === 0) {
      activeTab.value = 'roster'
    }
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'issue' && !justCreatedPass.value) {
    await nextTick()
    issueTabRef.value?.focusInput()
  }
})
</script>

<template>
  <Modal :open="modalVisible" title="纸间 · 访客簿" @cancel="closeModal">
    <template #title>
      <div class="guest-modal-title">
        <span>纸间 · 访客簿</span>
        <Tooltip
          tip="派发专属访问通行证，阅读进度与收藏红心相互隔离。"
          side="right"
          align="center"
          width="16rem"
        >
          <button type="button" class="title-info-btn" aria-label="查看权限隔离说明">
            <AppIcon name="info" size="xs" />
          </button>
        </Tooltip>
      </div>
    </template>

    <div class="guest-modal-container">
      <!-- 分段标签页导航 -->
      <div class="tabs-nav-bar">
        <SegmentedTabs
          v-model="activeTab"
          :items="tabs"
          size="md"
          :full-width="true"
          aria-label="访客簿功能切换"
        />
      </div>

      <!-- 选项卡 1：现存名册 -->
      <GuestRosterTab
        v-if="activeTab === 'roster'"
        :passes="passes"
        :loading="loading"
        :fetch-error="fetchError"
        @refresh="fetchPasses"
        @issue-first="activeTab = 'issue'"
      />

      <!-- 选项卡 2：登记印发 -->
      <GuestIssueTab
        v-else-if="activeTab === 'issue'"
        ref="issueTabRef"
        :just-created-pass="justCreatedPass"
        @created="onPassCreated"
        @reset-issue="justCreatedPass = null"
        @view-roster="activeTab = 'roster'"
      />
    </div>
  </Modal>
</template>

<style scoped>
.guest-modal-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: 0;
}

/* 标题栏集成提示信息 */
.guest-modal-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.title-info-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.title-info-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}

/* 分段选项卡条（吸顶固定） */
.tabs-nav-bar {
  position: sticky;
  top: calc(-1 * var(--space-5));
  z-index: 10;
  background: var(--paper-0);
  margin-left: calc(-1 * var(--space-5));
  margin-right: calc(-1 * var(--space-5));
  margin-top: calc(-1 * var(--space-5));
  padding: var(--space-4) var(--space-5) var(--space-3) var(--space-5);
  margin-bottom: var(--space-1);
  border-bottom: 1px solid var(--line);
  box-shadow: var(--shadow-1);
}
</style>
