<script setup lang="ts">
/**
 * @file GuestIssueTab.vue
 * @description 访客簿登记印发表单面板。
 *
 * 核心功能：
 * - 输入访客姓名/备注名；
 * - 配置有效期预设胶囊（7天/30天/90天/半年/永久有效）；
 * - 配置授权设备上限（1~5台）；
 * - 提交创建后切换为 `GuestSuccessVoucher` 凭证卡；
 * - 暴露 `focusInput()` 方法供父组件自动聚焦。
 */

import { nextTick, ref, useTemplateRef } from 'vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import GuestSuccessVoucher from './GuestSuccessVoucher.vue'
import { useGuestPasses } from '@/composables/useGuestPasses'
import type { GuestPass } from '@/types'

const props = defineProps<{
  /** 刚印发成功的通行证（有值时展示凭证卡，为 null 时展示输入表单） */
  justCreatedPass: GuestPass | null
}>()

const emit = defineEmits<{
  /** 印发成功事件 */
  created: [pass: GuestPass]
  /** 重置表单以继续印发下一张 */
  resetIssue: []
  /** 印发完成后查看现存名册 */
  viewRoster: []
}>()

const { createPass } = useGuestPasses()

/** 访客姓名/代号输入值 */
const newUsername = ref('')
/** 选中的有效期天数 */
const selectedDays = ref<number | null>(30)
/** 选中的设备席位上限 */
const selectedMaxDevices = ref(2)
/** 是否正在创建中 */
const creating = ref(false)
/** 输入框 DOM Ref */
const inputRef = useTemplateRef<HTMLInputElement>('inputRef')

const dayOptions: { label: string; value: number | null }[] = [
  { label: '7 天', value: 7 },
  { label: '30 天', value: 30 },
  { label: '90 天', value: 90 },
  { label: '半年', value: 180 },
  { label: '永久有效', value: null },
]

const deviceOptions: { label: string; value: number }[] = [
  { label: '1 台 · 独占', value: 1 },
  { label: '2 台 · 手机+电脑', value: 2 },
  { label: '3 台 · 全家桶', value: 3 },
  { label: '4 台', value: 4 },
  { label: '5 台', value: 5 },
]

async function handleCreate() {
  if (!newUsername.value.trim() || creating.value) return
  creating.value = true
  try {
    const created = await createPass({
      username: newUsername.value.trim(),
      expires_days: selectedDays.value,
      max_devices: selectedMaxDevices.value,
    })
    if (created) {
      newUsername.value = ''
      emit('created', created)
    }
  } finally {
    creating.value = false
  }
}

function handleResetIssue() {
  newUsername.value = ''
  selectedMaxDevices.value = 2
  emit('resetIssue')
  void nextTick(() => {
    inputRef.value?.focus()
  })
}

function focusInput() {
  void nextTick(() => {
    inputRef.value?.focus()
  })
}

defineExpose({
  focusInput,
})
</script>

<template>
  <section
    id="tabpanel-issue"
    class="tab-content issue-pane"
    role="tabpanel"
    aria-label="登记印发新通行证"
  >
    <!-- 场景 A：印发成功后的实体凭据卡（原地一键发送，不切页打断心流） -->
    <GuestSuccessVoucher
      v-if="justCreatedPass"
      :pass="justCreatedPass"
      @issue-next="handleResetIssue"
      @view-roster="emit('viewRoster')"
    />

    <!-- 场景 B：常规录入表单 -->
    <form v-else class="issue-form" @submit.prevent="handleCreate">
      <div class="form-group">
        <label for="modal-guest-name-input" class="form-label"> 访客名称 / 备注 </label>
        <input
          id="modal-guest-name-input"
          ref="inputRef"
          v-model="newUsername"
          type="text"
          class="form-input"
          placeholder="如：好友xx / 客厅 iPad"
          maxlength="32"
          required
        />
        <p class="field-hint">登记访客专属名称，生成后可一键复制免密直达链接发给朋友。</p>
      </div>

      <div class="form-group">
        <label class="form-label">有效期限</label>
        <div class="days-selector" role="radiogroup" aria-label="有效期限选择">
          <button
            v-for="opt in dayOptions"
            :key="String(opt.value)"
            type="button"
            class="day-pill"
            :class="{ active: selectedDays === opt.value }"
            :aria-checked="selectedDays === opt.value"
            role="radio"
            @click="selectedDays = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>

      <div class="form-group">
        <label class="form-label">允许同时登入设备数（席位）</label>
        <div class="days-selector" role="radiogroup" aria-label="设备席位配额选择">
          <button
            v-for="opt in deviceOptions"
            :key="opt.value"
            type="button"
            class="day-pill"
            :class="{ active: selectedMaxDevices === opt.value }"
            :aria-checked="selectedMaxDevices === opt.value"
            role="radio"
            @click="selectedMaxDevices = opt.value"
          >
            {{ opt.label }}
          </button>
        </div>
        <p class="field-hint">
          允许同时授权的物理设备上限。超出时自动置换挤出最久未活跃设备，防止口令群发扩散。
        </p>
      </div>

      <AppButton
        type="submit"
        variant="primary"
        size="md"
        class="issue-submit-btn"
        :loading="creating"
        :disabled="!newUsername.trim()"
      >
        <AppIcon name="plus" size="sm" />
        <span>登记并印发通行证</span>
      </AppButton>
    </form>
  </section>
</template>

<style scoped>
.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* 登记印发表单 */
.issue-form {
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-group {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-label {
  font-size: var(--text-caption);
  font-weight: 600;
  color: var(--ink-1);
}

.form-input {
  width: 100%;
  min-height: 44px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
  background: var(--paper-0);
  font-size: var(--text-body);
  color: var(--ink-0);
  outline: none;
  transition: border-color var(--duration-1) var(--ease-out);
}

.form-input:focus {
  border-color: var(--accent);
}

.field-hint {
  margin: 0;
  font-size: var(--text-caption);
  color: var(--ink-2);
  line-height: 1.4;
}

.days-selector {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.day-pill {
  min-height: 40px;
  padding: 0 var(--space-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
  background: var(--paper-0);
  font-size: var(--text-caption);
  color: var(--ink-1);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.day-pill:hover {
  border-color: var(--accent);
  color: var(--ink-0);
}

.day-pill.active {
  background: var(--accent);
  border-color: var(--accent);
  color: var(--paper-0);
  font-weight: 600;
}

.issue-submit-btn {
  width: 100%;
  min-height: 44px;
  margin-top: var(--space-2);
}
</style>
