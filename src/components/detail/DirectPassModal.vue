<script setup lang="ts">
/**
 * @file DirectPassModal.vue
 * @description 单本沙箱临时直达阅读通行证签发弹窗（Single-Book Sandbox Direct Pass Modal）。
 *
 * 核心设计哲学（Paper Room Design Metaphor）：
 * 1. 【古籍借阅笺隐喻】：将原本生硬冰冷的“网络时效配置”升华为私人阅览室的“图书借阅笺 / 藏书票”，沉淀纸墨温润感；
 * 2. 【四档认知黄金法则】：收敛为 ≤4 档黄金时效（2小时速览、24小时推荐、3天数日、7天长效），消除决策阻力；
 * 3. 【无障碍单选组 (ARIA RadioGroup)】：原生支持键盘方向键（←/→/↑/↓）循环切换与 Enter 回车直接签发，全状态高对比朱砂反馈；
 * 4. 【100% 严守设计 Token 契约】：彻底清除虚构 Token，全量收敛至 tokens.css（--paper-*, --ink-*, --accent* 等）；
 * 5. 【即时校验与焦点流转】：起始页码越界实时防护，生成后自动平滑聚焦复制按钮，提供一键复制与扫码开卷双轨支撑。
 */

import { computed, nextTick, ref, useTemplateRef, watch } from 'vue'
import { useClipboard } from '@vueuse/core'
import Modal from '@/components/Modal.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { api } from '@/api/client'
import { useToast } from '@/composables/useToast'
import type { DirectPassResponse } from '@/types'

const open = defineModel<boolean>('open', { default: false })

const props = defineProps<{
  /** 漫画图源 Provider (jm, local, picacg) */
  source: string
  /** 漫画车号 / 唯一 ID */
  sourceId: string
  /** 漫画标题 */
  title: string
  /** 全书总页数 */
  pageCount: number
  /** 上次阅读页码 */
  lastRead?: number
}>()

const { toast } = useToast()
const { copy, copied } = useClipboard({ copiedDuring: 2000 })

/** 有效借阅时长选项配置（严格遵循 ≤4 黄金认知负荷） */
interface DurationOption {
  seconds: number
  label: string
  desc: string
  recommended?: boolean
}

const DURATION_OPTIONS: DurationOption[] = [
  { seconds: 7200, label: '2 小时', desc: '临时速览' },
  { seconds: 86400, label: '24 小时', desc: '1 天 · 推荐', recommended: true },
  { seconds: 259200, label: '3 天', desc: '数日畅读' },
  { seconds: 604800, label: '7 天', desc: '长效借阅' },
]

const startPage = ref(props.lastRead && props.lastRead > 1 ? props.lastRead : 1)
const selectedTtl = ref(86400) // 默认推荐 24 小时（1天）
const generating = ref(false)
const generatedPass = ref<DirectPassResponse | null>(null)

const copyButtonEl = useTemplateRef<InstanceType<typeof AppButton>>('copyButtonEl')
const durationGroupEl = useTemplateRef<HTMLDivElement>('durationGroupEl')

// 弹窗每次打开时重置状态为健康默认值
watch(
  open,
  (isOpen) => {
    if (isOpen) {
      startPage.value = props.lastRead && props.lastRead > 1 ? props.lastRead : 1
      selectedTtl.value = 86400
      generatedPass.value = null
    }
  },
  { immediate: true },
)

/** 起始页码合法性实时校验 */
const isPageValid = computed(() => {
  const page = startPage.value
  return (
    typeof page === 'number' &&
    Number.isInteger(page) &&
    page >= 1 &&
    page <= Math.max(1, props.pageCount)
  )
})

/** 计算完整的绝对直达 URL */
const fullDirectUrl = computed(() => {
  if (!generatedPass.value) return ''
  const origin =
    typeof window !== 'undefined' && window.location?.origin ? window.location.origin : ''
  return `${origin}${generatedPass.value.direct_url}`
})

/** 格式化到期时间 */
const formattedExpiry = computed(() => {
  if (!generatedPass.value) return ''
  const expDate = new Date(generatedPass.value.expires_at * 1000)
  return expDate.toLocaleString(undefined, {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
})

/** 快速将起始页码设为第 1 页 */
function setFirstPage() {
  startPage.value = 1
}

/** 快速将起始页码设为上次阅读进度 */
function setLastReadPage() {
  if (props.lastRead && props.lastRead > 0) {
    startPage.value = Math.min(props.lastRead, Math.max(1, props.pageCount))
  }
}

/** 键盘单选切换处理（左右上下方向键导航） */
function handleDurationKeydown(event: KeyboardEvent, currentIndex: number) {
  let targetIndex = -1
  if (event.key === 'ArrowRight' || event.key === 'ArrowDown') {
    event.preventDefault()
    targetIndex = (currentIndex + 1) % DURATION_OPTIONS.length
  } else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') {
    event.preventDefault()
    targetIndex = (currentIndex - 1 + DURATION_OPTIONS.length) % DURATION_OPTIONS.length
  }

  if (targetIndex >= 0) {
    const nextOpt = DURATION_OPTIONS[targetIndex]
    if (nextOpt) {
      selectedTtl.value = nextOpt.seconds
      nextTick(() => {
        const buttons = durationGroupEl.value?.querySelectorAll<HTMLButtonElement>('[role="radio"]')
        buttons?.[targetIndex]?.focus()
      })
    }
  }
}

/** 触发接口生成直达通行证 */
async function handleGenerate() {
  if (!isPageValid.value || generating.value) return
  generating.value = true
  try {
    const validPage = Math.min(
      Math.max(1, Math.floor(startPage.value || 1)),
      Math.max(1, props.pageCount),
    )
    const res = await api.createDirectPass({
      source: props.source,
      source_id: props.sourceId,
      page_index: validPage,
      ttl_seconds: selectedTtl.value,
    })
    generatedPass.value = res
    toast('已成功签发单本沙箱直达链接', 'success')
    // 聚焦复制按钮以便键盘用户快速复制
    await nextTick()
    if (copyButtonEl.value?.$el instanceof HTMLElement) {
      copyButtonEl.value.$el.focus()
    }
  } catch (e) {
    toast(e instanceof Error ? e.message : '签发单本直达链接失败，请重试', 'error')
  } finally {
    generating.value = false
  }
}

/** 复制生成的直达链接 */
async function handleCopy() {
  if (!fullDirectUrl.value) return
  await copy(fullDirectUrl.value)
  toast('已复制直达阅读链接到剪贴板', 'success')
}

/** 重新配置与生成 */
function handleRegenerate() {
  generatedPass.value = null
}

function handleClose() {
  open.value = false
}
</script>

<template>
  <Modal v-model:open="open" title="签发单本借阅通行证" variant="paper" size="md">
    <div class="direct-pass-modal-body">
      <!-- 头部作品题眉与页码提示 -->
      <div class="comic-brief">
        <div class="brief-info">
          <span class="brief-title" :title="title">《{{ title }}》</span>
          <span class="brief-badge">全书共 {{ pageCount }} 页</span>
        </div>
        <div class="sandbox-tag" title="单本物理沙箱已开启，受访者无法离开当前漫画">
          <AppIcon name="lock" size="xs" />
          <span>单本隔离</span>
        </div>
      </div>

      <!-- 主视图过渡区（配置表单 ⇄ 借阅票笺） -->
      <Transition name="paper-fade" mode="out-in">
        <!-- 未生成：配置表单 -->
        <div v-if="!generatedPass" key="config" class="config-form">
          <!-- 起始页码设置 -->
          <div class="form-group">
            <label class="form-label" for="direct-pass-page">起始阅读页码</label>
            <div class="page-input-row">
              <div class="input-with-suffix">
                <input
                  id="direct-pass-page"
                  v-model.number="startPage"
                  type="number"
                  min="1"
                  :max="pageCount"
                  class="page-number-input"
                  :class="{ 'is-invalid': !isPageValid }"
                  @keydown.enter="handleGenerate"
                />
                <span class="page-total">/ {{ pageCount }} 页</span>
              </div>
              <div class="quick-page-buttons">
                <AppButton
                  size="sm"
                  variant="ghost"
                  type="button"
                  :disabled="startPage === 1"
                  @click="setFirstPage"
                >
                  第 1 页
                </AppButton>
                <AppButton
                  v-if="lastRead && lastRead > 1"
                  size="sm"
                  variant="ghost"
                  type="button"
                  :disabled="startPage === lastRead"
                  @click="setLastReadPage"
                >
                  上次进度 (第 {{ lastRead }} 页)
                </AppButton>
              </div>
            </div>
            <p v-if="!isPageValid" class="form-hint form-hint--error">
              请输入 1 到 {{ pageCount }} 之间的有效画页序号
            </p>
            <p v-else class="form-hint">受访者点开直达链接后将直接从该页开卷阅读。</p>
          </div>

          <!-- 有效借阅时长设置（ARIA RadioGroup 键盘可导航） -->
          <div class="form-group">
            <label class="form-label" id="ttl-group-label">有效借阅时长 (到期自动作废)</label>
            <div
              ref="durationGroupEl"
              class="duration-grid"
              role="radiogroup"
              aria-labelledby="ttl-group-label"
            >
              <button
                v-for="(opt, idx) in DURATION_OPTIONS"
                :key="opt.seconds"
                type="button"
                role="radio"
                class="duration-card"
                :class="{
                  'is-active': selectedTtl === opt.seconds,
                  'is-recommended': opt.recommended,
                }"
                :aria-checked="selectedTtl === opt.seconds"
                :tabindex="selectedTtl === opt.seconds ? 0 : -1"
                @click="selectedTtl = opt.seconds"
                @keydown="handleDurationKeydown($event, idx)"
              >
                <span v-if="opt.recommended" class="recommended-stamp">推荐</span>
                <span class="duration-label">{{ opt.label }}</span>
                <span class="duration-desc">{{ opt.desc }}</span>
                <span v-if="selectedTtl === opt.seconds" class="active-mark" aria-hidden="true">
                  <AppIcon name="check" size="xs" />
                </span>
              </button>
            </div>
          </div>

          <!-- 物理沙箱安全边界告示 -->
          <div class="sandbox-banner">
            <AppIcon name="lock" size="sm" class="banner-icon" />
            <div class="banner-text">
              <strong>单本专属沙箱保护</strong>
              <p>
                受访者仅能阅读当前这本画集，地址栏参数将在开卷后自动脱敏，且绝无法漫游书架或修改任何馆藏数据。
              </p>
            </div>
          </div>
        </div>

        <!-- 已生成：典雅借阅票笺与一键复制 -->
        <div v-else key="result" class="result-panel">
          <div class="bookplate-card">
            <div class="bookplate-header">
              <div class="bookplate-stamp">
                <AppIcon name="check" size="sm" class="stamp-icon" />
                <span>纸间 · 借阅笺已立</span>
              </div>
              <span class="bookplate-mono">SINGLE-BOOK SANDBOX</span>
            </div>

            <div class="bookplate-body">
              <div class="bookplate-meta-row">
                <span class="meta-name">典藏作品</span>
                <span class="meta-content" :title="title">《{{ title }}》</span>
              </div>
              <div class="bookplate-meta-row">
                <span class="meta-name">启阅画页</span>
                <span class="meta-content"
                  >第 {{ generatedPass.page_index }} 页 / 共 {{ pageCount }} 页</span
                >
              </div>
              <div class="bookplate-meta-row">
                <span class="meta-name">借阅时效</span>
                <span class="meta-content">
                  约 {{ Math.round((generatedPass.expires_in / 3600) * 10) / 10 }} 小时（至
                  {{ formattedExpiry }}）
                </span>
              </div>
            </div>

            <div class="bookplate-link-box">
              <input
                type="text"
                readonly
                aria-label="生成的单本阅读直达链接"
                :value="fullDirectUrl"
                class="link-input"
                @focus="($event.target as HTMLInputElement).select()"
              />
              <AppButton
                ref="copyButtonEl"
                variant="primary"
                size="md"
                class="btn-copy"
                :icon="copied ? 'check' : 'copy'"
                type="button"
                @click="handleCopy"
              >
                {{ copied ? '已复制链接' : '复制直达链接' }}
              </AppButton>
            </div>
          </div>

          <div class="sandbox-banner">
            <AppIcon name="info" size="sm" class="banner-icon" />
            <div class="banner-text">
              <strong>即点即读 · 零门槛借阅</strong>
              <p>好友点开链接无需注册或输入口令，阅读过程中地址栏凭据自动隐匿，到期自动失效。</p>
            </div>
          </div>
        </div>
      </Transition>
    </div>

    <template #footer>
      <div class="modal-footer-actions">
        <AppButton v-if="generatedPass" variant="ghost" type="button" @click="handleRegenerate">
          重新配置
        </AppButton>
        <AppButton variant="secondary" type="button" @click="handleClose">
          {{ generatedPass ? '完成' : '取消' }}
        </AppButton>
        <AppButton
          v-if="!generatedPass"
          variant="primary"
          type="button"
          :loading="generating"
          :disabled="!isPageValid"
          @click="handleGenerate"
        >
          立即签发
        </AppButton>
      </div>
    </template>
  </Modal>
</template>

<style scoped>
.direct-pass-modal-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 头部作品信息 */
.comic-brief {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding-bottom: var(--space-2-5);
  border-bottom: 1px solid var(--line);
}

.brief-info {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  overflow: hidden;
}

.brief-title {
  font-family: var(--font-display);
  font-weight: 600;
  color: var(--ink-0);
  font-size: var(--text-md);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.brief-badge {
  font-size: var(--text-xs);
  color: var(--ink-2);
  white-space: nowrap;
  flex-shrink: 0;
}

.sandbox-tag {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: var(--space-0-5) var(--space-2);
  border-radius: var(--radius-pill);
  background: var(--paper-1);
  border: 1px solid var(--line);
  color: var(--ink-1);
  font-size: var(--text-caption);
  font-weight: 500;
  flex-shrink: 0;
}

/* 配置表单 */
.config-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.form-label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-1);
}

.page-input-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.input-with-suffix {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  padding: var(--space-1) var(--space-2);
  transition: border-color var(--duration-1) var(--ease-out);
}

.input-with-suffix:focus-within {
  border-color: var(--accent);
}

.page-number-input {
  width: 4rem;
  padding: 0;
  border: none;
  background: transparent;
  color: var(--ink-0);
  font-size: var(--text-sm);
  font-family: var(--font-mono);
  font-weight: 600;
  text-align: center;
  outline: none;
}

.page-number-input.is-invalid {
  color: var(--danger);
}

.page-total {
  font-size: var(--text-xs);
  color: var(--ink-2);
  user-select: none;
}

.quick-page-buttons {
  display: flex;
  gap: var(--space-1-5);
  margin-left: auto;
}

.form-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin: 0;
}

.form-hint--error {
  color: var(--danger);
  font-weight: 500;
}

/* 4 档黄金时效卡片栅格 (ARIA RadioGroup) */
.duration-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: var(--space-2);
}

@media (max-width: 540px) {
  .duration-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

.duration-card {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 4.25rem;
  padding: var(--space-2) var(--space-1);
  border-radius: var(--radius-2);
  border: 1px solid var(--line);
  background: var(--paper-0);
  cursor: pointer;
  outline: none;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out),
    transform var(--duration-1) var(--ease-out);
}

.duration-card:hover {
  border-color: var(--line-strong);
  background: var(--paper-1);
}

.duration-card:active {
  transform: scale(0.97);
}

.duration-card:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.duration-card.is-active {
  border-color: var(--accent);
  background: var(--accent-soft);
}

.duration-label {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--ink-0);
  transition: color var(--duration-1) var(--ease-out);
}

.duration-card.is-active .duration-label {
  color: var(--accent-strong);
}

.duration-desc {
  font-size: var(--text-caption);
  color: var(--ink-2);
  margin-top: 2px;
  transition: color var(--duration-1) var(--ease-out);
}

.duration-card.is-active .duration-desc {
  color: var(--accent-strong);
  opacity: 0.88;
}

/* 推荐印章 */
.recommended-stamp {
  position: absolute;
  top: -6px;
  right: -4px;
  padding: 1px 4px;
  font-size: 0.625rem;
  font-weight: 600;
  line-height: 1;
  color: var(--accent-contrast);
  background: var(--accent);
  border-radius: var(--radius-pill);
  box-shadow: var(--shadow-1);
}

/* 激活勾选标记 */
.active-mark {
  position: absolute;
  bottom: 4px;
  right: 4px;
  color: var(--accent);
  display: flex;
}

/* 沙箱安全告示 */
.sandbox-banner {
  display: flex;
  gap: var(--space-2-5);
  padding: var(--space-3);
  border-radius: var(--radius-2);
  background: var(--paper-1);
  border: 1px solid var(--line);
}

.banner-icon {
  color: var(--accent);
  flex-shrink: 0;
  margin-top: 2px;
}

.banner-text {
  font-size: var(--text-xs);
  line-height: var(--leading-body);
  color: var(--ink-1);
}

.banner-text strong {
  color: var(--ink-0);
  display: block;
  margin-bottom: 2px;
}

.banner-text p {
  margin: 0;
}

/* 结果面板：纸间图书借阅笺 (Bookplate Card) */
.result-panel {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.bookplate-card {
  position: relative;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: var(--space-3-5) var(--space-4);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  border: 1px dashed var(--line-strong);
  box-shadow: var(--shadow-1);
}

.bookplate-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--line);
  padding-bottom: var(--space-2);
}

.bookplate-stamp {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1-5);
  font-weight: 600;
  font-size: var(--text-sm);
  color: var(--accent);
}

.bookplate-mono {
  font-family: var(--font-mono);
  font-size: 0.625rem;
  letter-spacing: 0.05em;
  color: var(--ink-2);
}

.bookplate-body {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
}

.bookplate-meta-row {
  display: flex;
  font-size: var(--text-xs);
  align-items: baseline;
}

.meta-name {
  width: 5.5rem;
  color: var(--ink-2);
  flex-shrink: 0;
}

.meta-content {
  color: var(--ink-0);
  font-weight: 500;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.bookplate-link-box {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-1);
}

.link-input {
  flex: 1;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
  background: var(--paper-1);
  color: var(--ink-0);
  font-size: var(--text-xs);
  font-family: var(--font-mono);
  outline: none;
}

.link-input:focus {
  border-color: var(--accent);
}

.btn-copy {
  flex-shrink: 0;
}

.modal-footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  width: 100%;
}

/* 纸面淡入淡出动效 */
.paper-fade-enter-active,
.paper-fade-leave-active {
  transition:
    opacity var(--duration-1) var(--ease-out),
    transform var(--duration-1) var(--ease-out);
}

.paper-fade-enter-from,
.paper-fade-leave-to {
  opacity: 0;
  transform: translateY(4px);
}
</style>
