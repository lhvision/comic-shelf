<script setup lang="ts">
/**
 * @file GateSecretForm.vue
 * @description 门禁第一阶段：初始口令/密钥输入表单。
 */

import { nextTick, onMounted, ref } from 'vue'
import { useAuth } from '@/composables/useAuth'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'

const { submitting, errorMessage, login } = useAuth()

const inputSecret = ref('')
const showPassword = ref(false)
const secretInputRef = ref<HTMLInputElement | null>(null)

onMounted(() => {
  nextTick(() => {
    secretInputRef.value?.focus()
  })
})

async function handleSecretSubmit() {
  if (submitting.value) return
  const token = inputSecret.value.trim()
  if (!token) return
  await login(token)
}
</script>

<template>
  <form class="gate-form" @submit.prevent="handleSecretSubmit">
    <div class="input-wrap" :class="{ error: !!errorMessage }">
      <span class="input-icon" aria-hidden="true">
        <AppIcon name="lock" size="md" />
      </span>
      <input
        ref="secretInputRef"
        v-model="inputSecret"
        :type="showPassword ? 'text' : 'password'"
        class="gate-input"
        placeholder="输入通行口令 (馆长密钥或访客口令)"
        autocomplete="current-password"
        :disabled="submitting"
      />
      <button
        type="button"
        class="btn-toggle-eye"
        :aria-label="showPassword ? '隐藏口令' : '显示口令'"
        @click="showPassword = !showPassword"
      >
        <AppIcon :name="showPassword ? 'eye-off' : 'eye'" size="18" />
      </button>
    </div>

    <p v-if="errorMessage" class="error-text" role="alert">
      {{ errorMessage }}
    </p>

    <div class="gate-actions">
      <AppButton
        type="submit"
        variant="primary"
        size="md"
        class="gate-submit-btn"
        :loading="submitting"
        :disabled="!inputSecret.trim()"
      >
        解锁进入
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
</style>
