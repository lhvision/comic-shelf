<script setup lang="ts">
/**
 * @file GatePinForm.vue
 * @description 门禁第三阶段：已认领借阅证 PIN 码验证表单。
 */

import { ref } from 'vue'
import { useAuth } from '@/composables/useAuth'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import GatePasswordInput from '@/components/gate/GatePasswordInput.vue'

const { submitting, errorMessage, pendingToken, username, login, resetAuthFormState } = useAuth()

const inputPin = ref('')

async function handlePinSubmit() {
  if (submitting.value) return
  const pin = inputPin.value.trim()
  if (!pin) return
  await login(pendingToken.value, pin)
}

function handleBackToSecret() {
  resetAuthFormState()
}
</script>

<template>
  <form class="gate-form" @submit.prevent="handlePinSubmit">
    <div class="claim-info-card active">
      <div class="claim-badge active">
        <AppIcon name="book-open" size="xs" />
        <span>读者借书证</span>
      </div>
      <div class="claim-meta">
        读者：<strong>{{ username || '已认领访客' }}</strong>
      </div>
    </div>

    <div class="form-item">
      <label for="login-pin" class="form-label">请输入您的 4~6 位个人 PIN 码</label>
      <GatePasswordInput
        id="login-pin"
        v-model="inputPin"
        placeholder="输入 4~6 位数字 PIN 码"
        autocomplete="current-password"
        inputmode="numeric"
        pattern="[0-9]*"
        :maxlength="6"
        :disabled="submitting"
        :error="!!errorMessage"
        :autofocus="true"
      />
    </div>

    <p v-if="errorMessage" class="error-text" role="alert">
      {{ errorMessage }}
    </p>

    <p class="pin-forgot-hint">
      <AppIcon name="info" size="xs" class="hint-icon" />
      <span>提示：PIN 码为首次认领时自设；如遗忘可联系馆长在访客簿「清空 PIN」重新设置。</span>
    </p>

    <div class="gate-actions between">
      <AppButton
        type="button"
        variant="ghost"
        size="md"
        icon="arrow-left"
        @click="handleBackToSecret"
      >
        换个口令
      </AppButton>
      <AppButton
        type="submit"
        variant="primary"
        size="md"
        class="gate-submit-btn"
        :loading="submitting"
        :disabled="inputPin.trim().length < 4"
      >
        验证进入
      </AppButton>
    </div>
  </form>
</template>

<style scoped>
.gate-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.claim-info-card {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-3) var(--space-4);
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
}

.claim-info-card.active {
  background: color-mix(in oklab, var(--paper-1) 85%, var(--paper-2));
  border-color: var(--line-strong);
}

.claim-badge {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-size: var(--text-xs);
  color: var(--ink-1);
  font-weight: 600;
  padding: 0.15rem 0.5rem;
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
}

.claim-badge.active {
  background: var(--paper-0);
  color: var(--accent-strong);
  border-color: color-mix(in oklab, var(--accent) 30%, transparent);
}

.claim-meta {
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.claim-meta strong {
  color: var(--ink-0);
  font-weight: 600;
}

.error-text {
  font-size: var(--text-xs);
  color: var(--accent-strong);
  margin: 0;
  padding-left: var(--space-1);
}

.pin-forgot-hint {
  display: flex;
  align-items: flex-start;
  gap: var(--space-2);
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin: 0;
  line-height: 1.4;
  padding: var(--space-2) var(--space-3);
  background: var(--paper-0);
  border-radius: var(--radius-1);
  border-left: 2px solid var(--line-strong);
}

.pin-forgot-hint .hint-icon {
  flex-shrink: 0;
  margin-top: 2px;
}

.gate-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-1);
}

.gate-actions.between {
  justify-content: space-between;
}
</style>
