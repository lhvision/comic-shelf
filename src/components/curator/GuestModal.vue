<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue'
import Modal from '@/components/Modal.vue'
import SegmentedTabs from '@/components/SegmentedTabs.vue'
import Tooltip from '@/components/Tooltip.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'
import { useGuestPasses } from '@/composables/useGuestPasses'
import type { TabItem } from '@/components/SegmentedTabs.vue'
import type { GuestPass } from '@/types'

const {
  passes,
  loading,
  operatingId,
  fetchError,
  modalVisible,
  fetchPasses,
  createPass,
  renewPass,
  resetToken,
  toggleActive,
  removePass,
  removeDevice,
  updateMaxDevices,
  copyToken,
  copyShareLink,
  closeModal,
} = useGuestPasses()

type TabKey = 'roster' | 'issue'
type FilterKey = 'all' | 'pending' | 'active' | 'full' | 'disabled'

const activeTab = ref<TabKey>('roster')
const currentFilter = ref<FilterKey>('all')
const newUsername = ref('')
const selectedDays = ref<number | null>(30)
const selectedMaxDevices = ref(2)
const creating = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

// 刚印发成功的凭证对象（原地展示，杜绝粗暴跳页截断心流）
const justCreatedPass = ref<GuestPass | null>(null)

// 局部内联确认与状态反馈
const confirmResetId = ref<number | null>(null)
const confirmDeleteId = ref<number | null>(null)
const confirmKickDeviceId = ref<number | null>(null)
const copiedLinkId = ref<number | null>(null)
const copiedTokenId = ref<number | null>(null)
const searchQuery = ref('')

const tabs = computed<TabItem<TabKey>[]>(() => [
  { key: 'roster', label: '现存名册', sub: String(passes.value.length) },
  { key: 'issue', label: '登记印发' },
])

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

const pendingCount = computed(
  () => passes.value.filter((p) => p.activation_status === 'pending').length,
)
const activeCount = computed(
  () => passes.value.filter((p) => p.activation_status === 'active').length,
)
const fullCount = computed(() => passes.value.filter((p) => p.activation_status === 'full').length)
const disabledCount = computed(
  () =>
    passes.value.filter(
      (p) => p.activation_status === 'disabled' || p.activation_status === 'expired',
    ).length,
)

const filterTabs = computed(() => [
  { key: 'all' as const, label: '全部', count: passes.value.length },
  { key: 'pending' as const, label: '待激活', count: pendingCount.value },
  { key: 'active' as const, label: '使用中', count: activeCount.value },
  { key: 'full' as const, label: '已满额', count: fullCount.value },
  { key: 'disabled' as const, label: '已失效', count: disabledCount.value },
])

const filteredPasses = computed(() => {
  let list = passes.value
  if (currentFilter.value === 'pending') {
    list = list.filter((p) => p.activation_status === 'pending')
  } else if (currentFilter.value === 'active') {
    list = list.filter((p) => p.activation_status === 'active')
  } else if (currentFilter.value === 'full') {
    list = list.filter((p) => p.activation_status === 'full')
  } else if (currentFilter.value === 'disabled') {
    list = list.filter(
      (p) => p.activation_status === 'disabled' || p.activation_status === 'expired',
    )
  }

  const query = searchQuery.value.trim().toLowerCase()
  if (query) {
    list = list.filter((p) => p.username.toLowerCase().includes(query))
  }

  return list
})

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
      // 原位升格为印发成功凭据卡，不粗暴踢回名册
      justCreatedPass.value = created
    }
  } finally {
    creating.value = false
  }
}

function resetIssueForm() {
  justCreatedPass.value = null
  newUsername.value = ''
  selectedMaxDevices.value = 2
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function goToRoster() {
  justCreatedPass.value = null
  activeTab.value = 'roster'
}

async function handleCopyLink(item: GuestPass) {
  const ok = await copyShareLink(item)
  if (ok) {
    copiedLinkId.value = item.id
    setTimeout(() => {
      if (copiedLinkId.value === item.id) {
        copiedLinkId.value = null
      }
    }, 1500)
  }
}

async function handleCopyToken(item: GuestPass) {
  const ok = await copyToken(item)
  if (ok) {
    copiedTokenId.value = item.id
    setTimeout(() => {
      if (copiedTokenId.value === item.id) {
        copiedTokenId.value = null
      }
    }, 1500)
  }
}

async function handleRemoveDevice(passId: number, deviceId: number) {
  await removeDevice(passId, deviceId)
}

function formatTimestamp(ts: number | null): string {
  if (!ts) return '永久有效'
  const date = new Date(ts * 1000)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
}

function formatRelativeTime(ts: number | null): string {
  if (!ts) return '从未'
  const now = Math.floor(Date.now() / 1000)
  const diff = now - ts
  if (diff < 60) return '刚刚'
  if (diff < 3600) return `${Math.floor(diff / 60)} 分钟前`
  if (diff < 86400) return `${Math.floor(diff / 3600)} 小时前`
  const days = Math.floor(diff / 86400)
  if (days < 30) return `${days} 天前`
  return formatTimestamp(ts)
}

function getDaysRemaining(expiresAt: number | null): string {
  if (!expiresAt) return '永久准入'
  const now = Math.floor(Date.now() / 1000)
  const diff = expiresAt - now
  if (diff <= 0) return '已过期'
  const days = Math.ceil(diff / 86400)
  return `准入 · 剩 ${days} 天`
}

function maskToken(token: string): string {
  if (!token || token.length < 12) return token
  return `${token.slice(0, 6)}••••${token.slice(-6)}`
}

watch(modalVisible, (visible) => {
  if (visible) {
    confirmResetId.value = null
    confirmDeleteId.value = null
    confirmKickDeviceId.value = null
    copiedLinkId.value = null
    copiedTokenId.value = null
    justCreatedPass.value = null
    currentFilter.value = 'all'
    searchQuery.value = ''
    if (passes.value.length === 0) {
      activeTab.value = 'roster'
    }
  }
})

watch(activeTab, async (tab) => {
  if (tab === 'issue' && !justCreatedPass.value) {
    await nextTick()
    inputRef.value?.focus()
  }
})
</script>

<template>
  <Modal :open="modalVisible" title="纸间 · 访客簿" @cancel="closeModal">
    <template #title>
      <div class="guest-modal-title">
        <span>纸间 · 访客簿</span>
        <Tooltip
          tip="派发专属访问通行证，阅读进度与收藏红心相互隔离。"
          side="right"
          align="center"
          width="16rem"
        >
          <button type="button" class="title-info-btn" aria-label="查看权限隔离说明">
            <AppIcon name="info" size="xs" />
          </button>
        </Tooltip>
      </div>
    </template>

    <div class="guest-modal-container">
      <!-- 分段标签页导航 -->
      <div class="tabs-nav-bar">
        <SegmentedTabs
          v-model="activeTab"
          :items="tabs"
          size="md"
          :full-width="true"
          aria-label="访客簿功能切换"
        />
      </div>

      <!-- 选项卡 1：现存名册 -->
      <section
        v-if="activeTab === 'roster'"
        id="tabpanel-roster"
        class="tab-content roster-pane"
        role="tabpanel"
        aria-label="现存名册列表"
      >
        <div class="roster-toolbar">
          <div class="roster-summary">
            <span class="roster-tip">共登记 {{ passes.length }} 位访客</span>
          </div>
          <div class="roster-toolbar-right">
            <div v-if="passes.length > 2" class="roster-search-box">
              <AppIcon name="search" size="xs" class="search-icon" />
              <input
                v-model="searchQuery"
                type="search"
                class="roster-search-input"
                placeholder="搜索访客..."
                aria-label="搜索访客名称"
              />
            </div>
            <button
              type="button"
              class="refresh-btn"
              title="重新获取最新名册数据"
              :disabled="loading"
              @click="fetchPasses"
            >
              <AppIcon name="refresh" size="xs" :class="{ 'spin-icon': loading }" />
              <span>刷新</span>
            </button>
          </div>
        </div>

        <!-- 状态快捷筛选胶囊 -->
        <div
          v-if="passes.length > 0"
          class="filter-bar"
          role="radiogroup"
          aria-label="名册激活状态筛选"
        >
          <button
            v-for="flt in filterTabs"
            :key="flt.key"
            type="button"
            class="filter-tab-btn"
            :class="{ active: currentFilter === flt.key }"
            :aria-checked="currentFilter === flt.key"
            role="radio"
            @click="currentFilter = flt.key"
          >
            <span>{{ flt.label }}</span>
            <span class="filter-badge">{{ flt.count }}</span>
          </button>
        </div>

        <!-- 加载中 -->
        <div v-if="loading && passes.length === 0" class="state-panel">
          <AppIcon name="refresh" size="lg" class="spin-icon" />
          <p>正在翻阅名册…</p>
        </div>

        <!-- 接口异常 -->
        <div v-else-if="fetchError && passes.length === 0" class="state-panel error">
          <AppIcon name="info" size="lg" />
          <p class="state-msg">{{ fetchError }}</p>
          <button type="button" class="retry-btn" @click="fetchPasses">重新翻阅名册</button>
        </div>

        <!-- 暂无名册（无数据） -->
        <div v-else-if="passes.length === 0" class="state-panel empty">
          <div class="empty-seal">暂无访客</div>
          <p class="empty-hint">尚未印发任何通行证，点击下方按钮即可派发。</p>
          <AppButton variant="primary" size="md" @click="activeTab = 'issue'">
            <AppIcon name="plus" size="sm" />
            <span>登记第一张通行证</span>
          </AppButton>
        </div>

        <!-- 筛选无结果 -->
        <div v-else-if="filteredPasses.length === 0" class="state-panel empty">
          <div class="empty-seal">无匹配通行证</div>
          <p class="empty-hint">当前筛选或搜索条件下暂无访客卡片。</p>
          <AppButton
            variant="secondary"
            size="sm"
            @click="
              () => {
                currentFilter = 'all'
                searchQuery = ''
              }
            "
          >
            <span>重置筛选并查看全部 {{ passes.length }} 位访客</span>
          </AppButton>
        </div>

        <!-- 借书卡名册卡片列表 -->
        <ul v-else class="pass-card-list">
          <li
            v-for="item in filteredPasses"
            :key="item.id"
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
                      : item.activation_status,
                ]"
              >
                <span v-if="item.is_cooling_locked">〔 ⚠️ 争抢锁定 〕</span>
                <span v-else-if="item.is_rate_limited">〔 ⚠️ 速率受限 〕</span>
                <span v-else-if="item.activation_status === 'disabled'">〔 已停用 〕</span>
                <span v-else-if="item.activation_status === 'expired'">〔 已过期 〕</span>
                <span v-else-if="item.activation_status === 'pending'">〔 待激活 · 0台占用 〕</span>
                <span v-else-if="item.activation_status === 'full'"
                  >〔 满额 · {{ item.device_count }}/{{ item.max_devices }}台 〕</span
                >
                <span v-else>〔 活跃 · {{ item.device_count }}/{{ item.max_devices }}台 〕</span>
              </div>
            </div>

            <!-- 核心高频动作区（主次分明，带就地微反馈） -->
            <div class="hero-actions">
              <button
                type="button"
                class="hero-btn primary"
                :class="{ copied: copiedLinkId === item.id }"
                :title="`复制「${item.username}」免密直达专属链接`"
                @click="handleCopyLink(item)"
              >
                <AppIcon :name="copiedLinkId === item.id ? 'check' : 'external-link'" size="sm" />
                <span>{{
                  copiedLinkId === item.id ? '已复制专属直达链接' : '复制专属直达链接'
                }}</span>
              </button>

              <button
                type="button"
                class="hero-btn secondary"
                :class="{ copied: copiedTokenId === item.id }"
                :title="`复制通行口令：${item.token}`"
                @click="handleCopyToken(item)"
              >
                <AppIcon :name="copiedTokenId === item.id ? 'check' : 'copy'" size="sm" />
                <span>{{
                  copiedTokenId === item.id ? '已复制口令' : `口令：${maskToken(item.token)}`
                }}</span>
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
                <span>检测到高频翻页/下载图片请求（>120页/分钟），已触发轻量限流保护。</span>
              </div>

              <div class="device-tray-head">
                <div class="device-tray-title">
                  <AppIcon name="users" size="xs" />
                  <span>授权设备（{{ item.device_count }} / {{ item.max_devices }}）</span>
                </div>
                <span
                  v-if="item.activation_status === 'pending'"
                  class="device-tray-status pending"
                >
                  尚未绑定任何设备（可安全转赠/分发）
                </span>
                <span v-else-if="item.activation_status === 'full'" class="device-tray-status full">
                  席位已满，新端登入将按 LRU 置换最旧端
                </span>
                <span v-else class="device-tray-status active">
                  已绑定 {{ item.device_count }} 台设备
                </span>
              </div>

              <!-- 设备名册列表 -->
              <ul v-if="item.devices && item.devices.length > 0" class="device-chip-list">
                <li v-for="dev in item.devices" :key="dev.id" class="device-chip">
                  <div class="device-chip-meta">
                    <span class="device-name">{{ dev.device_name }}</span>
                    <span class="device-time"
                      >活跃于 {{ formatRelativeTime(dev.last_active_at) }}</span
                    >
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
                        @click="
                          () => {
                            handleRemoveDevice(item.id, dev.id)
                            confirmKickDeviceId = null
                          }
                        "
                      >
                        踢出
                      </button>
                      <button
                        type="button"
                        class="device-kick-action confirm-no"
                        @click="confirmKickDeviceId = null"
                      >
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
                      @click="confirmKickDeviceId = dev.id"
                    >
                      <AppIcon name="close" size="xs" />
                    </button>
                  </div>
                </li>
              </ul>
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
                  role="spinbutton"
                  :aria-valuenow="item.max_devices"
                  aria-valuemin="1"
                  aria-valuemax="5"
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
                    v-if="confirmResetId !== item.id"
                    type="button"
                    class="sub-tool-btn"
                    title="换新密钥（旧口令即刻失效）"
                    :disabled="operatingId !== null"
                    @click="confirmResetId = item.id"
                  >
                    <span>重置</span>
                  </button>
                  <div v-else class="confirm-pop">
                    <span class="confirm-text">换新密钥？</span>
                    <button
                      type="button"
                      class="confirm-act confirm-yes"
                      :disabled="operatingId !== null"
                      @click="
                        () => {
                          resetToken(item.id)
                          confirmResetId = null
                        }
                      "
                    >
                      确定
                    </button>
                    <button
                      type="button"
                      class="confirm-act confirm-no"
                      @click="confirmResetId = null"
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
                    v-if="confirmDeleteId !== item.id"
                    type="button"
                    class="sub-tool-btn danger"
                    title="从名册中彻底注销该访客"
                    :disabled="operatingId !== null"
                    @click="confirmDeleteId = item.id"
                  >
                    <span>注销</span>
                  </button>
                  <div v-else class="confirm-pop">
                    <span class="confirm-text">彻底注销？</span>
                    <button
                      type="button"
                      class="confirm-act confirm-yes danger"
                      :disabled="operatingId !== null"
                      @click="
                        () => {
                          removePass(item.id)
                          confirmDeleteId = null
                        }
                      "
                    >
                      删除
                    </button>
                    <button
                      type="button"
                      class="confirm-act confirm-no"
                      @click="confirmDeleteId = null"
                    >
                      取消
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </li>
        </ul>
      </section>

      <!-- 选项卡 2：登记印发 -->
      <section
        v-else-if="activeTab === 'issue'"
        id="tabpanel-issue"
        class="tab-content issue-pane"
        role="tabpanel"
        aria-label="登记印发新通行证"
      >
        <!-- 场景 A：印发成功后的实体凭据卡（原地一键发送，不切页打断心流） -->
        <div v-if="justCreatedPass" class="issued-voucher-card">
          <div class="voucher-head">
            <span class="voucher-seal">〔 通行凭据已印发 〕</span>
            <h3 class="voucher-title">{{ justCreatedPass.username }}</h3>
            <p class="voucher-sub">
              专属通行证已生成，有效期至
              {{ formatTimestamp(justCreatedPass.expires_at) }}，允许同时授权
              {{ justCreatedPass.max_devices }} 台设备。
            </p>
          </div>

          <div class="voucher-actions">
            <button
              type="button"
              class="hero-btn primary voucher-hero-btn"
              :class="{ copied: copiedLinkId === justCreatedPass.id }"
              @click="handleCopyLink(justCreatedPass)"
            >
              <AppIcon
                :name="copiedLinkId === justCreatedPass.id ? 'check' : 'external-link'"
                size="md"
              />
              <span>{{
                copiedLinkId === justCreatedPass.id ? '已复制免密直达链接' : '复制专属免密直达链接'
              }}</span>
            </button>

            <button
              type="button"
              class="hero-btn secondary voucher-hero-btn"
              :class="{ copied: copiedTokenId === justCreatedPass.id }"
              @click="handleCopyToken(justCreatedPass)"
            >
              <AppIcon :name="copiedTokenId === justCreatedPass.id ? 'check' : 'copy'" size="sm" />
              <span>{{
                copiedTokenId === justCreatedPass.id
                  ? '已复制口令'
                  : `口令：${maskToken(justCreatedPass.token)}`
              }}</span>
            </button>
          </div>

          <div class="voucher-foot">
            <AppButton
              variant="secondary"
              size="md"
              class="voucher-nav-btn"
              @click="resetIssueForm"
            >
              <AppIcon name="plus" size="sm" />
              <span>继续登记下一张</span>
            </AppButton>
            <AppButton variant="ghost" size="md" class="voucher-nav-btn" @click="goToRoster">
              <span>查看现存名册</span>
            </AppButton>
          </div>
        </div>

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
              placeholder="如：好友阿杰 / 客厅 iPad"
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
    </div>
  </Modal>
</template>

<style scoped>
.guest-modal-container {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding: 0;
}

/* 标题栏集成提示信息 */
.guest-modal-title {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
}

.title-info-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 22px;
  height: 22px;
  padding: 0;
  border-radius: var(--radius-1);
  border: 1px solid var(--line);
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.title-info-btn:hover {
  color: var(--accent);
  border-color: var(--accent);
  background: var(--accent-soft);
}

/* 分段选项卡条（吸顶固定） */
.tabs-nav-bar {
  position: sticky;
  top: calc(-1 * var(--space-5));
  z-index: 10;
  background: var(--paper-0);
  margin-left: calc(-1 * var(--space-5));
  margin-right: calc(-1 * var(--space-5));
  margin-top: calc(-1 * var(--space-5));
  padding: var(--space-4) var(--space-5) var(--space-3) var(--space-5);
  margin-bottom: var(--space-1);
  border-bottom: 1px solid var(--line);
  box-shadow: var(--shadow-1);
}

/* 面板内容容器 */
.tab-content {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

/* 名册面板顶部信息 */
.roster-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  padding: 0 var(--space-1);
}

.roster-summary {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.roster-toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.roster-search-box {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 0 var(--space-2);
  height: 32px;
  background: var(--paper-1);
  border: 1px solid var(--line);
  border-radius: var(--radius-pill, 9999px);
  color: var(--ink-2);
  transition: all var(--duration-1) var(--ease-out);
}

.roster-search-box:focus-within {
  border-color: var(--accent);
  background: var(--paper-0);
  color: var(--ink-0);
}

.roster-search-input {
  border: none;
  background: transparent;
  padding: 0;
  font-size: var(--text-xs);
  color: var(--ink-0);
  outline: none;
  width: 110px;
}

.roster-search-input::placeholder {
  color: var(--ink-2);
}

.roster-tip {
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.refresh-btn {
  min-height: 32px;
  padding: 0 var(--space-2);
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  background: transparent;
  border: 1px solid transparent;
  border-radius: var(--radius-1);
  font-size: var(--text-caption);
  color: var(--ink-2);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.refresh-btn:hover {
  color: var(--ink-0);
  border-color: var(--line);
}

/* 状态快捷筛选胶囊栏 */
.filter-bar {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  overflow-x: auto;
  padding: 2px var(--space-1) var(--space-1) var(--space-1);
  scrollbar-width: none;
}

.filter-bar::-webkit-scrollbar {
  display: none;
}

.filter-tab-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  min-height: 32px;
  padding: 0 var(--space-3);
  border-radius: var(--radius-pill, 9999px);
  border: 1px solid var(--line);
  background: var(--paper-1);
  color: var(--ink-1);
  font-size: var(--text-caption);
  cursor: pointer;
  white-space: nowrap;
  transition: all var(--duration-1) var(--ease-out);
}

.filter-tab-btn:hover {
  background: var(--paper-2);
  color: var(--ink-0);
  border-color: var(--line-strong);
}

.filter-tab-btn.active {
  background: var(--paper-0);
  border-color: var(--accent);
  color: var(--accent);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}

.filter-badge {
  font-family: var(--font-mono);
  font-size: 11px;
  padding: 0 6px;
  border-radius: 9999px;
  background: var(--paper-2);
  color: var(--ink-2);
}

.filter-tab-btn.active .filter-badge {
  background: var(--accent-soft);
  color: var(--accent);
}

/* 状态占位 */
.state-panel {
  padding: var(--space-8) var(--space-4);
  text-align: center;
  color: var(--ink-2);
  font-size: var(--text-body);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
}

.state-panel.error {
  color: var(--accent);
}

.retry-btn {
  min-height: 40px;
  padding: 0 var(--space-4);
  border-radius: var(--radius-1);
  border: 1px solid var(--accent);
  background: var(--accent-soft);
  color: var(--accent);
  cursor: pointer;
  font-weight: 600;
}

.empty-seal {
  font-family: var(--font-display);
  font-size: var(--text-title);
  color: var(--ink-2);
  border: 1px solid var(--line);
  padding: var(--space-2) var(--space-4);
  border-radius: var(--radius-1);
  background: var(--paper-1);
}

.empty-hint {
  font-size: var(--text-caption);
  color: var(--ink-2);
  margin-bottom: var(--space-2);
}

/* 名册卡片列表（随 Modal 单源平滑滚动） */
.pass-card-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

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
}

.pass-name {
  font-size: var(--text-body);
  font-weight: 700;
  color: var(--ink-0);
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

/* 印发成功实体凭据卡 */
.issued-voucher-card {
  background: var(--paper-0);
  border: 1px solid color-mix(in oklab, var(--accent) 35%, var(--line));
  border-radius: var(--radius-2);
  padding: var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  box-shadow: var(--shadow-2);
}

.voucher-head {
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
  text-align: center;
  align-items: center;
  padding-bottom: var(--space-3);
  border-bottom: 1px dashed var(--line);
}

.voucher-seal {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--accent);
  font-weight: 600;
  letter-spacing: 0.08em;
}

.voucher-title {
  margin: 0;
  font-family: var(--font-display);
  font-size: var(--text-title);
  color: var(--ink-0);
  font-weight: 700;
}

.voucher-sub {
  margin: 0;
  font-size: var(--text-caption);
  color: var(--ink-2);
}

.voucher-actions {
  display: flex;
  flex-direction: column;
  gap: var(--space-2-5);
}

.voucher-hero-btn {
  min-height: 46px;
  font-size: var(--text-body);
}

.voucher-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--line);
}

.voucher-nav-btn {
  flex: 1;
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

/* 动效与减弱动效 */
.spin-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
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

  .roster-toolbar {
    flex-direction: column;
    align-items: stretch;
    gap: var(--space-2);
  }

  .roster-toolbar-right {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
  }

  .roster-search-box {
    flex: 1;
  }

  .roster-search-input {
    width: 100%;
  }
}

@media (prefers-reduced-motion: reduce) {
  .spin-icon {
    animation: none !important;
  }
}
</style>
