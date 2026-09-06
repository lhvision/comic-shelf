<script setup lang="ts">
/**
 * @file GuestCard.vue
 * @description 访客通行证单卡组件。
 *
 * 核心功能：
 * - 呈现访客身份、创建时间、四态典藏印章及异常告警（争抢锁定/速率受限）；
 * - 一键复制免密直达链接 / 授权口令（带 1.5s VueUse `refAutoReset` 成功反馈）；
 * - 物理设备抽屉与设备席位配额步进器（1~5 台）；
 * - 顺延续期（+30天）、重置密钥与注销名册（带 4s VueUse `refAutoReset` 防误触确认）。
 */

import { refAutoReset } from '@vueuse/core'
import AppIcon from '@/components/AppIcon.vue'
import GuestDeviceList from './GuestDeviceList.vue'
import { formatTimestamp, maskToken } from './guestUtils'
import { useGuestPasses } from '@/composables/useGuestPasses'
import type { GuestPass } from '@/types'

const props = defineProps<{
  /** 通行证数据实体 */
  item: GuestPass
}>()

const {
  operatingId,
  renewPass,
  resetToken,
  resetPin,
  toggleActive,
  removePass,
  removeDevice,
  updateMaxDevices,
  copyToken,
  copyShareLink,
} = useGuestPasses()

/** 直达链接复制成功微反馈（1.5s 后自动归位） */
const copiedLink = refAutoReset(false, 1500)
/** 口令复制成功微反馈（1.5s 后自动归位） */
const copiedToken = refAutoReset(false, 1500)
/** 重置密钥二次确认弹层状态（4s 未操作自动归位） */
const isConfirmingReset = refAutoReset(false, 4000)
/** 清空 PIN 码二次确认弹层状态（4s 未操作自动归位） */
const isConfirmingResetPin = refAutoReset(false, 4000)
/** 注销通行证二次确认弹层状态（4s 未操作自动归位） */
const isConfirmingDelete = refAutoReset(false, 4000)

/** 处理复制免密直达链接 */
async function handleCopyLink() {
  const ok = await copyShareLink(props.item)
  if (ok) copiedLink.value = true
}

/** 处理复制授权口令 */
async function handleCopyToken() {
  const ok = await copyToken(props.item)
  if (ok) copiedToken.value = true
}

/** 移除单台已授权设备 */
function handleRemoveDevice(passId: number, deviceId: number) {
  void removeDevice(passId, deviceId)
}

/** 确认重置密钥（换发新 Token 并踢出旧设备） */
function handleResetToken() {
  void resetToken(props.item.id)
  isConfirmingReset.value = false
}

/** 确认清空自设 PIN 码并恢复待认领 */
function handleResetPin() {
  void resetPin(props.item.id)
  isConfirmingResetPin.value = false
}

/** 确认从名册中注销该通行证 */
function handleRemovePass() {
  void removePass(props.item.id)
  isConfirmingDelete.value = false
}
</script>

<template>
  <li
    class="pass-card"
    :class="{
      disabled: item.activation_status === 'disabled',
      expired: item.activation_status === 'expired',
      pending: item.activation_status === 'pending',
      full: item.activation_status === 'full',
    }"
  >
    <div class="pass-card-top">
      <div class="pass-identity">
        <strong class="pass-name">{{ item.username }}</strong>
        <span class="pass-date">{{ formatTimestamp(item.created_at) }} 印发</span>
      </div>

      <!-- 典藏印章（支持展示争抢锁定与速率受限异常印章） -->
      <div
        class="status-seal"
        :class="[
          item.is_cooling_locked
            ? 'cooling-locked'
            : item.is_rate_limited
              ? 'rate-limited'
              : !item.is_claimed
                ? 'pending'
                : item.activation_status,
        ]"
      >
        <span v-if="item.is_cooling_locked">〔 ⚠️ 争抢锁定 〕</span>
        <span v-else-if="item.is_rate_limited">〔 ⚠️ 速率受限 〕</span>
        <span v-else-if="item.activation_status === 'disabled'">〔 已停用 〕</span>
        <span v-else-if="item.activation_status === 'expired'">〔 已过期 〕</span>
        <span v-else-if="!item.is_claimed">〔 🌿 待认领 (未设 PIN) 〕</span>
        <span v-else-if="item.activation_status === 'full'">
          〔 满额 · {{ item.device_count }}/{{ item.max_devices }}台 〕
        </span>
        <span v-else>〔 🍃 活跃 · {{ item.device_count }}/{{ item.max_devices }}台 〕</span>
      </div>
    </div>

    <!-- 核心高频动作区（主次分明，带就地微反馈） -->
    <div class="hero-actions">
      <button
        type="button"
        class="hero-btn primary"
        :class="{ copied: copiedLink }"
        :title="`复制「${item.username}」免密直达专属链接`"
        @click="handleCopyLink"
      >
        <AppIcon :name="copiedLink ? 'check' : 'external-link'" size="sm" />
        <span>{{ copiedLink ? '已复制专属直达链接' : '复制专属直达链接' }}</span>
      </button>

      <button
        type="button"
        class="hero-btn secondary"
        :class="{ copied: copiedToken }"
        :title="`复制通行口令：${item.token}`"
        @click="handleCopyToken"
      >
        <AppIcon :name="copiedToken ? 'check' : 'copy'" size="sm" />
        <span>{{ copiedToken ? '已复制口令' : `口令：${maskToken(item.token)}` }}</span>
      </button>
    </div>

    <!-- 物理设备与会话托盘 -->
    <div class="device-tray">
      <!-- 异常告警条（频发争抢锁定 / 速率超标） -->
      <div v-if="item.is_cooling_locked" class="device-abuse-alert lock">
        <AppIcon name="info" size="xs" />
        <span>
          该通行证近期频繁发生设备挤出置换，已启动 10
          分钟争抢保护锁定。当前在册设备正常使用，新设备暂无法接入。若怀疑口令外泄，建议点击底栏「重置密钥」立即将所有设备下线。
        </span>
      </div>
      <div v-else-if="item.is_rate_limited" class="device-abuse-alert rate">
        <AppIcon name="info" size="xs" />
        <span>检测到高频翻页/下载图片请求（>180页/分钟），已触发轻量限流保护。</span>
      </div>

      <div class="device-tray-head">
        <div class="device-tray-title">
          <AppIcon name="users" size="xs" />
          <span>授权设备（{{ item.device_count }} / {{ item.max_devices }}）</span>
        </div>
        <span v-if="item.activation_status === 'pending'" class="device-tray-status pending">
          尚未绑定任何设备（可安全转赠/分发）
        </span>
        <span v-else-if="item.activation_status === 'full'" class="device-tray-status full">
          席位已满，新端登入将按 LRU 置换最旧端
        </span>
        <span v-else class="device-tray-status active">
          已绑定 {{ item.device_count }} 台设备
        </span>
      </div>

      <!-- 设备名册列表子组件 -->
      <GuestDeviceList
        :devices="item.devices"
        :pass-id="item.id"
        :operating-id="operatingId"
        @remove-device="handleRemoveDevice"
      />
    </div>

    <!-- 辅助信息与次要管理工具栏 -->
    <div class="card-footer">
      <div class="expiry-info">
        <span class="expiry-label">有效期至：</span>
        <span class="expiry-val">{{ formatTimestamp(item.expires_at) }}</span>
      </div>

      <div class="sub-toolbar">
        <!-- 席位配额调节 -->
        <div
          class="quota-stepper"
          role="group"
          :aria-label="`访客「${item.username}」的设备席位上限`"
          title="调整允许同时绑定的设备数（1~5台）"
        >
          <span class="quota-label">席位:</span>
          <button
            type="button"
            class="quota-step-btn"
            :disabled="item.max_devices <= 1 || operatingId !== null"
            aria-label="减少设备配额"
            @click="updateMaxDevices(item.id, item.max_devices - 1)"
          >
            <AppIcon name="minus" size="xs" />
          </button>
          <span class="quota-val">{{ item.max_devices }}</span>
          <button
            type="button"
            class="quota-step-btn"
            :disabled="item.max_devices >= 5 || operatingId !== null"
            aria-label="增加设备配额"
            @click="updateMaxDevices(item.id, item.max_devices + 1)"
          >
            <AppIcon name="plus" size="xs" />
          </button>
        </div>

        <button
          type="button"
          class="sub-tool-btn"
          title="顺延续期 30 天"
          :disabled="operatingId !== null"
          @click="renewPass(item.id, 30)"
        >
          <span>+30天</span>
        </button>

        <!-- 重置密钥 -->
        <div class="confirm-wrapper">
          <button
            v-if="!isConfirmingReset"
            type="button"
            class="sub-tool-btn"
            title="换新密钥（旧口令即刻失效）"
            :disabled="operatingId !== null"
            @click="isConfirmingReset = true"
          >
            <span>重置</span>
          </button>
          <div v-else class="confirm-pop">
            <span class="confirm-text">换新密钥？</span>
            <button
              type="button"
              class="confirm-act confirm-yes"
              :disabled="operatingId !== null"
              @click="handleResetToken"
            >
              确定
            </button>
            <button type="button" class="confirm-act confirm-no" @click="isConfirmingReset = false">
              取消
            </button>
          </div>
        </div>

        <!-- 清空 PIN 码 -->
        <div v-if="item.is_claimed" class="confirm-wrapper">
          <button
            v-if="!isConfirmingResetPin"
            type="button"
            class="sub-tool-btn"
            title="清空读者自设 PIN 码并恢复为待认领"
            :disabled="operatingId !== null"
            @click="isConfirmingResetPin = true"
          >
            <span>清空PIN</span>
          </button>
          <div v-else class="confirm-pop">
            <span class="confirm-text">清空PIN？</span>
            <button
              type="button"
              class="confirm-act confirm-yes"
              :disabled="operatingId !== null"
              @click="handleResetPin"
            >
              确定
            </button>
            <button
              type="button"
              class="confirm-act confirm-no"
              @click="isConfirmingResetPin = false"
            >
              取消
            </button>
          </div>
        </div>

        <!-- 停用/启用 -->
        <button
          type="button"
          class="sub-tool-btn"
          :class="{ warning: item.is_active }"
          :title="item.is_active ? '暂时停用该访客通行权限' : '恢复该访客通行权限'"
          :disabled="operatingId !== null"
          @click="toggleActive(item.id, !item.is_active)"
        >
          <span>{{ item.is_active ? '停用' : '启用' }}</span>
        </button>

        <!-- 注销 -->
        <div class="confirm-wrapper">
          <button
            v-if="!isConfirmingDelete"
            type="button"
            class="sub-tool-btn danger"
            title="从名册中彻底注销该访客"
            :disabled="operatingId !== null"
            @click="isConfirmingDelete = true"
          >
            <span>注销</span>
          </button>
          <div v-else class="confirm-pop">
            <span class="confirm-text">彻底注销？</span>
            <button
              type="button"
              class="confirm-act confirm-yes danger"
              :disabled="operatingId !== null"
              @click="handleRemovePass"
            >
              删除
            </button>
            <button
              type="button"
              class="confirm-act confirm-no"
              @click="isConfirmingDelete = false"
            >
              取消
            </button>
          </div>
        </div>
      </div>
    </div>
  </li>
</template>

<style scoped>
.pass-card {
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  box-shadow: var(--shadow-1);
  transition: border-color var(--duration-1) var(--ease-out);
}

.pass-card:hover {
  border-color: color-mix(in oklab, var(--ink-2) 40%, var(--line));
}

.pass-card.disabled {
  opacity: 0.7;
  background: var(--paper-1);
}

.pass-card.expired {
  border-color: color-mix(in oklab, var(--ink-2) 30%, var(--line));
}

.pass-card-top {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-3);
}

.pass-identity {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.pass-name {
  font-size: var(--text-body);
  font-weight: 700;
  color: var(--ink-0);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.pass-date {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--ink-2);
}

/* 典藏印章（四态流转） */
.status-seal {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-1);
  border: 1px solid transparent;
}

.status-seal.pending {
  color: var(--ink-1);
  background: var(--paper-1);
  border-color: color-mix(in oklab, var(--ink-2) 35%, var(--line));
}

.status-seal.active {
  color: var(--success, #2e7d32);
  background: color-mix(in oklab, var(--success, #2e7d32) 10%, var(--paper-0));
  border-color: color-mix(in oklab, var(--success, #2e7d32) 30%, transparent);
}

.status-seal.full {
  color: var(--warning, #b45309);
  background: color-mix(in oklab, var(--warning, #b45309) 10%, var(--paper-0));
  border-color: color-mix(in oklab, var(--warning, #b45309) 35%, transparent);
}

.status-seal.cooling-locked {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: color-mix(in oklab, var(--accent) 40%, transparent);
  font-weight: 600;
}

.status-seal.rate-limited {
  color: var(--warning, #b45309);
  background: color-mix(in oklab, var(--warning, #b45309) 12%, var(--paper-0));
  border-color: color-mix(in oklab, var(--warning, #b45309) 40%, transparent);
  font-weight: 600;
}

.status-seal.expired {
  color: var(--ink-2);
  background: var(--paper-1);
  border-color: var(--line);
}

.status-seal.disabled {
  color: var(--ink-2);
  background: var(--paper-2);
  border-color: var(--line);
}

.device-abuse-alert {
  display: flex;
  align-items: flex-start;
  gap: var(--space-1-5);
  padding: var(--space-2) var(--space-2-5);
  margin-bottom: var(--space-2-5);
  border-radius: var(--radius-1);
  font-size: var(--text-xs);
  line-height: 1.4;
}

.device-abuse-alert.lock {
  color: var(--accent);
  background: color-mix(in oklab, var(--accent) 8%, var(--paper-0));
  border: 1px solid color-mix(in oklab, var(--accent) 30%, transparent);
}

.device-abuse-alert.rate {
  color: var(--warning, #b45309);
  background: color-mix(in oklab, var(--warning, #b45309) 8%, var(--paper-0));
  border: 1px solid color-mix(in oklab, var(--warning, #b45309) 30%, transparent);
}

/* 核心高频动作区 */
.hero-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.hero-btn {
  width: 100%;
  min-height: 42px;
  padding: 0 var(--space-3);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  border-radius: var(--radius-1);
  font-size: var(--text-caption);
  cursor: pointer;
  transition: all var(--duration-2) var(--ease-out);
}

.hero-btn.primary {
  background: color-mix(in oklab, var(--accent) 10%, var(--paper-0));
  border: 1px solid color-mix(in oklab, var(--accent) 30%, var(--line));
  color: var(--accent);
  font-weight: 600;
}

.hero-btn.primary:hover {
  background: var(--accent);
  color: var(--paper-0);
  border-color: var(--accent);
}

.hero-btn.secondary {
  background: var(--paper-1);
  border: 1px dashed var(--line);
  color: var(--ink-1);
  font-family: var(--font-mono);
}

.hero-btn.secondary:hover {
  border-color: var(--ink-0);
  color: var(--ink-0);
}

/* 复制成功后的 success 微状态（1.5s 后平滑恢复） */
.hero-btn.copied {
  border-color: color-mix(in oklab, var(--success) 45%, transparent) !important;
  background: color-mix(in oklab, var(--success) 8%, var(--paper-0)) !important;
  color: var(--success) !important;
  border-style: solid !important;
  font-weight: 600;
}

.hero-btn.copied:hover {
  border-color: color-mix(in oklab, var(--success) 60%, transparent) !important;
  background: color-mix(in oklab, var(--success) 14%, var(--paper-0)) !important;
  color: var(--success) !important;
}

/* 物理设备与会话托盘 */
.device-tray {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  padding: var(--space-2) var(--space-3);
}

.device-tray-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  font-size: var(--text-caption);
  color: var(--ink-1);
}

.device-tray-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-weight: 600;
  color: var(--ink-0);
}

.device-tray-status {
  font-size: var(--text-xs);
}

.device-tray-status.pending {
  color: var(--ink-2);
}

.device-tray-status.full {
  color: var(--accent);
  font-weight: 500;
}

.device-tray-status.active {
  color: var(--success, #2e7d32);
}

/* 卡片底栏 */
.card-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: var(--space-2);
  padding-top: var(--space-2);
  border-top: 1px solid var(--line);
}

.expiry-info {
  display: flex;
  align-items: center;
  gap: 2px;
  font-size: var(--text-caption);
}

.expiry-label {
  color: var(--ink-2);
}

.expiry-val {
  font-family: var(--font-mono);
  color: var(--ink-1);
}

.sub-toolbar {
  display: flex;
  align-items: center;
  gap: var(--space-1-5);
}

/* 席位配额微调 */
.quota-stepper {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  padding: 0 4px;
  min-height: 36px;
  background: var(--paper-0);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  font-size: var(--text-caption);
}

.quota-label {
  color: var(--ink-2);
  font-size: 11px;
  padding-left: 2px;
}

.quota-val {
  font-family: var(--font-mono);
  font-weight: 600;
  color: var(--ink-0);
  padding: 0 4px;
  font-size: 12px;
}

.quota-step-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: 2px;
  color: var(--ink-1);
  cursor: pointer;
  padding: 0;
  transition: all var(--duration-1) var(--ease-out);
}

/* WCAG 触控热区扩展至 36px */
.quota-step-btn::before {
  content: '';
  position: absolute;
  top: -7px;
  bottom: -7px;
  left: -7px;
  right: -7px;
}

.quota-step-btn:hover:not(:disabled) {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--paper-0);
}

.quota-step-btn:disabled {
  opacity: 0.35;
  cursor: not-allowed;
}

.sub-tool-btn {
  min-height: 36px;
  padding: 0 var(--space-2);
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
  background: var(--paper-0);
  font-size: var(--text-caption);
  color: var(--ink-1);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.sub-tool-btn:hover:not(:disabled) {
  border-color: var(--ink-0);
  color: var(--ink-0);
}

.sub-tool-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sub-tool-btn.warning:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

.sub-tool-btn.danger:hover:not(:disabled) {
  border-color: var(--accent);
  color: var(--accent);
}

/* 二次确认浮层 */
.confirm-wrapper {
  display: inline-flex;
}

.confirm-pop {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 2px 6px;
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
}

.confirm-text {
  font-size: var(--text-caption);
  color: var(--ink-1);
}

.confirm-act {
  min-height: 32px;
  padding: 0 var(--space-2);
  font-size: var(--text-caption);
  border-radius: var(--radius-1);
  border: none;
  cursor: pointer;
}

.confirm-act.confirm-yes {
  background: var(--ink-0);
  color: var(--paper-0);
}

.confirm-act.confirm-yes.danger {
  background: var(--accent);
  color: var(--paper-0);
}

.confirm-act.confirm-no {
  background: transparent;
  color: var(--ink-2);
}

@media (max-width: 640px) {
  .card-footer {
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-2);
  }

  .sub-toolbar {
    width: 100%;
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }

  .quota-stepper {
    margin-right: auto;
  }

  .sub-tool-btn {
    min-height: 36px;
    padding: 0 var(--space-2-5);
  }
}
</style>
