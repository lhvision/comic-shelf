<script setup lang="ts">
/**
 * @file GuestDeviceList.vue
 * @description 访客授权设备抽屉列表组件。
 *
 * 核心功能：
 * - 呈现已绑定物理设备名称、最近活跃时间及 IP；
 * - 提供单设备下线踢出按钮，配合 VueUse `refAutoReset` 实现 4 秒自动重置的防误触二次确认。
 */

import { refAutoReset } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import { formatRelativeTime } from './guestUtils'
import type { GuestDevice } from '@/types'

const props = defineProps<{
  /** 绑定的物理设备列表 */
  devices?: GuestDevice[]
  /** 所属通行证 ID */
  passId: number
  /** 当前正在异步操作中的通行证 ID（用于全局 loading 互斥锁定） */
  operatingId: number | null
}>()

const emit = defineEmits<{
  /** 触发移除指定设备请求 */
  removeDevice: [passId: number, deviceId: number]
}>()

/** 局部防误触二次确认：记录待踢出的设备 ID，4 秒未确认自动重置为 null */
const confirmKickDeviceId = refAutoReset<number | null>(null, 4000)

/** 唤起下线确认状态 */
function requestKick(deviceId: number) {
  confirmKickDeviceId.value = deviceId
}

/** 取消下线 */
function cancelKick() {
  confirmKickDeviceId.value = null
}

/** 确认踢出设备并派发事件 */
function confirmKick(deviceId: number) {
  emit('removeDevice', props.passId, deviceId)
  confirmKickDeviceId.value = null
}
</script>

<template>
  <ul v-if="devices && devices.length > 0" class="device-chip-list">
    <li v-for="dev in devices" :key="dev.id" class="device-chip">
      <div class="device-chip-meta">
        <span class="device-name">{{ dev.device_name }}</span>
        <span class="device-time">活跃于 {{ formatRelativeTime(dev.last_active_at) }}</span>
        <span v-if="dev.last_ip" class="device-ip">{{ dev.last_ip }}</span>
      </div>

      <!-- 单设备踢除二次确认防误触 -->
      <div class="device-kick-wrapper">
        <template v-if="confirmKickDeviceId === dev.id">
          <span class="device-kick-confirm-text">下线？</span>
          <button
            type="button"
            class="device-kick-action confirm-yes"
            :disabled="operatingId !== null"
            @click="confirmKick(dev.id)"
          >
            踢出
          </button>
          <button type="button" class="device-kick-action confirm-no" @click="cancelKick">
            取消
          </button>
        </template>
        <button
          v-else
          type="button"
          class="device-kick-btn"
          :title="`将设备「${dev.device_name}」踢下线`"
          :aria-label="`将设备「${dev.device_name}」踢下线`"
          :disabled="operatingId !== null"
          @click="requestKick(dev.id)"
        >
          <AppIcon name="close" size="xs" />
        </button>
      </div>
    </li>
  </ul>
</template>

<style scoped>
.device-chip-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.device-chip {
  display: flex;
  align-items: center;
  justify-content: space-between;
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  padding: 4px 8px;
  gap: var(--space-2);
}

.device-chip-meta {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  min-width: 0;
}

.device-name {
  font-weight: 600;
  font-size: var(--text-xs);
  color: var(--ink-0);
}

.device-time {
  font-size: 11px;
  color: var(--ink-2);
}

.device-ip {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--ink-2);
  padding: 1px 4px;
  background: var(--paper-2);
  border-radius: 2px;
}

.device-kick-wrapper {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.device-kick-confirm-text {
  font-size: 11px;
  color: var(--accent);
  font-weight: 600;
}

.device-kick-action {
  font-size: 11px;
  padding: 2px 6px;
  min-height: 24px;
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
  background: var(--paper-1);
  color: var(--ink-1);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.device-kick-action.confirm-yes {
  background: var(--accent-soft);
  border-color: color-mix(in oklab, var(--accent) 40%, transparent);
  color: var(--accent);
  font-weight: 600;
}

.device-kick-action.confirm-no {
  background: var(--paper-0);
  color: var(--ink-2);
}

.device-kick-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-1);
  border: 1px solid transparent;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
  flex-shrink: 0;
}

/* WCAG 触控热区扩展至 40px */
.device-kick-btn::before {
  content: '';
  position: absolute;
  top: -8px;
  bottom: -8px;
  left: -8px;
  right: -8px;
}

.device-kick-btn:hover:not(:disabled) {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: color-mix(in oklab, var(--accent) 30%, transparent);
}

.device-kick-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}
</style>
