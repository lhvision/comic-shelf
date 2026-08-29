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
  copyToken,
  copyShareLink,
  closeModal,
} = useGuestPasses()

type TabKey = 'roster' | 'issue'

const activeTab = ref<TabKey>('roster')
const newUsername = ref('')
const selectedDays = ref<number | null>(30)
const creating = ref(false)
const inputRef = ref<HTMLInputElement | null>(null)

// 刚印发成功的凭证对象（原地展示，杜绝粗暴跳页截断心流）
const justCreatedPass = ref<GuestPass | null>(null)

// 局部内联确认与状态反馈
const confirmResetId = ref<number | null>(null)
const confirmDeleteId = ref<number | null>(null)
const copiedLinkId = ref<number | null>(null)
const copiedTokenId = ref<number | null>(null)

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

async function handleCreate() {
  if (!newUsername.value.trim() || creating.value) return
  creating.value = true
  try {
    const created = await createPass({
      username: newUsername.value.trim(),
      expires_days: selectedDays.value,
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
  nextTick(() => {
    inputRef.value?.focus()
  })
}

function goToRoster() {
  justCreatedPass.value = null
  activeTab.value = 'roster'
}

async function handleCopyLink(item: { id: number; token: string }) {
  const ok = await copyShareLink(item.token)
  if (ok) {
    copiedLinkId.value = item.id
    setTimeout(() => {
      if (copiedLinkId.value === item.id) {
        copiedLinkId.value = null
      }
    }, 1500)
  }
}

async function handleCopyToken(item: { id: number; token: string }) {
  const ok = await copyToken(item.token)
  if (ok) {
    copiedTokenId.value = item.id
    setTimeout(() => {
      if (copiedTokenId.value === item.id) {
        copiedTokenId.value = null
      }
    }, 1500)
  }
}

function formatTimestamp(ts: number | null): string {
  if (!ts) return '永久有效'
  const date = new Date(ts * 1000)
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, '0')
  const d = String(date.getDate()).padStart(2, '0')
  return `${y}-${m}-${d}`
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
    copiedLinkId.value = null
    copiedTokenId.value = null
    justCreatedPass.value = null
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
          <span class="roster-tip">共登记 {{ passes.length }} 位访客</span>
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

        <!-- 暂无名册 -->
        <div v-else-if="passes.length === 0" class="state-panel empty">
          <div class="empty-seal">暂无访客</div>
          <p class="empty-hint">尚未印发任何通行证，点击下方按钮即可派发。</p>
          <AppButton variant="primary" size="md" @click="activeTab = 'issue'">
            <AppIcon name="plus" size="sm" />
            <span>登记第一张通行证</span>
          </AppButton>
        </div>

        <!-- 借书卡名册卡片列表（消除 420px 嵌套滚动死锁，自然随 Modal 滚动） -->
        <ul v-else class="pass-card-list">
          <li
            v-for="item in passes"
            :key="item.id"
            class="pass-card"
            :class="{
              disabled: !item.is_active,
              expired: item.is_expired && item.is_active,
            }"
          >
            <div class="pass-card-top">
              <div class="pass-identity">
                <strong class="pass-name">{{ item.username }}</strong>
                <span class="pass-date">{{ formatTimestamp(item.created_at) }} 印发</span>
              </div>

              <!-- 典藏印章（语义纠偏：生效为朱砂印，过期与停用为沉静墨印） -->
              <div
                class="status-seal"
                :class="{
                  active: item.is_active && !item.is_expired,
                  expired: item.is_active && item.is_expired,
                  disabled: !item.is_active,
                }"
              >
                <span v-if="!item.is_active">〔 已停用 〕</span>
                <span v-else-if="item.is_expired">〔 已过期 〕</span>
                <span v-else>〔 {{ getDaysRemaining(item.expires_at) }} 〕</span>
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

            <!-- 辅助信息与次要管理工具栏 -->
            <div class="card-footer">
              <div class="expiry-info">
                <span class="expiry-label">有效期至：</span>
                <span class="expiry-val">{{ formatTimestamp(item.expires_at) }}</span>
              </div>

              <div class="sub-toolbar">
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
              专属通行证已生成，有效期至 {{ formatTimestamp(justCreatedPass.expires_at) }}。
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
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.04);
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
  padding: 0 var(--space-1);
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

/* 典藏印章 */
.status-seal {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-1);
  border: 1px solid transparent;
}

.status-seal.active {
  color: var(--accent);
  background: var(--accent-soft);
  border-color: color-mix(in oklab, var(--accent) 30%, transparent);
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
  text-decoration: line-through;
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
    align-items: flex-start;
    gap: var(--space-2);
  }

  .sub-toolbar {
    width: 100%;
    justify-content: space-between;
  }

  .sub-tool-btn {
    min-height: 40px;
    padding: 0 var(--space-3);
  }
}

@media (prefers-reduced-motion: reduce) {
  .spin-icon {
    animation: none !important;
  }
}
</style>
