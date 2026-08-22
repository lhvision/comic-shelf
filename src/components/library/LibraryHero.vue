<script setup lang="ts">
/**
 * 书架首屏（hero）—— 品牌文案 + 三项统计 + 收录入口（slot 内嵌 ImportPanel）。
 * 统计数字由父级计算好传入，本组件只负责排版与文案。
 */
withDefaults(
  defineProps<{
    bookCount: number
    cachedPages: number
    totalPages: number
  }>(),
  { bookCount: 0, cachedPages: 0, totalPages: 0 },
)
</script>

<template>
  <section class="hero container">
    <div class="hero-copy">
      <p class="eyebrow">Read · Keep · Revisit</p>
      <h1>读过的，<br />都收进纸间。</h1>
      <p class="hero-lede">
        纸间是私人漫画收藏夹：把看过的作品收进来，喜欢的打上标记，
        之后只从本地打开与重读，不再给漫画站添重复请求。
      </p>
      <div class="hero-stats" aria-label="书库统计">
        <div>
          <strong>{{ bookCount }}</strong>
          <span>本藏书</span>
        </div>
        <div>
          <strong>{{ cachedPages }}</strong>
          <span>页已本地化</span>
        </div>
        <div>
          <strong>{{ totalPages }}</strong>
          <span>页总藏量</span>
        </div>
      </div>
    </div>

    <!-- 收录面板由父级塞入，保持 ImportPanel 独立可复用 -->
    <slot name="import" class="hero-import" />
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

.hero-stats div {
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

@media (max-width: 560px) {
  .hero-stats {
    gap: var(--space-4);
  }
}
</style>
