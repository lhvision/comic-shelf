<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import AppPopover from '@/components/AppPopover.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { formatBytes, useOfflineStorage } from '@/composables/useOfflineStorage'
import { usePwaInstall } from '@/composables/usePwaInstall'
import { usePwaUpdate } from '@/composables/usePwaUpdate'
import { useToast } from '@/composables/useToast'

const {
  quota,
  percentage,
  mangaImageCount,
  mangaImageBytes,
  usageFormatted,
  quotaFormatted,
  mangaImageBytesFormatted,
  coreAssetBytesFormatted,
  badgeText,
  clearing,
  refreshEstimate,
  clearImageCache,
  resetAllStorage,
} = useOfflineStorage()

const { canInstall, isStandalone, installApp } = usePwaInstall()
const { needRefresh, isUpdating, applyUpdate } = usePwaUpdate()
const { toast } = useToast()
const isOpen = ref(false)
const isConfirmingReset = ref(false)
let resetTimer: ReturnType<typeof setTimeout> | null = null

onMounted(() => {
  refreshEstimate()
})

onUnmounted(() => {
  if (resetTimer) clearTimeout(resetTimer)
})

function onOpen() {
  refreshEstimate()
  if (resetTimer) clearTimeout(resetTimer)
  isConfirmingReset.value = false
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
  if (!isConfirmingReset.value) {
    isConfirmingReset.value = true
    if (resetTimer) clearTimeout(resetTimer)
    resetTimer = setTimeout(() => {
      isConfirmingReset.value = false
    }, 5000)
    return
  }

  if (resetTimer) clearTimeout(resetTimer)
  isConfirmingReset.value = false
  const freedBytes = await resetAllStorage()
  toast(`已彻底重置离线环境（释放 ${formatBytes(freedBytes)}）`, 'info')
  isOpen.value = false
}

function cancelReset() {
  if (resetTimer) clearTimeout(resetTimer)
  isConfirmingReset.value = false
}
</script>

<template>
  <AppPopover
    v-model:open="isOpen"
    side="bottom"
    align="end"
    arrow
    width="21.5rem"
    aria-label="阅览室设备与离线存储管理"
    @open="onOpen"
  >
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
    >
      <AppIcon name="archive" size="xs" :stroke-width="1.8" />
      <span class="storage-label">{{ badgeText }}</span>
      <span v-if="needRefresh" class="update-indicator-dot" aria-hidden="true"></span>
    </button>

    <template #content>
      <div class="storage-panel">
        <!-- 顶栏标题与 PWA 安装态 -->
        <header class="storage-panel__header">
          <div class="header-titles">
            <h3 class="panel-title">阅览室设备与离线</h3>
            <span class="panel-subtitle font-mono">LOCAL STORAGE &amp; PWA</span>
          </div>

          <div class="header-action">
            <button
              v-if="canInstall"
              type="button"
              class="pwa-install-btn"
              title="将纸间添加至主屏幕或桌面独立运行"
              @click="handleInstall"
            >
              <AppIcon name="download" size="xs" :stroke-width="1.8" />
              <span>安装至桌面</span>
            </button>
            <span v-else-if="isStandalone" class="pwa-standalone-pill"> 〔 独立应用 〕 </span>
          </div>
        </header>

        <!-- 新卷本装订就绪提示卡片 -->
        <section v-if="needRefresh" class="storage-update-card" aria-label="应用更新">
          <div class="update-card-left">
            <span class="update-pill font-mono">UPD</span>
            <div class="update-card-text">
              <strong class="update-card-title">新卷本装订就绪</strong>
              <small class="update-card-sub">应用最新功能与静态补丁</small>
            </div>
          </div>
          <button type="button" class="update-card-btn" :disabled="isUpdating" @click="applyUpdate">
            <AppIcon
              name="refresh"
              size="xs"
              :stroke-width="1.8"
              :class="{ 'is-spinning': isUpdating }"
            />
            <span>{{ isUpdating ? '装订中…' : '立即装订' }}</span>
          </button>
        </section>

        <!-- 存储容量平直标尺（延续 3px 纸印规范） -->
        <section class="storage-gauge" aria-label="存储容量使用情况">
          <div class="gauge-meta">
            <span class="gauge-name">本机离线占用</span>
            <span class="gauge-value font-mono">
              <strong>{{ usageFormatted }}</strong>
              <small v-if="quota > 0"> / {{ quotaFormatted }}</small>
            </span>
          </div>

          <div
            class="storage-track"
            role="progressbar"
            :aria-valuenow="Math.round(percentage)"
            aria-valuemin="0"
            aria-valuemax="100"
            :aria-valuetext="`已占用 ${usageFormatted}`"
          >
            <div
              class="storage-fill"
              :style="{
                transform: `scaleX(${Math.max(percentage > 0 ? 0.015 : 0, Math.min(1, percentage / 100))})`,
              }"
            ></div>
          </div>
        </section>

        <!-- 分项账单细分清单 -->
        <ul class="storage-breakdown" role="list">
          <li class="breakdown-item">
            <div class="item-text">
              <span class="item-title">纸间核心资产</span>
              <small class="item-desc">App 外壳 · 脚本 · 字体（离线秒开）</small>
            </div>
            <span class="item-metric font-mono">{{ coreAssetBytesFormatted }}</span>
          </li>

          <li class="breakdown-item">
            <div class="item-text">
              <span class="item-title">漫画阅览缓存</span>
              <small class="item-desc">
                {{ mangaImageCount }} 张已读页面与封面 · 保留最新 1000 页面
              </small>
            </div>
            <span class="item-metric font-mono">{{ mangaImageBytesFormatted }}</span>
          </li>
        </ul>

        <!-- 安全边界提示 -->
        <div class="storage-boundary">
          <AppIcon name="info" size="xs" :stroke-width="1.8" />
          <p>仅释放本设备浏览器缓存，绝不影响服务器书库。</p>
        </div>

        <!-- 操作按钮区 -->
        <footer class="storage-panel__footer">
          <AppButton
            variant="secondary"
            size="sm"
            block
            :loading="clearing"
            :disabled="mangaImageCount === 0 && mangaImageBytes === 0"
            @click="handleClearImages"
          >
            <template #prefix>
              <AppIcon name="trash" size="xs" :stroke-width="1.8" />
            </template>
            清理阅览图片缓存 (释放 {{ mangaImageBytesFormatted }})
          </AppButton>

          <div class="reset-wrapper" :class="{ 'is-confirming': isConfirmingReset }">
            <template v-if="!isConfirmingReset">
              <button type="button" class="reset-btn" :disabled="clearing" @click="handleResetAll">
                重置全部离线环境
              </button>
            </template>
            <template v-else>
              <div class="confirm-box">
                <span class="confirm-warning">清空所有离线资源并注销 Service Worker</span>
                <div class="confirm-actions">
                  <button
                    type="button"
                    class="confirm-btn danger"
                    :disabled="clearing"
                    @click="handleResetAll"
                  >
                    确认彻底重置
                  </button>
                  <button type="button" class="confirm-btn cancel" @click="cancelReset">
                    取消
                  </button>
                </div>
              </div>
            </template>
          </div>
        </footer>
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

.storage-update-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: var(--space-2) var(--space-2-5);
  border: 1px solid color-mix(in oklab, var(--accent) 45%, var(--line));
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--accent-soft) 40%, var(--paper-0));
}

.update-card-left {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-width: 0;
}

.update-pill {
  display: inline-grid;
  place-items: center;
  padding: 0.1rem 0.35rem;
  border-radius: var(--radius-1);
  background: var(--accent);
  color: var(--paper-0);
  font-size: var(--text-caption);
  font-weight: 600;
  line-height: 1;
  flex: 0 0 auto;
}

.update-card-text {
  display: flex;
  flex-direction: column;
  min-width: 0;
}

.update-card-title {
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--ink-0);
  line-height: var(--leading-tight);
}

.update-card-sub {
  font-size: 0.625rem;
  color: var(--ink-2);
  line-height: 1.2;
}

.update-card-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  height: var(--control-xs);
  padding: 0 var(--space-2-5);
  border: 1px solid color-mix(in oklab, var(--accent) 60%, transparent);
  border-radius: var(--radius-1);
  background: var(--accent);
  color: var(--paper-0);
  font-size: var(--text-xs);
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  flex: 0 0 auto;
  transition: all var(--duration-1) var(--ease-out);
}

.update-card-btn:hover:not(:disabled) {
  background: var(--accent-strong);
}

.update-card-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.is-spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.storage-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3-5);
  padding: var(--space-3-5);
  color: var(--ink-0);
}

.storage-panel__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.panel-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-0);
  line-height: 1.2;
}

.panel-subtitle {
  display: block;
  font-size: 0.625rem;
  color: var(--ink-2);
  letter-spacing: 0.04em;
  margin-top: 1px;
}

.pwa-install-btn {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0.2rem 0.5rem;
  border: 1px solid color-mix(in oklab, var(--accent) 35%, var(--line));
  border-radius: var(--radius-1);
  background: var(--accent-soft);
  color: var(--accent-strong);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.pwa-install-btn:hover {
  background: color-mix(in oklab, var(--accent) 22%, var(--paper-0));
  border-color: var(--accent);
}

.pwa-standalone-pill {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

/* 存储刻度槽：3px 平直装订质感 */
.storage-gauge {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.gauge-meta {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  font-size: var(--text-xs);
}

.gauge-name {
  color: var(--ink-1);
}

.gauge-value strong {
  color: var(--ink-0);
  font-weight: 600;
}

.gauge-value small {
  color: var(--ink-2);
}

.storage-track {
  width: 100%;
  height: 6px;
  background: var(--paper-2);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  overflow: hidden;
}

.storage-fill {
  height: 100%;
  width: 100%;
  background: var(--accent);
  border-radius: var(--radius-1);
  transform-origin: left;
  transition: transform var(--duration-2) var(--ease-out);
}

/* 分项清单 */
.storage-breakdown {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  border-top: 1px solid var(--line);
  border-bottom: 1px solid var(--line);
  padding: var(--space-2-5) 0;
}

.breakdown-item {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
}

.item-title {
  display: block;
  font-size: var(--text-xs);
  font-weight: 500;
  color: var(--ink-0);
  line-height: 1.2;
}

.item-desc {
  display: block;
  font-size: var(--text-caption);
  color: var(--ink-2);
  line-height: 1.3;
}

.item-metric {
  font-size: var(--text-xs);
  color: var(--ink-1);
  white-space: nowrap;
}

/* 安全边界提示 */
.storage-boundary {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
  color: var(--ink-2);
  font-size: var(--text-caption);
  line-height: 1.35;
}

.storage-boundary p {
  margin: 0;
}

/* 操作尾部 */
.storage-panel__footer {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.reset-wrapper {
  display: flex;
  justify-content: center;
}

.reset-btn {
  background: transparent;
  border: none;
  min-height: 38px;
  padding: var(--space-1) var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
  cursor: pointer;
  text-decoration: underline;
  text-underline-offset: 3px;
  transition: color var(--duration-1) var(--ease-out);
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.reset-btn:hover:not(:disabled) {
  color: var(--accent);
}

.reset-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.confirm-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-1-5);
  padding: var(--space-2);
  background: var(--accent-soft);
  border: 1px dashed color-mix(in oklab, var(--accent) 40%, var(--line));
  border-radius: var(--radius-1);
  width: 100%;
}

.confirm-warning {
  font-size: var(--text-caption);
  color: var(--accent-strong);
  text-align: center;
}

.confirm-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.confirm-btn {
  padding: 0.25rem 0.65rem;
  border-radius: var(--radius-1);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  cursor: pointer;
  min-height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.confirm-btn.danger {
  background: var(--accent);
  color: #fff;
  border: 1px solid var(--accent-strong);
}

.confirm-btn.danger:hover {
  background: var(--accent-strong);
}

.confirm-btn.cancel {
  background: var(--paper-1);
  border: 1px solid var(--line);
  color: var(--ink-1);
}

.confirm-btn.cancel:hover {
  background: var(--paper-2);
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
  .storage-fill,
  .storage-badge-btn,
  .pwa-install-btn,
  .confirm-btn {
    transition: none !important;
  }
}
</style>
