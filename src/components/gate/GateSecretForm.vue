<script setup lang="ts">
/**
 * @file GateSecretForm.vue
 * @description 门禁第一阶段：初始口令/密钥输入表单。
 */

import { ref } from 'vue'
import { useAuth } from '@/composables/useAuth'
import AppButton from '@/components/AppButton.vue'
import GatePasswordInput from '@/components/gate/GatePasswordInput.vue'

const { submitting, errorMessage, login } = useAuth()

const inputSecret = ref('')

async function handleSecretSubmit() {
  if (submitting.value) return
  const token = inputSecret.value.trim()
  if (!token) return
  await login(token)
}
</script>

<template>
  <form class="gate-form" @submit.prevent="handleSecretSubmit">
    <GatePasswordInput
      v-model="inputSecret"
      placeholder="输入通行口令 (馆长密钥或访客口令)"
      autocomplete="current-password"
      :disabled="submitting"
      :error="!!errorMessage"
      :autofocus="true"
    />

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
