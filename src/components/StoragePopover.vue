<script setup lang="ts">
/**
 * @file StoragePopover.vue
 * @description 阅览室设备与离线存储管理交互浮层编排组件。
 *
 * 核心架构：
 * - 触发徽标（`storage-badge-btn`）：常驻展示离线体积、归档图标与 PWA 红点；
 * - 浮层内部聚合：`StorageHeader`（安装入口）、`StoragePwaCard`（更新卡片）、`StorageGaugeSection`（容量刻度）、`StorageActionsSection`（清理动作）；
 * - 状态机完全由 `useOfflineStorage`、`usePwaInstall` 与 `usePwaUpdate` 驱动。
 */

import { onMounted, ref, useTemplateRef } from 'vue'
import AppPopover from '@/components/AppPopover.vue'
import AppIcon from '@/components/AppIcon.vue'
import StorageHeader from './storage/StorageHeader.vue'
import StoragePwaCard from './storage/StoragePwaCard.vue'
import StorageGaugeSection from './storage/StorageGaugeSection.vue'
import StorageActionsSection from './storage/StorageActionsSection.vue'
import { formatBytes, useOfflineStorage } from '@/composables/useOfflineStorage'
import { usePwaInstall } from '@/composables/usePwaInstall'
import { usePwaUpdate } from '@/composables/usePwaUpdate'
import { useToast } from '@/composables/useToast'

const {
  quota,
  percentage,
  budgetPercentage,
  mangaImageCount,
  mangaImageBytes,
  usageFormatted,
  quotaFormatted,
  mangaImageBytesFormatted,
  coreAssetBytesFormatted,
  badgeText,
  environmentStatus,
  clearing,
  refreshEstimate,
  clearImageCache,
  resetAllStorage,
} = useOfflineStorage()

const { canInstall, isStandalone, installApp } = usePwaInstall()
const { needRefresh, isUpdating, applyUpdate } = usePwaUpdate()
const { toast } = useToast()

/** 浮层展开状态 */
const isOpen = ref(false)
/** 操作区组件 Ref */
const actionsRef = useTemplateRef<InstanceType<typeof StorageActionsSection>>('actionsRef')

onMounted(() => {
  refreshEstimate()
})

/** 浮层展开时重新估算存储配额并重置确认状态 */
function onOpen() {
  refreshEstimate()
  actionsRef.value?.resetConfirmation()
}

async function handleInstall() {
  const success = await installApp()
  if (success) {
    toast('已启动纸间桌面安装', 'success')
  }
}

async function handleClearImages() {
  if (clearing.value) return
  const { freedBytes } = await clearImageCache()
  const displayFreed = freedBytes > 0 ? formatBytes(freedBytes) : mangaImageBytesFormatted.value
  toast(`已释放 ${displayFreed} 设备存储`, 'success')
}

async function handleResetAll() {
  if (clearing.value) return
  const freedBytes = await resetAllStorage()
  toast(`已彻底重置离线环境（释放 ${formatBytes(freedBytes)}）`, 'info')
  isOpen.value = false
}
</script>

<template>
  <AppPopover
    v-model:open="isOpen"
    side="bottom"
    align="end"
    arrow
    width="21.5rem"
    role="dialog"
    aria-label="阅览室设备与离线存储管理"
    @open="onOpen"
  >
    <template #default="{ open, targetId }">
      <button
        type="button"
        class="storage-badge-btn"
        :class="{ 'has-update': needRefresh }"
        :title="
          needRefresh
            ? `发现新版本卷本可装订（离线占用 ${usageFormatted}）`
            : `设备离线存储占用 ${usageFormatted}（点击查看与管理）`
        "
        :aria-label="`设备离线存储占用 ${usageFormatted}，点击展开管理面板`"
        :aria-expanded="open"
        :aria-controls="targetId"
        :commandfor="targetId"
        command="toggle-popover"
        aria-haspopup="dialog"
      >
        <AppIcon name="archive" size="xs" :stroke-width="1.8" />
        <span class="storage-label">{{ badgeText }}</span>
        <span v-if="needRefresh" class="update-indicator-dot" aria-hidden="true"></span>
      </button>
    </template>

    <template #content>
      <div class="storage-panel">
        <!-- 顶栏标题与 PWA 安装态 -->
        <StorageHeader
          :can-install="canInstall"
          :is-standalone="isStandalone"
          @install="handleInstall"
        />

        <!-- 新卷本装订就绪提示卡片 -->
        <StoragePwaCard
          :need-refresh="needRefresh"
          :is-updating="isUpdating"
          @update="applyUpdate"
        />

        <!-- 存储容量平直标尺与账单清单 -->
        <StorageGaugeSection
          :quota="quota"
          :quota-formatted="quotaFormatted"
          :percentage="percentage"
          :budget-percentage="budgetPercentage"
          :core-asset-bytes-formatted="coreAssetBytesFormatted"
          :manga-image-count="mangaImageCount"
          :manga-image-bytes-formatted="mangaImageBytesFormatted"
          :environment-status="environmentStatus"
        />

        <!-- 操作按钮区 -->
        <StorageActionsSection
          ref="actionsRef"
          :clearing="clearing"
          :manga-image-count="mangaImageCount"
          :manga-image-bytes="mangaImageBytes"
          :manga-image-bytes-formatted="mangaImageBytesFormatted"
          @clear-images="handleClearImages"
          @reset-all="handleResetAll"
        />
      </div>
    </template>
  </AppPopover>
</template>

<style scoped>
.storage-badge-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  padding: var(--space-1) var(--space-2);
  line-height: 1.5;
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-1);
  cursor: pointer;
  white-space: nowrap;
  flex-shrink: 0;
  transition: all var(--duration-1) var(--ease-out);
}

.storage-badge-btn:hover {
  background: var(--paper-2);
  border-color: var(--line-strong);
  color: var(--ink-0);
}

.storage-badge-btn.has-update {
  border-color: color-mix(in oklab, var(--accent) 60%, var(--line));
}

.update-indicator-dot {
  width: 0.45rem;
  height: 0.45rem;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 0 1.5px var(--paper-1);
}

.storage-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3-5);
  padding: var(--space-3-5);
  color: var(--ink-0);
}

@media (max-width: 640px) {
  .storage-label {
    display: none;
  }

  .storage-badge-btn {
    width: var(--control-sm);
    height: var(--control-sm);
    min-width: var(--control-sm);
    min-height: var(--control-sm);
    padding: 0;
    justify-content: center;
  }
}

@media (max-width: 640px) and (pointer: coarse) {
  .storage-badge-btn::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    min-width: 44px;
    min-height: 44px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .storage-badge-btn {
    transition: none !important;
  }
}
</style>
