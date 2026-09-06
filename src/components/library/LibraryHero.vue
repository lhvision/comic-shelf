<script setup lang="ts">
/**
 * 书架首屏（hero）—— 品牌文案 + 三项统计 + 来源快捷入口 / 专属收录入口。
 * 统计数字与当前来源由父级传入，本组件负责排版、文案与来源快捷导航。
 */
import { computed } from 'vue'
import AppIcon from '@/components/AppIcon.vue'

const props = withDefaults(
  defineProps<{
    bookCount: number
    cachedPages: number
    totalPages: number
    activeSource?: string
    canWrite?: boolean
    providers?: Array<{ key: string; label: string; short_label?: string }>
  }>(),
  {
    bookCount: 0,
    cachedPages: 0,
    totalPages: 0,
    activeSource: '',
    canWrite: false,
    providers: () => [
      { key: 'jm', label: '禁漫', short_label: '禁漫' },
      { key: 'picacg', label: '哔咔', short_label: '哔咔' },
      { key: 'local', label: '本地', short_label: '本地' },
    ],
  },
)

const SOURCE_HERO_TITLES: Record<string, string> = {
  jm: '禁漫藏卷，\n入册安放。',
  picacg: '哔咔画集，\n纸间定格。',
  local: '本地原卷，\n工坊自裁。',
}

const SOURCE_HERO_LEDES: Record<string, string> = {
  jm: '集中整理禁漫车号藏卷，按需预热封面与分页画卷；离线化后随时重阅，断绝远端网络波动。',
  picacg: '收录哔咔分卷与原画，多 CDN 容灾分流；本地优先存储，告别网页打不开与加载中断。',
  local:
    '扫描服务器本地目录或拆帧图集，自由装订多卷；完全属于你个人的离线画室，不依赖任何外部网络。',
}

const heroTitle = computed(() => SOURCE_HERO_TITLES[props.activeSource] ?? '读过的，\n都收进纸间。')
const heroLede = computed(
  () =>
    SOURCE_HERO_LEDES[props.activeSource] ??
    '纸间是私人漫画收藏夹：把看过的作品收进来，喜欢的打上标记，之后只从本地打开与重读，不再给漫画站添重复请求。',
)
</script>

<template>
  <section class="hero container" :class="{ 'hero--single': !$slots.import }">
    <div class="hero-copy">
      <!-- 处于单源收录模式时，提供清晰的返回逃生通道 -->
      <div v-if="activeSource" class="hero-source-breadcrumb">
        <router-link to="/" class="hero-back-link">
          <AppIcon name="arrow-left" size="xs" />
          <span>返回全部藏书</span>
        </router-link>
      </div>

      <h1>
        <template v-for="(line, idx) in heroTitle.split('\n')" :key="idx">
          {{ line }}<br v-if="idx === 0" class="hero-br" />
        </template>
      </h1>
      <p class="hero-lede">{{ heroLede }}</p>
      <div class="hero-stats" aria-label="书库统计">
        <div class="hero-stat-item">
          <strong>{{ bookCount }}</strong>
          <span>本藏书</span>
        </div>
        <div class="hero-stat-item">
          <strong>{{ cachedPages }}</strong>
          <span>页已本地化</span>
        </div>
        <div class="hero-stat-item">
          <strong>{{ totalPages }}</strong>
          <span>页总藏量</span>
        </div>
      </div>

      <!-- 全部视图下的轻量快捷收录入口 -->
      <div v-if="!activeSource && canWrite && providers.length" class="hero-source-actions">
        <span class="hero-source-label">录入新卷：</span>
        <div class="hero-source-group">
          <router-link
            v-for="provider in providers"
            :key="provider.key"
            :to="`/?source=${provider.key}`"
            class="hero-source-pill"
          >
            <AppIcon name="plus" size="xs" />
            <span>{{ provider.short_label || provider.label }}</span>
          </router-link>
        </div>
      </div>
    </div>

    <!-- 收录面板由父级塞入，保持 ImportPanel 独立可复用 -->
    <slot name="import" />
  </section>
</template>

<style scoped>
.hero {
  display: grid;
  grid-template-columns: minmax(17rem, 0.85fr) minmax(22rem, 1.35fr);
  gap: var(--space-8);
  align-items: center;
  padding-block: var(--space-10) var(--space-8);
}

.hero.hero--single {
  grid-template-columns: 1fr;
  max-width: 48rem;
  padding-block: var(--space-8) var(--space-6);
}

.hero h1 {
  font-size: var(--text-3xl);
  letter-spacing: 0.01em;
}

.hero-lede {
  max-width: 38rem;
  margin-top: var(--space-4);
  color: var(--ink-1);
}

.hero-stats {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-6);
  margin-top: var(--space-6);
  padding-top: var(--space-4);
  border-top: 1px solid var(--line);
}

.hero-stats .hero-stat-item {
  display: grid;
  gap: 0.1rem;
}

.hero-stats strong {
  font-family: var(--font-display);
  font-size: var(--text-lg);
  line-height: 1.1;
  color: var(--accent-strong);
}

.hero-stats span {
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
}

@media (max-width: 960px) {
  .hero {
    grid-template-columns: 1fr;
    padding-block: var(--space-8) var(--space-6);
  }
}

@media (max-width: 640px) {
  .hero {
    padding-block: var(--space-4) var(--space-2);
    gap: var(--space-3);
  }

  .hero.hero--single {
    padding-block: var(--space-4) var(--space-2);
  }

  .hero .eyebrow,
  .hero-lede {
    display: none;
  }

  .hero h1 {
    font-size: var(--text-md);
    line-height: 1.25;
    letter-spacing: 0.02em;
  }

  .hero-br {
    display: none;
  }

  .hero-stats {
    display: flex;
    flex-direction: row;
    flex-wrap: wrap;
    align-items: baseline;
    gap: var(--space-3);
    margin-top: var(--space-2);
    padding-top: 0;
    border-top: none;
  }

  .hero-stats .hero-stat-item {
    display: inline-flex;
    align-items: baseline;
    gap: 0.25rem;
  }

  .hero-stats strong {
    font-size: var(--text-md);
  }

  .hero-stats span {
    font-size: var(--text-caption);
  }

  .hero-source-actions {
    margin-top: var(--space-3);
    gap: var(--space-1-5);
  }

  .hero-source-pill {
    padding: 0.5rem 0.85rem;
    min-height: 44px;
    box-sizing: border-box;
  }
}

.hero-source-breadcrumb {
  margin-bottom: var(--space-3);
}

.hero-back-link {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  font-family: var(--font-mono);
  font-size: var(--text-xs);
  color: var(--ink-2);
  text-decoration: none;
  transition: color var(--duration-1) var(--ease-out);
}

.hero-back-link:hover {
  color: var(--accent-strong);
}

.hero-back-link:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}

.hero-source-actions {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-top: var(--space-4);
  font-size: var(--text-xs);
}

.hero-source-label {
  color: var(--ink-2);
  font-family: var(--font-mono);
  user-select: none;
}

.hero-source-group {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.hero-source-pill {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 0.25rem 0.65rem;
  border: 1px solid var(--line);
  border-radius: var(--radius-pill);
  background: color-mix(in oklab, var(--paper-0) 70%, var(--paper-1));
  color: var(--ink-1);
  text-decoration: none;
  font-size: var(--text-xs);
  line-height: 1.2;
  transition: all var(--duration-1) var(--ease-out);
}

.hero-source-pill:hover {
  border-color: var(--accent);
  color: var(--accent-strong);
  background: var(--paper-0);
  box-shadow: var(--shadow-1);
}

.hero-source-pill:focus-visible {
  outline: 2px solid var(--accent);
  outline-offset: 2px;
}
</style>
