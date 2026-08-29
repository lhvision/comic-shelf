import { registerSW } from 'virtual:pwa-register'

/**
 * 注册 PWA Service Worker 并配置周期性更新探测
 * 严格遵循 vite-plugin-pwa 官方与 W3C Service Worker 规范
 */
export function registerPwa(): void {
  if (typeof window === 'undefined' || !('serviceWorker' in navigator)) {
    return
  }

  // 每小时检查一次 Service Worker 脚本是否有更新
  const intervalMS = 60 * 60 * 1000

  registerSW({
    immediate: true,
    onRegisteredSW(swUrl, r) {
      if (r) {
        setInterval(async () => {
          if (!r.installing && navigator.onLine) {
            try {
              const resp = await fetch(swUrl, {
                method: 'GET',
                cache: 'no-store',
                headers: {
                  'cache-control': 'no-cache',
                },
              })
              if (resp?.status === 200) {
                await r.update()
              }
            } catch {
              // 离线/弱网环境下静默忽略网络错误
            }
          }
        }, intervalMS)
      }
    },
  })
}
