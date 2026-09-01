<script setup lang="ts">
/**
 * @file GuestSuccessVoucher.vue
 * @description 通行证印发成功后就地呈现的水墨凭据卡组件。
 *
 * 核心功能：
 * - 呈现访客名称、有效期、设备席位与完整/脱敏口令；
 * - 复制专属免密直达链接 / 通行口令（带 1.5s VueUse `refAutoReset` 成功反馈）；
 * - 提供「继续印发」与「查看名册」快捷动作按钮。
 */

import { refAutoReset } from '@vueuse/core'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { formatTimestamp, maskToken } from './guestUtils'
import { useGuestPasses } from '@/composables/useGuestPasses'
import type { GuestPass } from '@/types'

const props = defineProps<{
  /** 新生成的通行证实体 */
  pass: GuestPass
}>()

const emit = defineEmits<{
  /** 触发继续印发下一张 */
  issueNext: []
  /** 触发返回现存名册 */
  viewRoster: []
}>()

const { copyShareLink, copyToken } = useGuestPasses()

/** 直达链接复制成功反馈 */
const copiedLink = refAutoReset(false, 1500)
/** 口令复制成功反馈 */
const copiedToken = refAutoReset(false, 1500)

/** 复制免密链接 */
async function handleCopyLink() {
  const ok = await copyShareLink(props.pass)
  if (ok) copiedLink.value = true
}

/** 复制通行口令 */
async function handleCopyToken() {
  const ok = await copyToken(props.pass)
  if (ok) copiedToken.value = true
}
</script>

<template>
  <div class="issued-voucher-card">
    <div class="voucher-head">
      <span class="voucher-seal">〔 通行凭据已印发 〕</span>
      <h3 class="voucher-title">{{ pass.username }}</h3>
      <p class="voucher-sub">
        专属通行证已生成，有效期至
        {{ formatTimestamp(pass.expires_at) }}，允许同时授权 {{ pass.max_devices }} 台设备。
      </p>
    </div>

    <div class="voucher-actions">
      <button
        type="button"
        class="hero-btn primary voucher-hero-btn"
        :class="{ copied: copiedLink }"
        @click="handleCopyLink"
      >
        <AppIcon :name="copiedLink ? 'check' : 'external-link'" size="md" />
        <span>{{ copiedLink ? '已复制免密直达链接' : '复制专属免密直达链接' }}</span>
      </button>

      <button
        type="button"
        class="hero-btn secondary voucher-hero-btn"
        :class="{ copied: copiedToken }"
        @click="handleCopyToken"
      >
        <AppIcon :name="copiedToken ? 'check' : 'copy'" size="sm" />
        <span>{{ copiedToken ? '已复制口令' : `口令：${maskToken(pass.token)}` }}</span>
      </button>
    </div>

    <div class="voucher-foot">
      <AppButton variant="secondary" size="md" class="voucher-nav-btn" @click="emit('issueNext')">
        <AppIcon name="plus" size="sm" />
        <span>继续登记下一张</span>
      </AppButton>
      <AppButton variant="ghost" size="md" class="voucher-nav-btn" @click="emit('viewRoster')">
        <span>查看现存名册</span>
      </AppButton>
    </div>
  </div>
</template>

<style scoped>
/* 印发成功实体凭据卡 */
.issued-voucher-card {
  background: var(--paper-0);
  border: 1px solid color-mix(in oklab, var(--accent) 35%, var(--line));
  border-radius: var(--radius-2);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  box-shadow: var(--shadow-2);
}

.voucher-head {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  text-align: center;
  align-items: center;
  padding-bottom: var(--space-3);
  border-bottom: 1px dashed var(--line);
}

.voucher-seal {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 0.08em;
}

.voucher-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-title);
  color: var(--ink-0);
  font-weight: 700;
}

.voucher-sub {
  margin: 0;
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.voucher-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2-5);
}

.hero-btn {
  width: 100%;
  min-height: 42px;
  padding: 0 var(--space-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border-radius: var(--radius-1);
  font-size: var(--text-caption);
  cursor: pointer;
  transition: all var(--duration-2) var(--ease-out);
}

.hero-btn.primary {
  background: color-mix(in oklab, var(--accent) 10%, var(--paper-0));
  border: 1px solid color-mix(in oklab, var(--accent) 30%, var(--line));
  color: var(--accent);
  font-weight: 600;
}

.hero-btn.primary:hover {
  background: var(--accent);
  color: var(--paper-0);
  border-color: var(--accent);
}

.hero-btn.secondary {
  background: var(--paper-1);
  border: 1px dashed var(--line);
  color: var(--ink-1);
  font-family: var(--font-mono);
}

.hero-btn.secondary:hover {
  border-color: var(--ink-0);
  color: var(--ink-0);
}

.hero-btn.copied {
  border-color: color-mix(in oklab, var(--success) 45%, transparent) !important;
  background: color-mix(in oklab, var(--success) 8%, var(--paper-0)) !important;
  color: var(--success) !important;
  border-style: solid !important;
  font-weight: 600;
}

.hero-btn.copied:hover {
  border-color: color-mix(in oklab, var(--success) 60%, transparent) !important;
  background: color-mix(in oklab, var(--success) 14%, var(--paper-0)) !important;
  color: var(--success) !important;
}

.voucher-hero-btn {
  min-height: 46px;
  font-size: var(--text-body);
}

.voucher-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--line);
}

.voucher-nav-btn {
  flex: 1;
}
</style>
