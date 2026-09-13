<script setup lang="ts">
/**
 * @file GatePasswordInput.vue
 * @description 门禁专属密码/口令输入组件。
 *
 * 封装能力：
 * 1. 左侧锁头/通行证图标与右侧明文/密文眼眸切换；
 * 2. 基于 VueUse useFocus 提供声明式无重排自动聚焦；
 * 3. 错误态警示边框与状态感知；
 * 4. 密码输入字体与占位符对齐。
 */

import { ref } from 'vue'
import { useFocus } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import type { IconName } from '@/components/icons'

const modelValue = defineModel<string>({ default: '' })

const props = withDefaults(
  defineProps<{
    id?: string
    placeholder?: string
    autocomplete?: string
    inputmode?: 'text' | 'numeric' | 'decimal' | 'tel' | 'search' | 'email' | 'url'
    pattern?: string
    maxlength?: number
    disabled?: boolean
    error?: boolean
    autofocus?: boolean
    icon?: IconName
    monospace?: boolean
  }>(),
  {
    id: undefined,
    placeholder: '',
    autocomplete: 'current-password',
    inputmode: undefined,
    pattern: undefined,
    maxlength: undefined,
    disabled: false,
    error: false,
    autofocus: false,
    icon: 'lock',
    monospace: false,
  },
)

const showPassword = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

if (props.autofocus) {
  useFocus(inputRef, { initialValue: true })
}

defineExpose({
  focus: () => inputRef.value?.focus(),
  inputEl: inputRef,
})
</script>

<template>
  <div class="input-wrap" :class="{ error }">
    <span class="input-icon" aria-hidden="true">
      <AppIcon :name="icon" size="md" />
    </span>
    <input
      :id="id"
      ref="inputRef"
      v-model="modelValue"
      :type="showPassword ? 'text' : 'password'"
      class="gate-input"
      :class="{ 'is-monospace': monospace || inputmode === 'numeric' }"
      :placeholder="placeholder"
      :autocomplete="autocomplete"
      :inputmode="inputmode"
      :pattern="pattern"
      :maxlength="maxlength"
      :disabled="disabled"
    />
    <button
      type="button"
      class="btn-toggle-eye"
      :aria-label="showPassword ? '隐藏口令' : '显示口令'"
      :disabled="disabled"
      tabindex="-1"
      @click="showPassword = !showPassword"
    >
      <AppIcon :name="showPassword ? 'eye-off' : 'eye'" size="18" />
    </button>
  </div>
</template>

<style scoped>
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

.gate-input.is-monospace {
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
</style>
