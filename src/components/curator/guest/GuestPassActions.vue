<script setup lang="ts">
/**
 * @file GuestPassActions.vue
 * @description 访客通行证专属链接与脱敏口令一键复制操作组。
 * 供名册卡片（GuestCard）与印发凭据卡（GuestSuccessVoucher）共同复用，消除双端逻辑与样式重复。
 */
import { computed } from 'vue'
import { refAutoReset } from '@vueuse/core'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { maskToken } from './guestUtils'
import { useGuestPasses } from '@/composables/useGuestPasses'
import type { GuestPass } from '@/types'

const props = withDefaults(
  defineProps<{
    /** 通行证数据实体 */
    pass: GuestPass
    /** 视觉密度变体：card（名册卡片紧凑行）/ voucher（印发成功主凭据卡） */
    variant?: 'card' | 'voucher'
  }>(),
  {
    variant: 'card',
  },
)

const { copyShareLink, copyToken } = useGuestPasses()

/** 直达链接复制成功微反馈（1.5s 后自动归位） */
const copiedLink = refAutoReset(false, 1500)
/** 口令复制成功微反馈（1.5s 后自动归位） */
const copiedToken = refAutoReset(false, 1500)

const isVoucher = computed(() => props.variant === 'voucher')
const linkLabel = computed(() => {
  if (isVoucher.value) {
    return copiedLink.value ? '已复制免密直达链接' : '复制专属免密直达链接'
  }
  return copiedLink.value ? '已复制专属直达链接' : '复制专属直达链接'
})

async function handleCopyLink() {
  const ok = await copyShareLink(props.pass)
  if (ok) copiedLink.value = true
}

async function handleCopyToken() {
  const ok = await copyToken(props.pass)
  if (ok) copiedToken.value = true
}
</script>

<template>
  <div class="guest-pass-actions" :class="`variant-${variant}`">
    <AppButton
      :variant="copiedLink ? 'success' : 'soft'"
      :size="isVoucher ? 'md' : 'sm'"
      block
      class="pass-link-btn"
      :class="{ 'is-copied': copiedLink }"
      :title="isVoucher ? undefined : `复制「${pass.username}」免密直达专属链接`"
      @click="handleCopyLink"
    >
      <template #prefix>
        <AppIcon :name="copiedLink ? 'check' : 'external-link'" size="sm" />
      </template>
      <span>{{ linkLabel }}</span>
    </AppButton>

    <AppButton
      :variant="copiedToken ? 'success' : 'ghost'"
      :size="isVoucher ? 'md' : 'sm'"
      block
      class="pass-token-btn"
      :class="{ 'is-copied': copiedToken }"
      :title="isVoucher ? undefined : `复制通行口令：${pass.token}`"
      @click="handleCopyToken"
    >
      <template #prefix>
        <AppIcon :name="copiedToken ? 'check' : 'copy'" size="sm" />
      </template>
      <span>{{ copiedToken ? '已复制口令' : `口令：${maskToken(pass.token)}` }}</span>
    </AppButton>
  </div>
</template>

<style scoped>
.guest-pass-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.guest-pass-actions.variant-voucher {
  gap: var(--space-2-5);
}

.pass-link-btn,
.pass-token-btn {
  border-radius: var(--radius-1);
}

.variant-card .pass-link-btn,
.variant-card .pass-token-btn {
  min-height: 2.625rem;
  font-size: var(--text-caption);
}

.variant-voucher .pass-link-btn,
.variant-voucher .pass-token-btn {
  min-height: 2.875rem;
  font-size: var(--text-md);
}

.pass-token-btn:not(.is-copied) {
  background: var(--paper-1);
  border-style: dashed;
  border-color: var(--line);
  color: var(--ink-1);
  font-family: var(--font-mono);
}

.pass-token-btn:not(.is-copied):hover {
  border-color: var(--ink-0);
  color: var(--ink-0);
}

.is-copied {
  font-weight: 600;
}
</style>
