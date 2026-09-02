<script setup lang="ts">
/**
 * @file GateClaimForm.vue
 * @description 门禁第二阶段：待认领借阅证首次自设 PIN 码与读者称呼认领表单。
 */

import { nextTick, onMounted, ref } from 'vue'
import { useAuth } from '@/composables/useAuth'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'

const { submitting, errorMessage, username, claimPass, resetAuthFormState } = useAuth()

const inputNickname = ref('')
const inputPin = ref('')
const showPassword = ref(false)
const pinInputRef = ref<HTMLInputElement | null>(null)

onMounted(() => {
  nextTick(() => {
    pinInputRef.value?.focus()
  })
})

async function handleClaimSubmit() {
  if (submitting.value) return
  const pin = inputPin.value.trim()
  if (!pin) return
  await claimPass(pin, inputNickname.value.trim() || undefined)
}

function handleBackToSecret() {
  resetAuthFormState()
}
</script>

<template>
  <form class="gate-form" @submit.prevent="handleClaimSubmit">
    <div class="claim-info-card">
      <div class="claim-badge">🌿 待认领凭证</div>
      <div class="claim-meta">
        读者初始称呼：<strong>{{ username || '访客读者' }}</strong>
      </div>
    </div>

    <div class="form-item">
      <label for="claim-nickname" class="form-label">自定义称呼（可选）</label>
      <div class="input-wrap">
        <span class="input-icon" aria-hidden="true">
          <AppIcon name="users" size="md" />
        </span>
        <input
          id="claim-nickname"
          v-model="inputNickname"
          type="text"
          class="gate-input"
          placeholder="您的读者昵称 (留空保持原称呼)"
          maxlength="20"
          :disabled="submitting"
        />
      </div>
    </div>

    <div class="form-item">
      <label for="claim-pin" class="form-label">自设数字 PIN 码（4~6 位纯数字）</label>
      <div class="input-wrap" :class="{ error: !!errorMessage }">
        <span class="input-icon" aria-hidden="true">
          <AppIcon name="lock" size="md" />
        </span>
        <input
          id="claim-pin"
          ref="pinInputRef"
          v-model="inputPin"
          :type="showPassword ? 'text' : 'password'"
          inputmode="numeric"
          pattern="[0-9]*"
          maxlength="6"
          class="gate-input pin-input"
          placeholder="如 2026"
          autocomplete="new-password"
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
        确认认领并进入
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
