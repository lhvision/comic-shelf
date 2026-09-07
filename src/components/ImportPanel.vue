<script setup lang="ts">
/**
 * @file ImportPanel.vue
 * @description 纸间作品收录与导入总控面板编排组件。
 *
 * 核心架构：
 * - 选项卡：远端车号收录（`ImportRemoteTab`） vs 本地自建/拆帧（`ImportLocalTab`）；
 * - 设置项：全站新入库默认对访客隐藏 + 下载并发步进器（`ImportConcurrencyStepper`）；
 * - 响应式折叠：移动端（≤640px）通过 VueUse `useMediaQuery` 驱动网格抽屉折叠与弹性展开过渡。
 */

import { computed, onMounted, ref, useId, watch } from 'vue'
import { useRouter } from 'vue-router'
import { useMediaQuery } from '@vueuse/core'
import { useLibraryStore } from '@/stores/library'
import { useAppSettings } from '@/stores/settings'
import { useToast } from '@/composables/useToast'
import { useViewTransition } from '@/composables/useViewTransition'
import { api } from '@/api/client'
import Tooltip from '@/components/Tooltip.vue'
import AppIcon from '@/components/AppIcon.vue'
import ImportRemoteTab from './import/ImportRemoteTab.vue'
import ImportLocalTab from './import/ImportLocalTab.vue'
import ImportConcurrencyStepper from './import/ImportConcurrencyStepper.vue'

const props = defineProps<{
  /**
   * 指定当前来源（'jm' | 'picacg' | 'local'）。
   * 若传入，面板锁定到该来源并隐藏内部二级 Tab；未传入则支持内部自主切换（保持向下兼容）。
   */
  source?: string
}>()

const emit = defineEmits<{
  /** 收录成功事件（向父级传递 source 与 sourceId） */
  imported: [source: string, sourceId: string]
}>()

const store = useLibraryStore()
const settings = useAppSettings()
const router = useRouter()
const { toast } = useToast()
const { withViewTransition } = useViewTransition()

const contentId = useId()
const isMobileExpanded = ref(false)
const isDesktop = useMediaQuery('(min-width: 640px)')

watch(isDesktop, (desktop) => {
  if (desktop && isMobileExpanded.value) {
    isMobileExpanded.value = false
  }
})

onMounted(() => {
  void settings.load()
})

const id = ref('')
const prefetchAll = ref(false)
const warnings = ref<string[]>([])

const activeTab = ref<'jm' | 'picacg' | 'local'>(
  props.source === 'jm' || props.source === 'picacg' || props.source === 'local'
    ? props.source
    : 'jm',
)

watch(
  () => props.source,
  (val) => {
    if (val === 'jm' || val === 'picacg' || val === 'local') {
      activeTab.value = val
    }
  },
)

const PANEL_TITLES: Record<string, string> = {
  jm: '收录禁漫车号',
  picacg: '收录哔咔画卷',
  local: '收录本地图集',
}

const PANEL_HINTS: Record<string, string> = {
  jm: '输入禁漫车号。首次收录会读取元数据并缓存前 4 页做封面；之后永远先读本地，不再打扰远端。',
  picacg: '输入哔咔 24 位 ID，或直接粘贴网页分享链接（如 picawang.com/comic/5ebe...）。',
  local: '输入服务器目录（如 public/tiya-frames）一键扫描收录，或进入工坊上传多图与多章节。',
}

const panelTitle = computed(() => PANEL_TITLES[activeTab.value] ?? '收录作品')
const panelHint = computed(() => PANEL_HINTS[activeTab.value] ?? '')
const mobileCollapseTitle = computed(() => PANEL_TITLES[activeTab.value] ?? '收录新作品 / 本地图集')

const localPath = ref('')
const localImporting = ref(false)

watch([id, localPath, activeTab], () => {
  if (store.importMessage) store.clearImportMessage()
  warnings.value = []
})

const canSubmitJm = computed(() => /^(?:JM)?\d{5,8}$/i.test(id.value.trim()))
const canSubmitPica = computed(() => /[0-9a-fA-F]{24}/.test(id.value.trim()))

async function submitRemote(source: 'jm' | 'picacg', btnEl: HTMLButtonElement | null) {
  const isValid = source === 'jm' ? canSubmitJm.value : canSubmitPica.value
  if (!isValid) return
  warnings.value = []
  try {
    const result = await withViewTransition(
      () =>
        store.importComic({
          id: id.value.trim(),
          source,
          prefetch_covers: 4,
          prefetch_all: prefetchAll.value,
        }),
      { element: btnEl },
    )
    warnings.value = result.warnings
    toast(store.importMessage, warnings.value.length ? 'error' : 'success')

    if (!result.from_cache) {
      emit('imported', result.meta.source, result.meta.source_id)
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

function decConcurrency(el: HTMLElement | null) {
  void withViewTransition(() => settings.dec(), { element: el })
}

function incConcurrency(el: HTMLElement | null) {
  void withViewTransition(() => settings.inc(), { element: el })
}
</script>

<template>
  <section
    class="import-panel"
    :class="{
      'is-mobile-collapsed': !isMobileExpanded,
      'is-source-locked': !!source,
    }"
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
        <span>{{ mobileCollapseTitle }}</span>
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

    <div
      :id="contentId"
      class="import-animator"
      :class="{ 'is-expanded': isMobileExpanded }"
      :inert="!isDesktop && !isMobileExpanded"
    >
      <div class="import-content">
        <div class="import-info">
          <div v-if="!source" class="panel-tabs">
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
              :class="{ 'is-active': activeTab === 'picacg' }"
              type="button"
              @click="activeTab = 'picacg'"
            >
              哔咔漫画
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

          <h2 id="import-title">{{ panelTitle }}</h2>
          <p class="hint">{{ panelHint }}</p>
        </div>

        <div class="import-controls">
          <!-- JM Tab Form -->
          <ImportRemoteTab
            v-if="activeTab === 'jm'"
            v-model:id="id"
            v-model:prefetch-all="prefetchAll"
            prefix="JM"
            placeholder="523607"
            aria-label="禁漫车号"
            inputmode="numeric"
            tooltip-id="cache-all-tip"
            tooltip-text="收录时直接把所有章节与页面下载到本地磁盘（适合整本离线保存）。不勾选则仅缓存前 4 页封面，后续页面在翻阅时按需秒级懒下载。"
            :importing="store.importing"
            :can-submit="canSubmitJm"
            @submit="(btnEl) => submitRemote('jm', btnEl)"
          />

          <!-- PicAcg Tab Form -->
          <ImportRemoteTab
            v-else-if="activeTab === 'picacg'"
            v-model:id="id"
            v-model:prefetch-all="prefetchAll"
            prefix="PICA"
            placeholder="5ebe89bf... 或粘贴网页链接"
            aria-label="哔咔车号或网页分享链接"
            tooltip-id="cache-all-pica-tip"
            tooltip-text="收录时直接把所有分卷与画页下载到本地磁盘（支持多分流自动容灾）。不勾选则仅预热前 4 页封面，后续页面在阅读时按需秒级懒下载。"
            :importing="store.importing"
            :can-submit="canSubmitPica"
            @submit="(btnEl) => submitRemote('picacg', btnEl)"
          />

          <!-- Local Tab Form -->
          <ImportLocalTab
            v-else
            v-model:local-path="localPath"
            :local-importing="localImporting"
            @submit="submitLocalPath"
            @workshop="goToWorkshop"
          />

          <div class="download-settings" :aria-busy="settings.loading">
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

            <!-- Concurrency Stepper (Remote tabs only) -->
            <ImportConcurrencyStepper
              v-if="activeTab === 'jm' || activeTab === 'picacg'"
              :concurrency="settings.concurrency"
              :min="settings.min"
              :max="settings.max"
              :loading="settings.loading"
              :env-controlled="settings.envControlled"
              @dec="decConcurrency"
              @inc="incConcurrency"
            />
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
  grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
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

/* 专属来源模式下，无内部二级 Tab，采用单列紧凑编排，避免中屏 (961~1180px) 发生列宽挤压与视口溢出 */
.import-panel.is-source-locked {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
  max-width: 32rem;
  justify-self: end;
  width: 100%;
}

.import-panel.is-source-locked .import-info h2 {
  font-size: var(--text-lg);
  font-weight: 600;
}

.import-panel.is-source-locked .import-info .hint {
  font-size: var(--text-xs);
  margin-top: var(--space-1);
  max-width: none;
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

.download-settings {
  display: flex;
  flex-direction: column;
  gap: var(--space-1-5);
  margin-top: var(--space-1);
  padding-top: var(--space-2);
  border-top: 1px dashed color-mix(in oklab, var(--line) 70%, transparent);
}

.download-settings__row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  min-height: 1.8rem;
}

.cache-check {
  display: inline-flex;
  align-items: center;
  gap: var(--space-2);
  cursor: pointer;
  user-select: none;
  font-size: var(--text-xs);
  color: var(--ink-1);
}

.cache-check input {
  accent-color: var(--accent);
  width: 14px;
  height: 14px;
}

.tooltip-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border: 0;
  background: transparent;
  color: var(--ink-2);
  cursor: pointer;
  padding: 2px;
  border-radius: var(--radius-1);
}

.tooltip-icon:hover {
  color: var(--accent);
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

.import-message {
  grid-column: 1 / -1;
  padding: var(--space-2) var(--space-3);
  border-radius: var(--radius-2);
  background: var(--paper-2);
  color: var(--ink-0);
  font-size: var(--text-xs);
}

.import-warnings {
  grid-column: 1 / -1;
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: var(--text-xs);
  color: var(--accent);
}

@media (max-width: 640px) {
  .import-panel {
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 0;
  }

  .mobile-collapse-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    width: 100%;
    min-height: 44px;
    padding: var(--space-2-5) var(--space-3);
    background: transparent;
    border: 0;
    cursor: pointer;
    font-size: var(--text-xs);
    color: var(--ink-0);
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
    font-size: var(--text-caption);
    color: var(--ink-2);
  }

  .collapse-chevron {
    transition: transform var(--duration-2) var(--ease-out);
  }

  .collapse-chevron.is-rotated {
    transform: rotate(180deg);
  }

  .import-animator {
    display: grid;
    grid-template-rows: 0fr;
    visibility: hidden;
    transition:
      grid-template-rows var(--duration-2) var(--ease-out),
      visibility var(--duration-2) var(--ease-out);
  }

  .import-animator.is-expanded {
    grid-template-rows: 1fr;
    visibility: visible;
  }

  .import-content {
    display: flex;
    flex-direction: column;
    gap: var(--space-4);
    overflow: hidden;
    padding: 0 var(--space-4) var(--space-4) var(--space-4);
  }

  .import-panel.is-mobile-collapsed .import-content {
    padding: 0;
  }
}
</style>
