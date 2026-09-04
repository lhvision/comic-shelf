import { describe, it, expect, vi } from 'vite-plus/test'
import type { ViteDevServer } from 'vite'
import { illustrationsPlugin } from '../../plugins/illustrations'

describe('illustrationsPlugin', () => {
  const plugin = illustrationsPlugin()

  it('has correct plugin name', () => {
    expect(plugin.name).toBe('vite-plugin-illustrations')
  })

  it('resolves virtual:illustrations correctly', () => {
    const resolveId = plugin.resolveId as (id: string) => string | undefined
    expect(resolveId('virtual:illustrations')).toBe('\0virtual:illustrations')
    expect(resolveId('some-other-module')).toBeUndefined()
  })

  it('loads virtual module without calling addWatchFile', () => {
    const addWatchFileMock = vi.fn<() => void>()
    const context = {
      addWatchFile: addWatchFileMock,
    }
    const load = plugin.load as (this: unknown, id: string) => string | undefined
    const result = load.call(context, '\0virtual:illustrations')

    expect(result).toBeDefined()
    expect(result).toContain('export const illustrations = [')
    expect(result).toContain('/loading-1.webp')
    // Crucial: addWatchFile must NOT be called in load to avoid Vite import-analysis directory panic
    expect(addWatchFileMock).not.toHaveBeenCalled()
  })

  it('registers file change listener in configureServer', () => {
    const onMock = vi.fn<() => void>()
    const fakeServer = {
      watcher: {
        on: onMock,
      },
      environments: {
        client: {
          moduleGraph: {
            getModuleById: vi.fn<() => null>(),
            invalidateModule: vi.fn<() => void>(),
          },
        },
      },
      moduleGraph: {
        getModuleById: vi.fn<() => null>(),
        invalidateModule: vi.fn<() => void>(),
      },
      ws: {
        send: vi.fn<() => void>(),
      },
    } as unknown as ViteDevServer

    const configureServer = plugin.configureServer as (server: ViteDevServer) => void
    configureServer(fakeServer)

    expect(onMock).toHaveBeenCalledWith('add', expect.any(Function))
    expect(onMock).toHaveBeenCalledWith('unlink', expect.any(Function))
    expect(onMock).toHaveBeenCalledWith('change', expect.any(Function))
  })
})
