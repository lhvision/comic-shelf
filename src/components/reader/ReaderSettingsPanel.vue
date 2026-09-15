<script setup lang="ts">
/**
 * 阅读器设置面板 —— 模式 / 每屏页数 / 自动切换 / 方向 / 图片适配。
 * 基于公共 Modal.vue（variant="reader" + size="lg"）构建；
 * 状态直接来自全局 `useReaderSettings`（createGlobalState 单例），
 * 面板与 ReaderView 天然共享同一份设置，修改即时响应式生效。
 */
import { computed, nextTick, ref, watch } from 'vue'
import {
  AUTO_SCROLL_SPEED_OPTIONS,
  AUTO_SCROLL_SPEED_PRESETS,
  AUTO_TURN_INTERVALS,
  AUTO_TURN_OPTIONS,
  FIT_OPTIONS,
  MODE_OPTIONS,
  useReaderSettings,
} from '@/composables/useReaderSettings'
import Modal from '@/components/Modal.vue'
import AppButton from '@/components/AppButton.vue'
import AppIcon from '@/components/AppIcon.vue'

const props = withDefaults(
  defineProps<{
    open?: boolean
  }>(),
  {
    open: true,
  },
)

const emit = defineEmits<{ close: [] }>()

const {
  settings,
  globalSettings,
  hasActiveOverride,
  isInheritingGlobal,
  activeComicIsStrip,
  revertToGlobal,
  resetGlobalBaseline,
  pagesPerViewOptions,
} = useReaderSettings()

const activeScopeTab = ref<'comic' | 'global'>('comic')
const currentTargetSettings = computed(() =>
  activeScopeTab.value === 'comic' ? settings : globalSettings,
)

const isCurrentSeamlessStrip = computed(
  () =>
    currentTargetSettings.value.mode === 'vertical-continuous' &&
    currentTargetSettings.value.seamless,
)

const isPagedMode = computed(() => currentTargetSettings.value.mode !== 'vertical-continuous')

const isFitDisabled = computed(() => isPagedMode.value || isCurrentSeamlessStrip.value)

const isCustomInterval = computed(
  () => !AUTO_TURN_INTERVALS.some((val) => val === currentTargetSettings.value.autoTurnInterval),
)

const customInputRef = ref<HTMLInputElement | null>(null)
const customValue = ref(currentTargetSettings.value.autoTurnInterval)

watch(
  () => currentTargetSettings.value.autoTurnInterval,
  (val) => {
    customValue.value = val
  },
)

watch(activeScopeTab, () => {
  customValue.value = currentTargetSettings.value.autoTurnInterval
})

watch(
  () => props.open,
  (open) => {
    if (open) {
      activeScopeTab.value = 'comic'
    }
  },
)

function selectPreset(val: number) {
  currentTargetSettings.value.autoTurnInterval = val
  customValue.value = val
}

function enableCustom() {
  if (!isCustomInterval.value) {
    if ((AUTO_TURN_INTERVALS as readonly number[]).includes(customValue.value)) {
      customValue.value = 20
    }
    currentTargetSettings.value.autoTurnInterval = customValue.value
  }
  nextTick(() => {
    customInputRef.value?.focus()
    customInputRef.value?.select()
  })
}

function onCustomInput(event: Event) {
  const target = event.target as HTMLInputElement
  const num = parseInt(target.value, 10)
  if (!Number.isNaN(num) && num >= 1 && num <= 300) {
    currentTargetSettings.value.autoTurnInterval = num
    customValue.value = num
  }
}

function onCustomBlur() {
  if (!customValue.value || customValue.value < 1) {
    customValue.value = 1
  } else if (customValue.value > 300) {
    customValue.value = 300
  }
  currentTargetSettings.value.autoTurnInterval = customValue.value
  if (customInputRef.value) {
    customInputRef.value.value = String(customValue.value)
  }
}

const isCustomSpeed = computed(
  () =>
    !(AUTO_SCROLL_SPEED_PRESETS as readonly number[]).includes(
      currentTargetSettings.value.autoScrollSpeed,
    ),
)

const customSpeedInputRef = ref<HTMLInputElement | null>(null)
const customSpeedValue = ref(currentTargetSettings.value.autoScrollSpeed)

watch(
  () => currentTargetSettings.value.autoScrollSpeed,
  (val) => {
    customSpeedValue.value = val
  },
)

function selectSpeedPreset(val: number) {
  currentTargetSettings.value.autoScrollSpeed = val
  customSpeedValue.value = val
}

function enableCustomSpeed() {
  if (!isCustomSpeed.value) {
    if ((AUTO_SCROLL_SPEED_PRESETS as readonly number[]).includes(customSpeedValue.value)) {
      customSpeedValue.value = 100
    }
    currentTargetSettings.value.autoScrollSpeed = customSpeedValue.value
  }
  nextTick(() => {
    customSpeedInputRef.value?.focus()
    customSpeedInputRef.value?.select()
  })
}

function onCustomSpeedInput(event: Event) {
  const target = event.target as HTMLInputElement
  const num = parseInt(target.value, 10)
  if (!Number.isNaN(num) && num >= 20 && num <= 400) {
    currentTargetSettings.value.autoScrollSpeed = num
    customSpeedValue.value = num
  }
}

function onCustomSpeedBlur() {
  if (!customSpeedValue.value || customSpeedValue.value < 20) {
    customSpeedValue.value = 20
  } else if (customSpeedValue.value > 400) {
    customSpeedValue.value = 400
  }
  currentTargetSettings.value.autoScrollSpeed = customSpeedValue.value
  if (customSpeedInputRef.value) {
    customSpeedInputRef.value.value = String(customSpeedValue.value)
  }
}
</script>

<template>
  <Modal :open="props.open" title="阅读设置" variant="reader" size="lg" @cancel="emit('close')">
    <div class="settings-content">
      <!-- 作用域分段切换胶囊 -->
      <div class="scope-tabs-bar" role="tablist" aria-label="排版生效范围">
        <button
          type="button"
          role="tab"
          class="scope-tab-btn"
          :class="{ 'is-active': activeScopeTab === 'comic' }"
          :aria-selected="activeScopeTab === 'comic'"
          @click="activeScopeTab = 'comic'"
        >
          <AppIcon name="book-open" size="xs" />
          <span>本作偏好</span>
          <span v-if="activeComicIsStrip" class="scope-status-tag is-strip">条漫</span>
          <span v-else-if="hasActiveOverride" class="scope-status-tag is-override">已自定义</span>
          <span v-else class="scope-status-tag is-inherited">跟随全局</span>
        </button>

        <button
          type="button"
          role="tab"
          class="scope-tab-btn"
          :class="{ 'is-active': activeScopeTab === 'global' }"
          :aria-selected="activeScopeTab === 'global'"
          @click="activeScopeTab = 'global'"
        >
          <AppIcon name="globe" size="xs" />
          <span>全局默认</span>
        </button>
      </div>

      <!-- 作用域上下文提示横幅 -->
      <div
        v-if="activeScopeTab === 'comic'"
        class="scope-hint-banner"
        :class="{ 'is-override': hasActiveOverride }"
      >
        <div class="scope-hint-content">
          <strong v-if="activeComicIsStrip">〔 条漫专属长卷 〕</strong>
          <strong v-else-if="hasActiveOverride">〔 本作专属偏好 〕</strong>
          <strong v-else>〔 继承全局默认 〕</strong>
          <span class="scope-hint-desc">
            {{
              activeComicIsStrip
                ? '已智能应用条漫无缝拼接与宽度适配，不改变全局默认。'
                : hasActiveOverride
                  ? '当前正在使用针对本作单独定制的排版，不影响其他漫画。'
                  : '本作尚未保存独立设置。在此调节将立即为本书创建专属偏好。'
            }}
          </span>
        </div>
        <AppButton
          v-if="isInheritingGlobal"
          variant="ghost"
          size="xs"
          theme="reader"
          class="scope-jump-link"
          @click="activeScopeTab = 'global'"
        >
          <span>去改全站默认</span>
          <template #suffix>
            <AppIcon name="arrow-right" size="xs" />
          </template>
        </AppButton>
      </div>

      <div v-else class="scope-hint-banner is-global">
        <div class="scope-hint-content">
          <strong>〔 全局默认基线 〕</strong>
          <span class="scope-hint-desc">
            此处设置将作为所有未单独自定义漫画的默认排版（新收录漫画自动继承）。
          </span>
        </div>
      </div>

      <div class="setting-group setting-group--first">
        <h3>阅读模式</h3>
        <div class="mode-cards">
          <button
            v-for="option in MODE_OPTIONS"
            :key="option.value"
            class="mode-card"
            type="button"
            :aria-pressed="currentTargetSettings.mode === option.value"
            @click="currentTargetSettings.mode = option.value"
          >
            <strong>{{ option.label }}</strong>
            <small>{{ option.hint }}</small>
          </button>
        </div>
      </div>

      <div v-if="currentTargetSettings.mode === 'vertical-continuous'" class="setting-group">
        <div class="setting-row">
          <div class="setting-copy">
            <h3>无缝长卷拼接</h3>
            <p>
              {{
                currentTargetSettings.seamless
                  ? '已消除页间黑缝与阴影，自动将切片画卷咬合为连续条漫'
                  : '保留页面间距、底色与行内页码指示'
              }}
            </p>
          </div>
          <button
            class="switch"
            type="button"
            role="switch"
            :aria-checked="currentTargetSettings.seamless"
            :aria-label="currentTargetSettings.seamless ? '关闭无缝长卷拼接' : '开启无缝长卷拼接'"
            @click="currentTargetSettings.seamless = !currentTargetSettings.seamless"
          />
        </div>
      </div>

      <div class="setting-group" :class="{ 'is-disabled-group': isCurrentSeamlessStrip }">
        <div class="setting-header-with-badge">
          <h3>每屏页数</h3>
          <span v-if="isCurrentSeamlessStrip" class="constraint-badge">条漫已锁定单页</span>
        </div>
        <div class="segmented">
          <button
            v-for="count in pagesPerViewOptions"
            :key="count"
            type="button"
            :disabled="isCurrentSeamlessStrip"
            :aria-pressed="currentTargetSettings.pagesPerView === count"
            @click="currentTargetSettings.pagesPerView = count"
          >
            {{ count }} 页
          </button>
        </div>
      </div>

      <div class="setting-group">
        <div class="setting-row">
          <div class="setting-copy">
            <h3>
              {{ currentTargetSettings.mode === 'vertical-continuous' ? '自动流卷' : '自动切换' }}
            </h3>
            <p v-if="currentTargetSettings.mode === 'vertical-continuous'">
              {{
                currentTargetSettings.autoTurn
                  ? `以每秒 ${currentTargetSettings.autoScrollSpeed} 像素平滑匀速向下滚动`
                  : '开启后以设定速率匀速漫游，无需手动翻滚'
              }}
            </p>
            <p v-else>
              {{
                currentTargetSettings.autoTurn
                  ? `每 ${currentTargetSettings.autoTurnInterval} 秒切到下一屏`
                  : '开启后按设定间隔自动翻到下一屏'
              }}
            </p>
          </div>
          <button
            class="switch"
            type="button"
            role="switch"
            :aria-checked="currentTargetSettings.autoTurn"
            :aria-label="
              currentTargetSettings.autoTurn
                ? currentTargetSettings.mode === 'vertical-continuous'
                  ? '关闭自动流卷'
                  : '关闭自动切换'
                : currentTargetSettings.mode === 'vertical-continuous'
                  ? '开启自动流卷'
                  : '开启自动切换'
            "
            @click="currentTargetSettings.autoTurn = !currentTargetSettings.autoTurn"
          />
        </div>

        <!-- 连续模式：速率预设与自定义 (px/s) -->
        <div
          v-if="
            currentTargetSettings.autoTurn && currentTargetSettings.mode === 'vertical-continuous'
          "
          class="segmented auto-turn-options"
        >
          <button
            v-for="option in AUTO_SCROLL_SPEED_OPTIONS"
            :key="option.value"
            type="button"
            :aria-pressed="!isCustomSpeed && currentTargetSettings.autoScrollSpeed === option.value"
            @click="selectSpeedPreset(option.value)"
          >
            {{ option.label }}
          </button>

          <button
            v-if="!isCustomSpeed"
            type="button"
            class="custom-chip-btn"
            aria-label="自定义自动流卷速度"
            @click="enableCustomSpeed"
          >
            自定义…
          </button>

          <div v-else class="custom-interval-pill" :class="{ 'is-active': isCustomSpeed }">
            <input
              ref="customSpeedInputRef"
              v-model.number="customSpeedValue"
              type="number"
              min="20"
              max="400"
              step="10"
              class="custom-interval-input"
              aria-label="自定义流卷速度"
              @input="onCustomSpeedInput"
              @blur="onCustomSpeedBlur"
              @keydown.enter="onCustomSpeedBlur"
            />
            <span class="custom-unit">px/s</span>
          </div>
        </div>

        <!-- 翻页模式：离散秒数预设与自定义 (秒) -->
        <div v-else-if="currentTargetSettings.autoTurn" class="segmented auto-turn-options">
          <button
            v-for="option in AUTO_TURN_OPTIONS"
            :key="option.value"
            type="button"
            :aria-pressed="
              !isCustomInterval && currentTargetSettings.autoTurnInterval === option.value
            "
            @click="selectPreset(option.value)"
          >
            {{ option.label }}
          </button>

          <button
            v-if="!isCustomInterval"
            type="button"
            class="custom-chip-btn"
            aria-label="自定义自动翻页秒数"
            @click="enableCustom"
          >
            自定义…
          </button>

          <div v-else class="custom-interval-pill" :class="{ 'is-active': isCustomInterval }">
            <input
              ref="customInputRef"
              v-model.number="customValue"
              type="number"
              min="1"
              max="300"
              step="1"
              class="custom-interval-input"
              aria-label="自定义翻页间隔秒数"
              @input="onCustomInput"
              @blur="onCustomBlur"
              @keydown.enter="onCustomBlur"
            />
            <span class="custom-unit">秒</span>
          </div>
        </div>
      </div>

      <div class="setting-group">
        <h3>横向阅读方向</h3>
        <div class="segmented">
          <button
            type="button"
            :aria-pressed="currentTargetSettings.direction === 'ltr'"
            @click="currentTargetSettings.direction = 'ltr'"
          >
            <span>左</span>
            <AppIcon name="arrow-right" size="xs" />
            <span>右</span>
          </button>
          <button
            type="button"
            :aria-pressed="currentTargetSettings.direction === 'rtl'"
            @click="currentTargetSettings.direction = 'rtl'"
          >
            <span>右</span>
            <AppIcon name="arrow-left" size="xs" />
            <span>左（日漫）</span>
          </button>
        </div>
      </div>

      <div class="setting-group" :class="{ 'is-disabled-group': isFitDisabled }">
        <div class="setting-header-with-badge">
          <h3>图片适配</h3>
          <span v-if="isPagedMode" class="constraint-badge">翻页已锁定整页入目</span>
          <span v-else-if="isCurrentSeamlessStrip" class="constraint-badge"
            >条漫已锁定适应宽度</span
          >
        </div>
        <p v-if="isPagedMode" class="setting-desc">
          翻页模式自动保持整页完整入目，避免产生单屏内垂直滚动。
        </p>
        <p v-else-if="isCurrentSeamlessStrip" class="setting-desc">
          条漫长卷已锁定适应宽度，消除横向黑边。
        </p>
        <div class="segmented">
          <button
            v-for="option in FIT_OPTIONS"
            :key="option.value"
            type="button"
            :disabled="isFitDisabled"
            :aria-pressed="
              isPagedMode
                ? option.value === 'height'
                : isCurrentSeamlessStrip
                  ? option.value === 'width'
                  : currentTargetSettings.fit === option.value
            "
            @click="currentTargetSettings.fit = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>
    </div>

    <template #footer>
      <div class="settings-foot-inner">
        <p class="settings-save-note">
          {{
            activeScopeTab === 'comic'
              ? isInheritingGlobal
                ? '修改将为本作创建专属设置'
                : '修改已自动保存至本作'
              : '修改将实时更新全站默认'
          }}
        </p>
        <div class="settings-actions">
          <AppButton
            v-if="activeScopeTab === 'comic'"
            variant="ghost"
            size="sm"
            type="button"
            :disabled="isInheritingGlobal"
            @click="revertToGlobal"
          >
            恢复跟随全局
          </AppButton>
          <AppButton v-else variant="ghost" size="sm" type="button" @click="resetGlobalBaseline">
            恢复出厂默认
          </AppButton>
          <AppButton variant="primary" size="sm" type="button" @click="emit('close')">
            完成
          </AppButton>
        </div>
      </div>
    </template>
  </Modal>
</template>

<style scoped>
.settings-content {
  display: flex;
  flex-direction: column;
}

/* ---------------- 作用域分段切换胶囊 ---------------- */
.scope-tabs-bar {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: var(--space-1);
  background: var(--reader-surface-strong);
  border-radius: var(--radius-2);
  border: 1px solid var(--reader-line);
}

.scope-tab-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-2);
  min-height: var(--control-sm);
  padding: var(--space-1-5) var(--space-3);
  border-radius: var(--radius-1);
  border: 1px solid transparent;
  background: transparent;
  color: var(--reader-muted);
  font-family: var(--font-body);
  font-size: var(--text-sm);
  font-weight: 500;
  cursor: pointer;
  transition: all 160ms cubic-bezier(0.2, 0, 0, 1);
}

.scope-tab-btn:hover {
  color: var(--reader-ink);
  background: color-mix(in oklab, var(--reader-ink) 6%, transparent);
}

.scope-tab-btn.is-active {
  color: var(--reader-ink);
  background: var(--reader-bg);
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.45);
  border-color: var(--reader-line-strong);
}

.scope-status-tag {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  padding: var(--space-badge-y) var(--space-badge-x);
  border-radius: var(--radius-1);
  line-height: 1.2;
}

.scope-status-tag.is-strip {
  background: color-mix(in oklab, var(--accent) 18%, transparent);
  color: var(--accent);
  border: 1px solid color-mix(in oklab, var(--accent) 35%, transparent);
}

.scope-status-tag.is-override {
  background: color-mix(in oklab, var(--warning) 18%, transparent);
  color: var(--warning);
  border: 1px solid color-mix(in oklab, var(--warning) 35%, transparent);
}

.scope-status-tag.is-inherited {
  background: var(--reader-surface);
  color: var(--reader-muted);
  border: 1px solid var(--reader-line-soft);
}

/* ---------------- 作用域上下文提示横幅 ---------------- */
.scope-hint-banner {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: var(--space-2-5) var(--space-3-5);
  border-radius: var(--radius-2);
  background: var(--reader-surface);
  border: 1px solid var(--reader-line-soft);
  font-size: var(--text-xs);
  color: var(--reader-muted);
  margin-bottom: var(--space-3);
}

.scope-hint-banner.is-override {
  border-color: color-mix(in oklab, var(--warning) 30%, transparent);
}

.scope-hint-banner.is-global {
  border-color: color-mix(in oklab, var(--accent) 30%, transparent);
}

.scope-hint-content {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.scope-hint-content strong {
  color: var(--reader-ink);
  font-weight: 600;
  white-space: nowrap;
}

.scope-hint-desc {
  color: var(--reader-muted);
  line-height: 1.4;
}

.scope-jump-link {
  background: transparent;
  border: none;
  color: var(--accent);
  font-size: var(--text-xs);
  cursor: pointer;
  padding: var(--space-1) var(--space-2);
  text-decoration: underline;
  text-underline-offset: 2px;
  white-space: nowrap;
  flex-shrink: 0;
}

.scope-jump-link:hover {
  color: var(--accent-strong);
}

@media (max-width: 480px) {
  .scope-hint-banner {
    flex-direction: column;
    align-items: flex-start;
  }
}

.setting-group {
  padding: var(--space-4) 0;
  border-top: 1px solid var(--reader-line-soft);
}

.setting-group.setting-group--first {
  padding-top: var(--space-3);
  border-top: 1px solid var(--reader-line-soft);
}

.setting-group h3 {
  font-family: var(--font-body);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  color: var(--reader-muted);
  margin-bottom: var(--space-3);
}

.setting-header-with-badge {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
}

.setting-header-with-badge h3 {
  margin-bottom: 0;
}

.constraint-badge {
  font-family: var(--font-mono);
  font-size: var(--text-caption);
  color: var(--accent);
  background: var(--accent-soft);
  padding: var(--space-badge-y) var(--space-badge-x);
  border-radius: var(--radius-1);
  letter-spacing: 0.04em;
}

.setting-desc {
  color: var(--reader-muted);
  font-size: var(--text-xs);
  line-height: 1.5;
  margin-bottom: var(--space-2);
}

.is-disabled-group .segmented button:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.setting-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
}

.setting-copy h3 {
  margin-bottom: var(--space-1);
}

.setting-copy p {
  max-width: 36ch;
  color: var(--reader-muted);
  font-size: var(--text-xs);
  line-height: 1.5;
}

.switch {
  position: relative;
  flex: none;
  width: var(--control-md);
  height: var(--control-md);
  border: 0;
  border-radius: 999px;
  background: transparent;
  cursor: pointer;
}

.switch::before {
  content: '';
  position: absolute;
  top: 50%;
  left: 0;
  width: 100%;
  height: 1.5rem;
  translate: 0 -50%;
  border: 1px solid var(--reader-line-strong);
  border-radius: 999px;
  background: var(--reader-surface-strong);
  transition:
    background-color var(--duration-2) var(--ease-out),
    border-color var(--duration-2) var(--ease-out);
}

.switch::after {
  content: '';
  position: absolute;
  top: 50%;
  left: var(--space-1);
  width: var(--space-4);
  height: var(--space-4);
  translate: 0 -50%;
  border-radius: 50%;
  background: var(--reader-muted);
  transition:
    translate var(--duration-2) var(--ease-out),
    background-color var(--duration-2) var(--ease-out);
}

.switch[aria-checked='true']::before {
  border-color: var(--accent);
  background: var(--accent);
}

.switch[aria-checked='true']::after {
  translate: calc(var(--control-md) - var(--space-4) - 2 * var(--space-1)) -50%;
  background: var(--paper-0);
}

.switch:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.auto-turn-options {
  margin-top: var(--space-3);
}

.mode-cards {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}

.mode-card {
  display: grid;
  gap: var(--space-1);
  padding: var(--space-3);
  border: 1px solid var(--reader-line);
  border-radius: var(--radius-2);
  background: var(--reader-surface);
  color: var(--reader-ink);
  text-align: left;
  cursor: pointer;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.mode-card:hover {
  border-color: var(--reader-line-strong);
  background: var(--reader-surface-hover);
}

.mode-card[aria-pressed='true'] {
  border-color: var(--accent);
  background: color-mix(in oklab, var(--accent) 20%, transparent);
}

.mode-card strong {
  font-size: var(--text-sm);
}

.mode-card small {
  color: var(--reader-muted);
  line-height: 1.45;
}

.segmented {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.segmented button {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-1);
  min-height: var(--control-md);
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--reader-line);
  border-radius: var(--radius-2);
  background: var(--reader-surface-strong);
  color: var(--reader-ink);
  font-size: var(--text-sm);
  cursor: pointer;
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.segmented button:hover {
  border-color: var(--reader-line-strong);
  background: var(--reader-surface-hover);
}

.segmented button[aria-pressed='true'] {
  border-color: var(--accent);
  background: color-mix(in oklab, var(--accent) 20%, transparent);
}

.custom-chip-btn {
  min-height: var(--control-md);
  padding: var(--space-1) var(--space-3);
  border: 1px dashed var(--reader-line-strong);
  border-radius: var(--radius-2);
  background: var(--reader-surface-strong);
  color: var(--reader-muted);
  font-size: var(--text-sm);
  cursor: pointer;
  transition:
    border-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
}

.custom-chip-btn:hover {
  border-color: var(--accent);
  color: var(--reader-ink);
  background: color-mix(in oklab, var(--accent) 12%, var(--reader-surface-strong));
}

.custom-interval-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  min-height: var(--control-md);
  padding: 0 var(--space-2);
  border: 1px solid var(--accent);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--accent) 20%, transparent);
  color: var(--reader-ink);
  font-size: var(--text-sm);
}

.custom-interval-input {
  width: 2.8rem;
  height: calc(var(--control-md) - 0.5rem);
  padding: 0 0.25rem;
  border: 1px solid color-mix(in oklab, var(--accent) 60%, var(--reader-line));
  border-radius: var(--radius-1);
  background: var(--reader-bg);
  color: var(--reader-ink);
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  text-align: center;
  outline: none;
}

.custom-interval-input:focus {
  border-color: var(--accent);
  box-shadow: 0 0 0 2px color-mix(in oklab, var(--accent) 30%, transparent);
}

.custom-unit {
  font-size: var(--text-sm);
  color: var(--reader-ink);
}

.settings-foot-inner {
  display: flex;
  width: 100%;
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
}

.settings-save-note {
  color: var(--reader-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.04em;
}

.settings-actions {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

@media (max-width: 680px) {
  .mode-cards {
    grid-template-columns: 1fr;
  }

  .setting-row {
    flex-wrap: wrap;
  }
}
</style>
