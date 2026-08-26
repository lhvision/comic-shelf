<script setup lang="ts">
/**
 * 阅读器设置面板 —— 模式 / 每屏页数 / 自动切换 / 方向 / 图片适配。
 * 状态直接来自全局 `useReaderSettings`；
 * 关闭按钮复用 ReaderButton（票据 05：与顶栏共用一套控件样式）（createGlobalState 单例），
 * 所以面板与 ReaderView 天然共享同一份设置，无需 props 层层传递。
 */
import {
  AUTO_TURN_OPTIONS,
  FIT_OPTIONS,
  MODE_OPTIONS,
  useReaderSettings,
} from '@/composables/useReaderSettings'
import ReaderButton from '@/components/reader/ReaderButton.vue'
import AppIcon from '@/components/AppIcon.vue'

const emit = defineEmits<{ close: [] }>()

const { settings, pagesPerViewOptions, reset } = useReaderSettings()
</script>

<template>
  <div class="settings-backdrop" @click.self="emit('close')">
    <section class="settings-panel" role="dialog" aria-modal="true" aria-label="阅读设置">
      <header class="settings-head">
        <div>
          <p class="eyebrow">Reader settings</p>
          <h2>阅读设置</h2>
        </div>
        <ReaderButton @click="emit('close')">
          <span>关闭</span>
          <AppIcon name="close" size="xs" />
        </ReaderButton>
      </header>

      <div class="setting-group">
        <h3>阅读模式</h3>
        <div class="mode-cards">
          <button
            v-for="option in MODE_OPTIONS"
            :key="option.value"
            class="mode-card"
            type="button"
            :aria-pressed="settings.mode === option.value"
            @click="settings.mode = option.value"
          >
            <strong>{{ option.label }}</strong>
            <small>{{ option.hint }}</small>
          </button>
        </div>
      </div>

      <div class="setting-group">
        <h3>每屏页数</h3>
        <div class="segmented">
          <button
            v-for="count in pagesPerViewOptions"
            :key="count"
            type="button"
            :aria-pressed="settings.pagesPerView === count"
            @click="settings.pagesPerView = count"
          >
            {{ count }} 页
          </button>
        </div>
      </div>

      <div class="setting-group">
        <div class="setting-row">
          <div class="setting-copy">
            <h3>自动切换</h3>
            <p>
              {{
                settings.autoTurn
                  ? `每 ${settings.autoTurnInterval} 秒切到下一屏`
                  : '开启后按设定间隔自动翻到下一屏'
              }}
            </p>
          </div>
          <button
            class="switch"
            type="button"
            role="switch"
            :aria-checked="settings.autoTurn"
            :aria-label="settings.autoTurn ? '关闭自动切换' : '开启自动切换'"
            @click="settings.autoTurn = !settings.autoTurn"
          />
        </div>
        <div v-if="settings.autoTurn" class="segmented auto-turn-options">
          <button
            v-for="option in AUTO_TURN_OPTIONS"
            :key="option.value"
            type="button"
            :aria-pressed="settings.autoTurnInterval === option.value"
            @click="settings.autoTurnInterval = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <div class="setting-group">
        <h3>横向阅读方向</h3>
        <div class="segmented">
          <button
            type="button"
            :aria-pressed="settings.direction === 'ltr'"
            @click="settings.direction = 'ltr'"
          >
            左 → 右
          </button>
          <button
            type="button"
            :aria-pressed="settings.direction === 'rtl'"
            @click="settings.direction = 'rtl'"
          >
            右 → 左（日漫）
          </button>
        </div>
      </div>

      <div class="setting-group">
        <h3>竖向连续模式图片适配</h3>
        <div class="segmented">
          <button
            v-for="option in FIT_OPTIONS"
            :key="option.value"
            type="button"
            :aria-pressed="settings.fit === option.value"
            @click="settings.fit = option.value"
          >
            {{ option.label }}
          </button>
        </div>
      </div>

      <footer class="settings-foot">
        <p class="settings-save-note">设置会自动保存到本机</p>
        <div class="settings-actions">
          <button class="btn btn-ghost" type="button" @click="reset">恢复默认</button>
          <button class="btn btn-primary" type="button" @click="emit('close')">完成</button>
        </div>
      </footer>
    </section>
  </div>
</template>

<style scoped>
.settings-backdrop {
  position: absolute;
  inset: 0;
  z-index: 20;
  display: grid;
  place-items: center;
  padding: var(--space-4);
  background: var(--reader-backdrop);
}

.settings-panel {
  width: min(42rem, 100%);
  max-height: calc(100dvh - 2 * var(--space-4));
  overflow: auto;
  padding: var(--space-5);
  border: 1px solid var(--reader-line);
  border-radius: var(--radius-3);
  background: var(--reader-bg);
  color: var(--reader-ink);
  box-shadow: var(--shadow-3);
}

.settings-head {
  display: flex;
  justify-content: space-between;
  align-items: start;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.settings-head h2 {
  font-size: var(--text-xl);
}

.setting-group {
  padding: var(--space-4) 0;
  border-top: 1px solid var(--reader-line-soft);
}

.setting-group h3 {
  font-family: var(--font-body);
  font-size: var(--text-xs);
  letter-spacing: 0.08em;
  color: var(--reader-muted);
  margin-bottom: var(--space-3);
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
  transition:
    border-color var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out);
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
  min-height: var(--control-md);
  padding: var(--space-1) var(--space-3);
  border: 1px solid var(--reader-line);
  border-radius: var(--radius-2);
  background: var(--reader-surface-strong);
  color: var(--reader-ink);
  font-size: var(--text-sm);
}

.segmented button[aria-pressed='true'] {
  border-color: var(--accent);
  background: color-mix(in oklab, var(--accent) 20%, transparent);
}

.settings-foot {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: var(--space-3);
  padding-top: var(--space-5);
  border-top: 1px solid var(--reader-line-soft);
}

.settings-save-note {
  align-self: center;
  color: var(--reader-muted);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  letter-spacing: 0.04em;
}

.settings-actions {
  display: flex;
  gap: var(--space-3);
}

.settings-foot .btn-ghost {
  border-color: var(--reader-line-strong);
  color: var(--reader-ink);
}

@media (max-width: 680px) {
  .mode-cards {
    grid-template-columns: 1fr;
  }

  .settings-panel {
    padding: var(--space-4);
  }

  .setting-row {
    flex-wrap: wrap;
  }
}
</style>
