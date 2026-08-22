<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useLibraryStore } from '@/stores/library'
import { useAppSettings } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useViewTransition } from '@/composables/useViewTransition'
import Tooltip from '@/components/Tooltip.vue'

const emit = defineEmits<{
  imported: [source: string, sourceId: string]
}>()

const store = useLibraryStore()
const settings = useAppSettings()
const router = useRouter()
const { toast } = useToast()
const { withViewTransition } = useViewTransition()

const submitBtnRef = ref<HTMLButtonElement | null>(null)
const stepperRef = ref<HTMLElement | null>(null)

onMounted(() => {
  void settings.load()
})

const id = ref('')
const prefetchAll = ref(false)
const warnings = ref<string[]>([])
const lastId = ref('')

const canSubmit = computed(() => /^(?:JM)?\d{6,8}$/i.test(id.value.trim()))

async function submit() {
  if (!canSubmit.value) return
  warnings.value = []
  try {
    const result = await withViewTransition(
      () =>
        store.importComic({
          id: id.value.trim(),
          source: 'jm',
          prefetch_covers: 4,
          prefetch_all: prefetchAll.value,
        }),
      { element: submitBtnRef.value },
    )
    lastId.value = result.meta.display_id
    warnings.value = result.warnings
    toast(store.importMessage, warnings.value.length ? 'error' : 'info')

    if (!result.from_cache) {
      emit('imported', result.meta.source, result.meta.source_id)
      if (prefetchAll.value) {
        router.push(`/comic/${result.meta.source}/${result.meta.source_id}`)
      }
    }
    id.value = ''
  } catch {
    toast(store.error, 'error')
  }
}

function decConcurrency() {
  void withViewTransition(() => settings.dec(), { element: stepperRef.value })
}

function incConcurrency() {
  void withViewTransition(() => settings.inc(), { element: stepperRef.value })
}
</script>

<template>
  <section class="import-panel" aria-labelledby="import-title">
    <div>
      <p class="eyebrow" id="import-title">Import / 收录</p>
      <h2>放进纸间</h2>
      <p class="hint">
        输入禁漫车号。首次收录会读取元数据并缓存前 4 页做封面； 之后永远先读本地，不再打扰远端。
      </p>
    </div>

    <form class="import-form" @submit.prevent="submit">
      <label class="field">
        <span class="field-prefix">JM</span>
        <input
          v-model="id"
          type="text"
          inputmode="numeric"
          autocomplete="off"
          placeholder="523607"
          aria-label="禁漫车号"
        />
      </label>
      <button
        ref="submitBtnRef"
        class="btn btn-primary"
        type="submit"
        :disabled="!canSubmit || store.importing"
      >
        {{ store.importing ? '收录中…' : '收录到纸间' }}
      </button>
    </form>

    <div class="download-settings" :aria-busy="settings.loading">
      <div class="download-settings__row">
        <label class="cache-check">
          <input v-model="prefetchAll" type="checkbox" />
          <span>同时缓存全部页面</span>
        </label>
        <Tooltip
          id="cache-all-tip"
          tip="单本上限 600P，其余页面阅读时自动补齐。"
          side="top"
          align="end"
        >
          <button class="tooltip-icon" type="button" aria-label="关于缓存全部页面">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <circle cx="8" cy="8" r="6.4" fill="none" stroke="currentColor" stroke-width="1.4" />
              <path
                d="M8 7.3v3.2"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
              />
              <circle cx="8" cy="5.1" r="0.9" fill="currentColor" />
            </svg>
          </button>
        </Tooltip>
      </div>

      <div class="download-settings__row">
        <span class="download-settings__title">下载并发</span>
        <Tooltip
          id="concurrency-tip"
          tip="同时下载的页数：调大缓存更快，太高容易被 CDN 限流拖慢服务。"
          side="top"
          align="end"
        >
          <button class="tooltip-icon" type="button" aria-label="关于下载并发">
            <svg viewBox="0 0 16 16" aria-hidden="true">
              <circle cx="8" cy="8" r="6.4" fill="none" stroke="currentColor" stroke-width="1.4" />
              <path
                d="M8 7.3v3.2"
                stroke="currentColor"
                stroke-width="1.5"
                stroke-linecap="round"
              />
              <circle cx="8" cy="5.1" r="0.9" fill="currentColor" />
            </svg>
          </button>
        </Tooltip>

        <div
          v-if="!settings.envControlled"
          ref="stepperRef"
          class="stepper"
          role="group"
          aria-label="同时下载页数"
        >
          <button
            class="stepper__btn"
            type="button"
            :disabled="settings.concurrency <= settings.min || settings.loading"
            aria-label="减少下载并发"
            @click="decConcurrency"
          >
            −
          </button>
          <span class="stepper__value">{{ settings.concurrency }}</span>
          <button
            class="stepper__btn"
            type="button"
            :disabled="settings.concurrency >= settings.max || settings.loading"
            aria-label="增加下载并发"
            @click="incConcurrency"
          >
            ＋
          </button>
        </div>

        <span v-else class="stepper__value stepper__value--locked">{{ settings.concurrency }}</span>
        <span class="download-settings__unit">路 / 次</span>
      </div>
      <p v-if="settings.envControlled" class="download-settings__locked">
        已由环境变量 <code>COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS</code> 锁定，界面不可改。
      </p>
    </div>

    <div v-if="store.importMessage" class="import-message" role="status">
      {{ store.importMessage }}
    </div>

    <ul v-if="warnings.length" class="import-warnings">
      <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
    </ul>
  </section>
</template>

<style scoped>
.import-panel {
  display: grid;
  grid-template-columns: minmax(15rem, 0.9fr) minmax(18rem, 1.4fr);
  gap: var(--space-5) var(--space-6);
  padding: var(--space-6);
  border: 1px solid var(--line);
  border-radius: var(--radius-4);
  background: color-mix(in oklab, var(--paper-0) 78%, var(--paper-1));
  box-shadow: var(--shadow-2);
}

.import-panel h2 {
  font-size: var(--text-xl);
}

.hint {
  margin-top: var(--space-3);
  max-width: 34rem;
  color: var(--ink-1);
  font-size: var(--text-sm);
}

.import-form {
  align-self: center;
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-3);
}

.field-prefix {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--accent);
  letter-spacing: 0.1em;
}

.cache-check {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  color: var(--ink-1);
  font-size: var(--text-xs);
  line-height: 1.5;
  cursor: pointer;
}

.cache-check input {
  accent-color: var(--accent);
  width: 1rem;
  height: 1rem;
  flex: 0 0 auto;
}

.tooltip-icon {
  display: inline-grid;
  place-items: center;
  width: 1.25rem;
  height: 1.25rem;
  padding: 0;
  border-radius: 50%;
  background: transparent;
  color: var(--ink-2);
  transition:
    background-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.tooltip-icon svg {
  width: 0.95rem;
  height: 0.95rem;
}

.tooltip-icon:hover {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.download-settings {
  grid-column: 2;
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3);
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-0) 60%, transparent);
}

.download-settings__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.download-settings__title {
  margin-right: auto;
  color: var(--ink-1);
  font-size: var(--text-xs);
}

.download-settings__row--help {
  display: inline-flex;
  align-items: center;
  gap: var(--space-0-5);
}

.download-settings__unit {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

.stepper {
  display: inline-flex;
  align-items: center;
  border: 1px solid var(--line-strong);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  overflow: hidden;
}

.stepper__btn {
  display: grid;
  place-items: center;
  width: 2rem;
  height: 2rem;
  background: transparent;
  color: var(--ink-1);
  font-size: var(--text-md);
  transition:
    background-color var(--duration-1) var(--ease-out),
    color var(--duration-1) var(--ease-out);
}

.stepper__btn:hover:not(:disabled) {
  background: var(--accent-soft);
  color: var(--accent-strong);
}

.stepper__btn:disabled {
  cursor: not-allowed;
  opacity: 0.4;
}

.stepper__value {
  min-width: 2rem;
  padding: 0 0.15rem;
  text-align: center;
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  color: var(--ink-0);
}

.stepper__value--locked {
  padding: 0.25rem 0.6rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-1);
  background: var(--paper-1);
  color: var(--ink-1);
}

.download-settings__locked {
  font-size: var(--text-xs);
  line-height: 1.5;
  color: var(--ink-2);
}

.download-settings__locked code {
  font-family: var(--font-mono);
  color: var(--accent-strong);
}

.import-message {
  grid-column: 1 / -1;
  padding: var(--space-2) var(--space-3);
  border-left: 3px solid var(--success);
  background: color-mix(in oklab, var(--success) 10%, transparent);
  color: var(--ink-1);
  font-size: var(--text-sm);
}

.import-warnings {
  grid-column: 1 / -1;
  display: grid;
  gap: var(--space-1);
  color: var(--warning);
  font-size: var(--text-xs);
}

@media (max-width: 760px) {
  .import-panel {
    grid-template-columns: 1fr;
    padding: var(--space-5);
  }

  .import-form {
    grid-template-columns: 1fr;
  }

  .download-settings {
    grid-column: 1;
  }
}
</style>
