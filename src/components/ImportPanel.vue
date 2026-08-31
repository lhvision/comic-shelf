<script setup lang="ts">
import { computed, onMounted, ref, useId, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useEventListener } from '@vueuse/core'
import { useLibraryStore } from '@/stores/library'
import { useAppSettings } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useViewTransition } from '@/composables/useViewTransition'
import { api } from '@/api/client'
import Tooltip from '@/components/Tooltip.vue'
import AppIcon from '@/components/AppIcon.vue'

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
const contentId = useId()
const isMobileExpanded = ref(false)

useEventListener('resize', () => {
  if (typeof window !== 'undefined' && window.innerWidth > 640 && isMobileExpanded.value) {
    isMobileExpanded.value = false
  }
})

onMounted(() => {
  void settings.load()
})

const id = ref('')
const prefetchAll = ref(false)
const warnings = ref<string[]>([])
const lastId = ref('')

const activeTab = ref<'jm' | 'local'>('jm')
const localPath = ref('')
const localImporting = ref(false)

watch([id, localPath, activeTab], () => {
  if (store.importMessage) store.clearImportMessage()
  warnings.value = []
})

const canSubmit = computed(() => /^(?:JM)?\d{5,8}$/i.test(id.value.trim()))

const jmBtnText = computed(() => (store.importing ? '收录中…' : '收录到纸间'))
const localBtnText = computed(() => (localImporting.value ? '扫描中…' : '一键收录'))

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
    toast(store.importMessage, warnings.value.length ? 'error' : 'success')

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

async function submitLocalPath() {
  if (!localPath.value.trim()) return
  localImporting.value = true
  try {
    const res = await api.importLocalPath({
      path: localPath.value.trim(),
    })
    await store.load()
    toast(`已收录本地图集《${res.meta.title}》（共 ${res.meta.page_count} 页）`, 'info')
    emit('imported', res.meta.source, res.meta.source_id)
    router.push(`/comic/${res.meta.source}/${res.meta.source_id}`)
    localPath.value = ''
  } catch (err) {
    toast(err instanceof Error ? err.message : String(err), 'error')
  } finally {
    localImporting.value = false
  }
}

function goToWorkshop() {
  router.push('/create')
}

function decConcurrency() {
  void withViewTransition(() => settings.dec(), { element: stepperRef.value })
}

function incConcurrency() {
  void withViewTransition(() => settings.inc(), { element: stepperRef.value })
}
</script>

<template>
  <section
    class="import-panel"
    :class="{ 'is-mobile-collapsed': !isMobileExpanded }"
    aria-labelledby="import-title"
  >
    <button
      type="button"
      class="mobile-collapse-bar"
      :aria-expanded="isMobileExpanded"
      :aria-controls="contentId"
      @click="isMobileExpanded = !isMobileExpanded"
    >
      <span class="mobile-collapse-lead">
        <AppIcon name="plus" size="xs" :stroke-width="2" />
        <span>收录新作品 / 本地图集</span>
      </span>
      <span class="mobile-collapse-action font-mono">
        <span class="action-text">{{ isMobileExpanded ? '收起' : '展开' }}</span>
        <AppIcon
          name="chevron-down"
          size="xs"
          class="collapse-chevron"
          :class="{ 'is-rotated': isMobileExpanded }"
        />
      </span>
    </button>

    <div :id="contentId" class="import-animator" :class="{ 'is-expanded': isMobileExpanded }">
      <div class="import-content">
        <div class="import-info">
          <div class="panel-tabs">
            <button
              class="panel-tab"
              :class="{ 'is-active': activeTab === 'jm' }"
              type="button"
              @click="activeTab = 'jm'"
            >
              禁漫车号
            </button>
            <button
              class="panel-tab"
              :class="{ 'is-active': activeTab === 'local' }"
              type="button"
              @click="activeTab = 'local'"
            >
              本地自建 / 拆帧
            </button>
          </div>

          <p class="eyebrow" id="import-title">
            {{ activeTab === 'jm' ? 'IMPORT / 收录' : 'LOCAL ARCHIVE / 自建' }}
          </p>
          <h2>{{ activeTab === 'jm' ? '放进纸间' : '收录本地图集' }}</h2>
          <p class="hint">
            {{
              activeTab === 'jm'
                ? '输入禁漫车号。首次收录会读取元数据并缓存前 4 页做封面；之后永远先读本地，不再打扰远端。'
                : '输入服务器目录（如 public/tiya-frames）一键扫描收录，或进入工坊上传多图与多章节。'
            }}
          </p>
        </div>

        <div class="import-controls">
          <!-- JM Tab Form -->
          <template v-if="activeTab === 'jm'">
            <form class="import-form" @submit.prevent="submit">
              <label class="field import-field">
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
                class="import-submit-btn"
                type="submit"
                :disabled="!canSubmit || store.importing"
                aria-label="收录到纸间"
              >
                <span class="vertical-text">
                  <span v-for="(char, idx) in jmBtnText" :key="idx">{{ char }}</span>
                </span>
              </button>
            </form>
          </template>

          <!-- Local Tab Form -->
          <template v-else>
            <form class="import-form" @submit.prevent="submitLocalPath">
              <label class="field import-field">
                <span class="field-prefix">PATH</span>
                <input
                  v-model="localPath"
                  type="text"
                  autocomplete="off"
                  placeholder="public/tiya-frames"
                  aria-label="服务器本地目录路径"
                />
              </label>
              <button
                class="import-submit-btn"
                type="submit"
                :disabled="!localPath.trim() || localImporting"
                aria-label="一键收录"
              >
                <span class="vertical-text">
                  <span v-for="(char, idx) in localBtnText" :key="idx">{{ char }}</span>
                </span>
              </button>
            </form>

            <div class="workshop-card">
              <span class="workshop-hint">需要上传多图或编排多章节？</span>
              <button class="workshop-btn" type="button" @click="goToWorkshop">
                进入自建图集工坊 →
              </button>
            </div>
          </template>

          <div class="download-settings" :aria-busy="settings.loading">
            <div v-if="activeTab === 'jm'" class="download-settings__row">
              <label class="cache-check">
                <input v-model="prefetchAll" type="checkbox" />
                <span>同时缓存全部页面</span>
              </label>
              <Tooltip
                id="cache-all-tip"
                tip="收录时直接把所有章节与页面下载到本地磁盘（适合整本离线保存）。不勾选则仅缓存前 4 页封面，后续页面在翻阅时按需秒级懒下载。"
                side="top"
              >
                <button class="tooltip-icon" type="button" aria-label="关于缓存全部页面">
                  <AppIcon name="info" size="xs" />
                </button>
              </Tooltip>
            </div>

            <div class="download-settings__row">
              <label class="cache-check">
                <input
                  :checked="settings.guestHideNewComics"
                  type="checkbox"
                  @change="settings.setGuestHideNewComics(!settings.guestHideNewComics)"
                />
                <span>新入库默认对访客隐藏</span>
              </label>
              <Tooltip
                id="guest-hide-tip"
                tip="开启后，新收录或导入的漫画初始状态将对访客隐身，防止私人敏感藏书误暴露。馆长审核后可在卡片底部手动公开借阅。"
                side="top"
              >
                <button class="tooltip-icon" type="button" aria-label="关于新入库默认对访客隐藏">
                  <AppIcon name="info" size="xs" />
                </button>
              </Tooltip>
            </div>

            <template v-if="activeTab === 'jm'">
              <div class="download-settings__row">
                <span class="download-settings__title">下载并发</span>
                <Tooltip
                  id="concurrency-tip"
                  tip="同时下载的页数：调大缓存更快，太高容易被 CDN 限流拖慢服务。"
                  side="top"
                >
                  <button class="tooltip-icon" type="button" aria-label="关于下载并发">
                    <AppIcon name="info" size="xs" />
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

                <span v-else class="stepper__value stepper__value--locked">{{
                  settings.concurrency
                }}</span>
                <span class="download-settings__unit">路 / 次</span>
              </div>
              <p v-if="settings.envControlled" class="download-settings__locked">
                已由环境变量 <code>COMIC_SHELF_MAX_CONCURRENT_DOWNLOADS</code> 锁定，界面不可改。
              </p>
            </template>
          </div>
        </div>

        <Transition name="message-fade">
          <div v-if="store.importMessage" class="import-message" role="status">
            {{ store.importMessage }}
          </div>
        </Transition>

        <ul v-if="warnings.length" class="import-warnings">
          <li v-for="warning in warnings" :key="warning">{{ warning }}</li>
        </ul>
      </div>
    </div>
  </section>
</template>

<style scoped>
.import-panel {
  display: grid;
  grid-template-columns: minmax(16rem, 1fr) minmax(21rem, 1.4fr);
  gap: var(--space-5) var(--space-6);
  padding: var(--space-6);
  border: 1px solid var(--line);
  border-radius: var(--radius-4);
  background: color-mix(in oklab, var(--paper-0) 78%, var(--paper-1));
  box-shadow: var(--shadow-2);
  transition:
    padding var(--duration-2) var(--ease-out),
    border-color var(--duration-2) var(--ease-out),
    border-radius var(--duration-2) var(--ease-out),
    background-color var(--duration-2) var(--ease-out),
    box-shadow var(--duration-2) var(--ease-out);
}

.import-info {
  display: flex;
  flex-direction: column;
}

.panel-tabs {
  display: inline-flex;
  gap: var(--space-1);
  margin-bottom: var(--space-4);
  padding: 0.25rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-1);
  align-self: flex-start;
}

.panel-tab {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 0.35rem 0.85rem;
  border: 0;
  border-radius: var(--radius-1);
  background: transparent;
  font-size: var(--text-xs);
  line-height: 1.2;
  color: var(--ink-1);
  cursor: pointer;
  transition: all var(--duration-1) var(--ease-out);
}

.panel-tab:hover:not(.is-active) {
  color: var(--ink-0);
}

.panel-tab.is-active {
  background: var(--paper-0);
  color: var(--accent-strong);
  font-weight: 600;
  box-shadow: var(--shadow-1);
}

.eyebrow {
  margin-bottom: var(--space-1);
}

.import-panel h2 {
  font-size: var(--text-2xl);
  font-family: var(--font-display);
  font-weight: 600;
  color: var(--ink-0);
  line-height: 1.2;
  white-space: nowrap;
}

.hint {
  margin-top: var(--space-3);
  max-width: 24rem;
  color: var(--ink-1);
  font-size: var(--text-sm);
  line-height: 1.6;
}

.import-controls {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  justify-content: center;
}

.import-form {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: var(--space-3);
  align-items: stretch;
}

.import-field {
  min-height: 7.2rem;
  padding: var(--space-4) var(--space-4);
  border: 1px solid var(--line);
  border-radius: var(--radius-3);
  background: var(--paper-0);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  transition:
    border-color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out);
}

.import-field:focus-within {
  border-color: var(--accent);
  box-shadow: 0 0 0 3px var(--accent-soft);
}

.field-prefix {
  font-family: var(--font-mono);
  font-size: var(--text-md);
  font-weight: 700;
  color: var(--accent);
  letter-spacing: 0.12em;
}

.import-field input {
  flex: 1;
  min-width: 0;
  border: 0;
  outline: 0;
  background: transparent;
  font-size: var(--text-md);
  color: var(--ink-0);
}

.import-submit-btn {
  width: 3.6rem;
  padding: var(--space-3) 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 0;
  border-radius: var(--radius-3);
  background: var(--accent);
  color: #fff8f2;
  cursor: pointer;
  user-select: none;
  transition:
    transform var(--duration-1) var(--ease-out),
    background-color var(--duration-1) var(--ease-out),
    box-shadow var(--duration-1) var(--ease-out),
    opacity var(--duration-1) var(--ease-out);
}

.vertical-text {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.22rem;
  font-size: var(--text-sm);
  font-weight: 600;
  line-height: 1.1;
  letter-spacing: normal;
}

.import-submit-btn:hover:not(:disabled) {
  background: var(--accent-strong);
  transform: translateY(-1px);
  box-shadow: var(--shadow-1);
}

.import-submit-btn:active:not(:disabled) {
  transform: translateY(0);
}

.import-submit-btn:disabled {
  cursor: not-allowed;
  opacity: 0.55;
  transform: none;
  box-shadow: none;
}

.workshop-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px dashed var(--line);
  border-radius: var(--radius-2);
  background: color-mix(in oklab, var(--paper-1) 35%, transparent);
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.workshop-hint {
  white-space: nowrap;
}

.workshop-btn {
  display: inline-flex;
  align-items: center;
  padding: 0.5rem 0.95rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-2);
  background: var(--paper-0);
  font-size: var(--text-xs);
  font-weight: 600;
  color: var(--accent-strong);
  white-space: nowrap;
  cursor: pointer;
  transition:
    background-color var(--duration-1) var(--ease-out),
    border-color var(--duration-1) var(--ease-out);
}

.workshop-btn:hover {
  background: var(--paper-1);
  border-color: var(--line-strong);
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
  display: grid;
  gap: var(--space-2);
  padding: var(--space-3) var(--space-4);
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
  border: 1px solid color-mix(in oklab, var(--success) 30%, transparent);
  border-radius: var(--radius-1);
  background: color-mix(in oklab, var(--success) 10%, transparent);
  color: var(--ink-1);
  font-size: var(--text-sm);
}

.message-fade-enter-active,
.message-fade-leave-active {
  transition: opacity var(--duration-2) var(--ease-out);
}

.message-fade-enter-from,
.message-fade-leave-to {
  opacity: 0;
}

.import-warnings {
  grid-column: 1 / -1;
  display: grid;
  gap: var(--space-1);
  color: var(--warning);
  font-size: var(--text-xs);
}

.mobile-collapse-bar {
  display: none;
}

.import-animator {
  display: contents;
}

.import-content {
  display: contents;
}

.collapse-chevron {
  transition: transform var(--duration-2) var(--ease-spring);
}

.collapse-chevron.is-rotated {
  transform: rotate(180deg);
}

@media (max-width: 760px) {
  .import-panel {
    grid-template-columns: 1fr;
    padding: var(--space-5);
  }

  .vertical-text {
    flex-direction: row;
    gap: 0.1rem;
  }

  .import-submit-btn {
    width: auto;
    min-height: 2.75rem;
    padding: 0.55rem 1.15rem;
  }

  .import-field {
    min-height: 3.25rem;
  }
}

@media (max-width: 640px) {
  .mobile-collapse-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 2.75rem;
    padding: var(--space-2) var(--space-3);
    background: transparent;
    border: 0;
    color: var(--accent-strong);
    cursor: pointer;
    font-family: var(--font-body);
    font-size: var(--text-sm);
    transition: padding var(--duration-2) var(--ease-out);
  }

  .mobile-collapse-lead {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1-5);
    font-weight: 600;
  }

  .mobile-collapse-action {
    display: inline-flex;
    align-items: center;
    gap: var(--space-1);
    font-size: var(--text-xs);
    color: var(--ink-2);
  }

  .import-panel {
    display: flex;
    flex-direction: column;
    padding: var(--space-3-5);
    gap: 0;
  }

  .import-panel.is-mobile-collapsed {
    padding: 0;
    border: 1px dashed color-mix(in oklab, var(--accent) 35%, var(--line));
    border-radius: var(--radius-2);
    background: color-mix(in oklab, var(--paper-1) 60%, var(--paper-0));
    box-shadow: none;
  }

  .import-panel:not(.is-mobile-collapsed) .mobile-collapse-bar {
    padding: 0 0 var(--space-2) 0;
    border-bottom: 1px dashed var(--line);
  }

  .import-animator {
    display: grid;
    grid-template-rows: 0fr;
    transition: grid-template-rows var(--duration-2) var(--ease-out);
  }

  .import-animator.is-expanded {
    grid-template-rows: 1fr;
  }

  .import-animator > .import-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-3-5);
    min-height: 0;
    overflow: clip;
    opacity: 0;
    transform: translateY(-4px);
    visibility: hidden;
    transition:
      visibility 0s var(--duration-2),
      opacity var(--duration-2) var(--ease-out),
      transform var(--duration-2) var(--ease-out),
      padding-top var(--duration-2) var(--ease-out);
  }

  .import-animator.is-expanded > .import-content {
    padding-top: var(--space-3);
    opacity: 1;
    transform: translateY(0);
    visibility: visible;
    transition:
      visibility 0s,
      opacity var(--duration-2) var(--ease-out),
      transform var(--duration-2) var(--ease-out),
      padding-top var(--duration-2) var(--ease-out);
  }
}
</style>
