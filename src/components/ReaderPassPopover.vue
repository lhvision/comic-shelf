<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useClipboard } from '@vueuse/core'
import AppPopover from '@/components/AppPopover.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { useAuth } from '@/composables/useAuth'
import { useToast } from '@/composables/useToast'

const { username, logout, getStoredToken } = useAuth()
const { toast } = useToast()
const { copy, copied } = useClipboard({ copiedDuring: 1500 })

const isOpen = ref(false)
const isConfirming = ref(false)
const loggingOut = ref(false)

const cancelBtnRef = ref<InstanceType<typeof AppButton> | null>(null)
const promptBtnRef = ref<InstanceType<typeof AppButton> | null>(null)

const trimmedName = computed(() => username.value.trim())
const displayName = computed(() => trimmedName.value || '阅览室读者')
const badgeLabel = computed(() =>
  trimmedName.value ? `〔 读者 · ${trimmedName.value} 〕` : '〔 阅览室读者 〕',
)

function onOpen() {
  cancelReturn()
}

function handleCopyRoamLink() {
  const token = getStoredToken()
  if (!token) {
    toast('未找到当前借阅口令', 'error')
    return
  }
  const url = new URL(window.location.href)
  url.searchParams.set('token', token)
  url.hash = ''
  const roamUrl = url.toString()
  void copy(roamUrl)
  toast('已复制跨端入馆链接，在新设备打开输入您的 PIN 码即可入座', 'success')
}

async function handlePromptReturn() {
  isConfirming.value = true
  await nextTick()
  cancelBtnRef.value?.$el?.focus?.()
}

async function cancelReturn() {
  isConfirming.value = false
  await nextTick()
  promptBtnRef.value?.$el?.focus?.()
}

async function handleConfirmReturn() {
  if (loggingOut.value) return
  loggingOut.value = true
  try {
    await logout()
    isOpen.value = false
    isConfirming.value = false
    toast('已交还借阅凭证，设备席位已释放', 'info')
  } catch {
    toast('注销失败，请稍后重试', 'error')
  } finally {
    loggingOut.value = false
  }
}
</script>

<template>
  <AppPopover
    v-model:open="isOpen"
    side="bottom"
    align="end"
    arrow
    width="20.5rem"
    role="dialog"
    aria-label="读者借阅凭证卡"
    @open="onOpen"
  >
    <template #default="{ open, targetId }">
      <button
        type="button"
        class="reader-badge-btn"
        :title="`持证读者：${displayName}（点击查看借阅凭证）`"
        :aria-label="`持证读者：${displayName}，点击展开借阅凭证`"
        :aria-expanded="open"
        :aria-controls="targetId"
        aria-haspopup="dialog"
      >
        <AppIcon name="book-open" size="xs" :stroke-width="1.8" />
        <span class="reader-label">{{ badgeLabel }}</span>
      </button>
    </template>

    <template #content>
      <div class="reader-card">
        <!-- 头部印章与标题 -->
        <header class="reader-card__header">
          <div class="card-titles">
            <div class="title-row">
              <AppIcon name="book-open" size="sm" class="card-icon" />
              <h3 class="card-title">借阅凭证</h3>
            </div>
            <span class="card-subtitle font-mono">READER PASS</span>
          </div>

          <span class="status-seal">〔 持证阅览 〕</span>
        </header>

        <!-- 读者信息卡 -->
        <div class="reader-card__body">
          <div class="reader-plate">
            <span class="plate-label">持证读者</span>
            <strong class="plate-name">{{ displayName }}</strong>
          </div>

          <div class="privilege-note">
            <AppIcon name="heart" size="xs" class="note-icon" />
            <span class="note-text">专属书架已就绪 · 个人收藏与阅读进度已独立绑定</span>
          </div>

          <button
            type="button"
            class="btn-copy-roam"
            :class="{ copied }"
            title="复制专属直达链接，发给自己在新设备打开输入 PIN 码入座"
            @click="handleCopyRoamLink"
          >
            <AppIcon :name="copied ? 'check' : 'external-link'" size="xs" />
            <span>{{ copied ? '已复制跨端链接' : '复制入馆链接（换设备看）' }}</span>
          </button>
        </div>

        <!-- 底部交还操作 -->
        <footer class="reader-card__footer">
          <div v-if="isConfirming" class="confirm-box" role="group" aria-label="确认交还借阅凭证">
            <div class="confirm-header">
              <span class="confirm-title">确定交还借阅凭证？</span>
              <p class="confirm-desc">交还后将释放本设备席位，后续仍可凭原口令随时入座。</p>
            </div>
            <div class="confirm-actions">
              <AppButton
                ref="cancelBtnRef"
                variant="secondary"
                size="sm"
                class="confirm-btn"
                :disabled="loggingOut"
                @click="cancelReturn"
              >
                暂不交还
              </AppButton>
              <AppButton
                variant="danger"
                size="sm"
                class="confirm-btn"
                :loading="loggingOut"
                @click="handleConfirmReturn"
              >
                确认释放席位
              </AppButton>
            </div>
          </div>

          <AppButton
            v-else
            ref="promptBtnRef"
            variant="secondary"
            size="sm"
            class="btn-return-pass"
            @click="handlePromptReturn"
          >
            <AppIcon name="logout" size="xs" />
            <span>交还借阅凭证</span>
          </AppButton>
        </footer>
      </div>
    </template>
  </AppPopover>
</template>

<style scoped>
/* 顶栏徽章按钮（严格对齐顶栏响应式规范） */
.reader-badge-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-1) var(--space-2);
  line-height: 1.5;
  background: color-mix(in oklab, var(--paper-0) 60%, var(--paper-1));
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

.reader-badge-btn:hover {
  background: var(--paper-2);
  border-color: var(--line-strong);
  color: var(--ink-0);
}

.reader-badge-btn:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.reader-label {
  letter-spacing: 0.02em;
  max-width: 140px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 凭证卡面板 */
.reader-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3);
  color: var(--ink-0);
  background: var(--paper-0);
}

.reader-card__header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-2);
  padding-bottom: var(--space-2);
  border-bottom: 1px dashed var(--line);
}

.card-titles {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.title-row {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
}

.card-icon {
  color: var(--accent);
}

.card-title {
  margin: 0;
  font-family: var(--font-serif);
  font-size: var(--text-body);
  font-weight: 600;
  color: var(--ink-0);
  letter-spacing: 0.04em;
}

.card-subtitle {
  font-size: 0.65rem;
  letter-spacing: 0.12em;
  color: var(--ink-2);
}

.status-seal {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  padding: 1px 6px;
  border-radius: var(--radius-1);
  background: var(--paper-1);
  color: var(--ink-1);
  border: 1px solid var(--line);
  white-space: nowrap;
}

/* 卡片信息体 */
.reader-card__body {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.reader-plate {
  display: flex;
  flex-direction: column;
  gap: 2px;
  padding: var(--space-2) var(--space-2-5);
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
}

.plate-label {
  font-size: 0.68rem;
  color: var(--ink-2);
  font-family: var(--font-mono);
}

.plate-name {
  font-size: var(--text-body);
  font-family: var(--font-serif);
  color: var(--ink-0);
  letter-spacing: 0.02em;
  word-break: break-word;
}

.privilege-note {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1-5);
  padding: var(--space-1-5) var(--space-2);
  font-size: var(--text-caption);
  color: var(--ink-2);
  line-height: 1.4;
  background: var(--paper-1);
  border: 1px dashed var(--line);
  border-radius: var(--radius-1);
}

.note-icon {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--accent);
}

.note-text {
  flex: 1;
}

.btn-copy-roam {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1-5);
  width: 100%;
  padding: var(--space-2) var(--space-3);
  font-family: var(--font-body);
  font-size: var(--text-caption);
  color: var(--ink-1);
  background: var(--paper-1);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-1);
  cursor: pointer;
  transition:
    background-color var(--duration-1) var(--ease-out),
    border-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.btn-copy-roam:hover {
  background: var(--paper-2);
  color: var(--ink-0);
  border-color: var(--accent);
}

.btn-copy-roam.copied {
  color: var(--success);
  border-color: color-mix(in oklab, var(--success) 45%, transparent);
  background: color-mix(in oklab, var(--success) 8%, var(--paper-1));
}

/* 底部操作 */
.reader-card__footer {
  padding-top: var(--space-2);
  border-top: 1px dashed var(--line);
}

.btn-return-pass {
  width: 100%;
  justify-content: center;
}

.confirm-box {
  display: flex;
  flex-direction: column;
  gap: var(--space-2-5);
  padding: var(--space-2-5);
  background: var(--paper-1);
  border: 1px dashed var(--line);
  border-radius: var(--radius-1);
}

.confirm-header {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.confirm-title {
  font-size: var(--text-body);
  font-family: var(--font-serif);
  font-weight: 600;
  color: var(--ink-0);
}

.confirm-desc {
  margin: 0;
  font-size: var(--text-caption);
  color: var(--ink-2);
  line-height: 1.4;
}

.confirm-actions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
}

.confirm-btn {
  justify-content: center;
  min-height: 36px;
}

/* 移动端响应式规约（严格遵守 <=640px 规范） */
@media (max-width: 640px) {
  .reader-label {
    display: none;
  }

  .reader-badge-btn {
    width: var(--control-sm);
    height: var(--control-sm);
    min-width: var(--control-sm);
    min-height: var(--control-sm);
    padding: 0;
    justify-content: center;
  }
}

@media (max-width: 640px) and (pointer: coarse) {
  .reader-badge-btn::before {
    content: '';
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    min-width: 44px;
    min-height: 44px;
    width: 100%;
    height: 100%;
  }
}
</style>
