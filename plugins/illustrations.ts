import fs from 'node:fs'
import { fileURLToPath, URL } from 'node:url'
import type { Plugin } from 'vite'

/**
 * 插画池虚拟模块插件。
 *
 * 职责：
 * 编译期自动扫描 public/ 目录下的 loading-*.webp 文件名生成路径数组，
 * 避免 import.meta.glob 将多媒体资产重复打包至 assets/ 并双重注入预缓存。
 */
export function illustrationsPlugin(): Plugin {
  const virtualModuleId = 'virtual:illustrations'
  const resolvedVirtualModuleId = '\0' + virtualModuleId

  return {
    name: 'vite-plugin-illustrations',
    resolveId(id: string) {
      if (id === virtualModuleId) {
        return resolvedVirtualModuleId
      }
    },
    load(id: string) {
      if (id === resolvedVirtualModuleId) {
        const publicDir = fileURLToPath(new URL('../public', import.meta.url))
        if (!process.env.VITEST && typeof this.addWatchFile === 'function') {
          this.addWatchFile(publicDir)
        }
        const files = fs.existsSync(publicDir)
          ? fs
              .readdirSync(publicDir)
              .filter((f) => /^loading-.*\.(webp|png|jpg|jpeg)$/i.test(f))
              .sort((a, b) => a.localeCompare(b, undefined, { numeric: true }))
              .map((f) => `/${f}`)
          : []
        return `export const illustrations = ${JSON.stringify(files)};`
      }
    },
  }
}
