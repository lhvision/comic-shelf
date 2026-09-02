<script setup lang="ts">
/**
 * @file GatePinForm.vue
 * @description 门禁第三阶段：已认领借阅证 PIN 码验证表单。
 */

import { nextTick, onMounted, ref } from 'vue'
import { useAuth } from '@/composables/useAuth'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'

const { submitting, errorMessage, pendingToken, username, login, resetAuthFormState } = useAuth()

const inputPin = ref('')
const showPassword = ref(false)
const pinInputRef = ref<HTMLInputElement | null>(null)

onMounted(() => {
  nextTick(() => {
    pinInputRef.value?.focus()
  })
})

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
      <div class="claim-badge active">🍃 读者借书证</div>
      <div class="claim-meta">
        读者：<strong>{{ username || '已认领访客' }}</strong>
      </div>
    </div>

    <div class="form-item">
      <label for="login-pin" class="form-label">请输入您的 4~6 位个人 PIN 码</label>
      <div class="input-wrap" :class="{ error: !!errorMessage }">
        <span class="input-icon" aria-hidden="true">
          <AppIcon name="lock" size="md" />
        </span>
        <input
          id="login-pin"
          ref="pinInputRef"
          v-model="inputPin"
          :type="showPassword ? 'text' : 'password'"
          inputmode="numeric"
          pattern="[0-9]*"
          maxlength="6"
          class="gate-input pin-input"
          placeholder="输入 4~6 位数字 PIN 码"
          autocomplete="current-password"
          :disabled="submitting"
        />
        <button
          type="button"
          class="btn-toggle-eye"
          :aria-label="showPassword ? '隐藏 PIN 码' : '显示 PIN 码'"
          @click="showPassword = !showPassword"
        >
          <AppIcon :name="showPassword ? 'eye-off' : 'eye'" size="18" />
        </button>
      </div>
    </div>

    <p v-if="errorMessage" class="error-text" role="alert">
      {{ errorMessage }}
    </p>

    <p class="pin-forgot-hint">
      <span>💡 提示：PIN 码为首次认领时自设；如遗忘可联系馆长在访客簿「清空 PIN」重新设置。</span>
    </p>

    <div class="gate-actions between">
      <AppButton type="button" variant="ghost" size="md" @click="handleBackToSecret">
        ← 更换口令
      </AppButton>

      <AppButton
        type="submit"
        variant="primary"
        size="md"
        class="gate-submit-btn"
        :loading="submitting"
        :disabled="!inputPin.trim() || inputPin.trim().length < 4"
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
  background: var(--paper-0);
  border: 1px dashed var(--line);
  border-radius: var(--radius-2);
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.claim-badge {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
  padding: 0.15rem 0.45rem;
  background: var(--paper-1);
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
}

.claim-badge.active {
  color: var(--accent);
  border-color: var(--accent-soft);
}

.claim-meta strong {
  color: var(--ink-0);
  font-weight: 600;
}

.form-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-label {
  font-size: var(--text-xs);
  color: var(--ink-2);
  font-weight: 500;
}

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  transition:
    border-color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out);
}

.input-icon {
  display: grid;
  place-items: center;
  padding-left: var(--space-3);
  color: var(--ink-2);
}

.input-wrap:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px var(--accent-soft);
}

.input-wrap:focus-within .input-icon {
  color: var(--accent);
}

.input-wrap.error {
  border-color: var(--accent-strong);
}

.gate-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: var(--space-3) var(--space-3);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  color: var(--ink-0);
  outline: none;
}

.gate-input.pin-input {
  font-family: var(--font-mono);
  letter-spacing: 0.15em;
}

.gate-input::placeholder {
  color: var(--ink-2);
  opacity: 0.7;
  font-family: var(--font-body);
  letter-spacing: normal;
}

.btn-toggle-eye {
  display: grid;
  place-items: center;
  padding: var(--space-2) var(--space-3);
  background: transparent;
  border: none;
  color: var(--ink-2);
  cursor: pointer;
  border-radius: var(--radius-1);
  transition: color var(--duration-1) var(--ease-out);
}

.btn-toggle-eye:hover {
  color: var(--ink-0);
}

.error-text {
  font-size: var(--text-xs);
  color: var(--accent-strong);
  margin: 0;
  padding-left: var(--space-1);
}

.pin-forgot-hint {
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin: 0;
  line-height: 1.4;
  padding: var(--space-2) var(--space-3);
  background: var(--paper-0);
  border-radius: var(--radius-1);
  border-left: 2px solid var(--line-strong);
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
