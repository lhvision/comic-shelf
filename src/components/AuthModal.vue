<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import { useAuth } from '@/composables/useAuth'

const { authRequired, authenticated, modalVisible, submitting, errorMessage, login, closeModal } =
  useAuth()

const inputSecret = ref('')
const showPassword = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

watch(modalVisible, (visible) => {
  if (visible) {
    inputSecret.value = ''
    nextTick(() => {
      inputRef.value?.focus()
    })
  }
})

async function handleSubmit() {
  if (submitting.value) return
  const success = await login(inputSecret.value)
  if (success) {
    inputSecret.value = ''
  }
}

function handleBackdropClick() {
  // Only allow closing backdrop if we are already authenticated or auth is not required
  if (authenticated.value || !authRequired.value) {
    closeModal()
  }
}

function togglePasswordVisibility() {
  showPassword.value = !showPassword.value
}
</script>

<template>
  <Teleport to="body">
    <div
      v-if="modalVisible"
      class="auth-backdrop"
      @click.self="handleBackdropClick"
      role="dialog"
      aria-modal="true"
      aria-labelledby="auth-modal-title"
    >
      <div class="auth-card">
        <header class="auth-header">
          <div class="auth-brand-badge">
            <img class="brand-logo" src="/brand-icon.webp" alt="" aria-hidden="true" />
          </div>
          <div class="auth-title-group">
            <div class="brand-eyebrow">
              <strong>纸间</strong>
              <span>Paper Room</span>
            </div>
            <h2 id="auth-modal-title" class="auth-title">阅览室通行口令</h2>
            <p class="auth-subtitle">私人收藏受口令保护，请输入访问密钥以进入</p>
          </div>
        </header>

        <form class="auth-form" @submit.prevent="handleSubmit">
          <div class="input-wrap" :class="{ error: !!errorMessage }">
            <span class="input-icon" aria-hidden="true">
              <svg
                viewBox="0 0 24 24"
                width="16"
                height="16"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </span>
            <input
              ref="inputRef"
              v-model="inputSecret"
              :type="showPassword ? 'text' : 'password'"
              class="secret-input"
              placeholder="输入访问密钥 (COMIC_SHELF_SECRET)"
              autocomplete="current-password"
              :disabled="submitting"
            />
            <button
              type="button"
              class="btn-toggle-eye"
              :aria-label="showPassword ? '隐藏口令' : '显示口令'"
              @click="togglePasswordVisibility"
            >
              <svg
                v-if="!showPassword"
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
                <circle cx="12" cy="12" r="3" />
              </svg>
              <svg
                v-else
                viewBox="0 0 24 24"
                width="18"
                height="18"
                fill="none"
                stroke="currentColor"
                stroke-width="2"
                stroke-linecap="round"
                stroke-linejoin="round"
              >
                <path
                  d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24"
                />
                <line x1="1" y1="1" x2="23" y2="23" />
              </svg>
            </button>
          </div>

          <p v-if="errorMessage" class="error-text" role="alert">
            {{ errorMessage }}
          </p>

          <div class="auth-actions">
            <button
              v-if="authenticated || !authRequired"
              type="button"
              class="btn-secondary"
              @click="closeModal"
            >
              取消
            </button>
            <button type="submit" class="btn-primary" :disabled="submitting || !inputSecret.trim()">
              <span v-if="submitting">验证中…</span>
              <span v-else>解锁进入</span>
            </button>
          </div>
        </form>

        <footer class="auth-footer">
          <span>防盗链与私有数据安全保护已就绪</span>
        </footer>
      </div>
    </div>
  </Teleport>
</template>

<style scoped>
.auth-backdrop {
  position: fixed;
  inset: 0;
  z-index: 100;
  display: grid;
  place-items: center;
  padding: var(--space-4);
  background: color-mix(in oklab, var(--ink-0) 45%, transparent);
  backdrop-filter: blur(16px);
  animation: fadeIn var(--duration-2) var(--ease-out);
}

.auth-card {
  width: min(100%, 420px);
  background: var(--paper-0);
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-3);
  padding: var(--space-6);
  box-shadow: var(--shadow-3);
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
  animation: scaleUp var(--duration-2) var(--ease-spring);
}

.auth-header {
  display: flex;
  align-items: center;
  gap: var(--space-4);
}

.auth-brand-badge {
  width: 3.25rem;
  height: 3.25rem;
  border-radius: var(--radius-2);
  background: var(--paper-1);
  border: 1px solid var(--line-strong);
  display: grid;
  place-items: center;
  flex-shrink: 0;
  box-shadow: var(--shadow-1);
  overflow: hidden;
}

.brand-logo {
  width: 2.4rem;
  height: 2.4rem;
  object-fit: contain;
  border-radius: var(--radius-1);
}

.auth-title-group {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.brand-eyebrow {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.brand-eyebrow strong {
  font-family: var(--font-display);
  font-size: var(--text-xs);
  color: var(--accent);
  letter-spacing: 0.04em;
}

.auth-title {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  font-weight: 700;
  color: var(--ink-0);
  margin: 0;
  letter-spacing: 0.02em;
}

.auth-subtitle {
  font-size: var(--text-xs);
  color: var(--ink-2);
  margin: 0;
  line-height: 1.4;
}

.auth-form {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.input-wrap {
  position: relative;
  display: flex;
  align-items: center;
  background: var(--paper-1);
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

.secret-input {
  flex: 1;
  border: none;
  background: transparent;
  padding: var(--space-3) var(--space-3);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--ink-0);
  outline: none;
}

.secret-input::placeholder {
  color: var(--ink-2);
  opacity: 0.7;
  font-family: var(--font-body);
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

.auth-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-1);
}

.btn-primary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: var(--control-sm);
  padding: 0 var(--space-5);
  background: var(--accent);
  color: var(--paper-0);
  border: none;
  border-radius: var(--radius-2);
  font-size: var(--text-sm);
  font-weight: 600;
  letter-spacing: 0.04em;
  cursor: pointer;
  transition:
    background var(--duration-1) var(--ease-out),
    transform var(--duration-1) var(--ease-out);
}

.btn-primary:hover:not(:disabled) {
  background: var(--accent-strong);
}

.btn-primary:active:not(:disabled) {
  transform: scale(0.98);
}

.btn-primary:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.btn-secondary {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: var(--control-sm);
  padding: 0 var(--space-4);
  background: transparent;
  color: var(--ink-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  font-size: var(--text-sm);
  cursor: pointer;
}

.btn-secondary:hover {
  background: var(--paper-1);
  color: var(--ink-0);
}

.auth-footer {
  padding-top: var(--space-3);
  border-top: 1px dashed var(--line);
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
  text-align: center;
}

@keyframes fadeIn {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

@keyframes scaleUp {
  from {
    transform: scale(0.96);
    opacity: 0;
  }
  to {
    transform: scale(1);
    opacity: 1;
  }
}
</style>
