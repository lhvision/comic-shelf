import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import type { Plugin } from 'vite'

/**
 * 插画池虚拟模块插件。
 *
 * 职责：
 * 编译期自动扫描 public/ 目录下的 loading-*.webp 文件名生成路径数组，
 * 避免 import.meta.glob 将多媒体资产重复打包至 assets/ 并双重注入预缓存。
 *
 * 注意：
 * 在 Vite 开发服务环境下，严禁在 load() 中调用 this.addWatchFile(publicDir)，
 * 否则 Vite 会将非模块的目录路径推入 _addedImports 并尝试通过 import-analysis 解析，
 * 抛出 Failed to resolve import from virtual:illustrations 严重错误。
 * 目录与静态资产的文件监听统一在 configureServer(server) 中通过 server.watcher 接管。
 */
export function illustrationsPlugin(): Plugin {
  const virtualModuleId = 'virtual:illustrations'
  const resolvedVirtualModuleId = '\0' + virtualModuleId

  function getPublicDir(): string {
    try {
      const url = new URL('../public', import.meta.url)
      if (url.protocol === 'file:') {
        return fileURLToPath(url)
      }
    } catch {
      // Fallback for non-file URLs or parsing failures
    }
    return path.resolve(process.cwd(), 'public')
  }

  return {
    name: 'vite-plugin-illustrations',
    resolveId(id: string) {
      if (id === virtualModuleId) {
        return resolvedVirtualModuleId
      }
    },
    load(id: string) {
      if (id === resolvedVirtualModuleId) {
        const publicDir = getPublicDir()
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
    configureServer(server) {
      const publicDir = getPublicDir()
      const isIllustration = (file: string) =>
        file.startsWith(publicDir) && /^loading-.*\.(webp|png|jpg|jpeg)$/i.test(path.basename(file))

      const handleFileChange = (file: string) => {
        if (!isIllustration(file)) return
        const clientGraph = server.environments?.client?.moduleGraph
        if (clientGraph) {
          const mod = clientGraph.getModuleById(resolvedVirtualModuleId)
          if (mod) clientGraph.invalidateModule(mod)
        } else {
          const mod = server.moduleGraph.getModuleById(resolvedVirtualModuleId)
          if (mod) server.moduleGraph.invalidateModule(mod)
        }
        server.ws.send({
          type: 'full-reload',
          path: '*',
        })
      }

      server.watcher.on('add', handleFileChange)
      server.watcher.on('unlink', handleFileChange)
      server.watcher.on('change', handleFileChange)
    },
  }
}
