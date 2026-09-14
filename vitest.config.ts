import { fileURLToPath } from 'node:url'
import path from 'node:path'
import { createRequire } from 'node:module'
import { mergeConfig, defineConfig, configDefaults } from 'vite-plus'
import viteConfig from './vite.config'

const require = createRequire(import.meta.url)
const vueReq = createRequire(require.resolve('vue'))
const testUtilsPkg = require.resolve('@vue/test-utils/package.json')

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      alias: {
        '@vue/test-utils': path.resolve(
          path.dirname(testUtilsPkg),
          'dist/vue-test-utils.esm-bundler.mjs',
        ),
        vue: require.resolve('vue/dist/vue.esm-bundler.js'),
        '@vue/runtime-dom': vueReq
          .resolve('@vue/runtime-dom')
          .replace(/index\.js$/, 'dist/runtime-dom.esm-bundler.js'),
        '@vue/runtime-core': vueReq
          .resolve('@vue/runtime-core')
          .replace(/index\.js$/, 'dist/runtime-core.esm-bundler.js'),
        '@vue/reactivity': vueReq
          .resolve('@vue/reactivity')
          .replace(/index\.js$/, 'dist/reactivity.esm-bundler.js'),
        '@vue/shared': vueReq
          .resolve('@vue/shared')
          .replace(/index\.js$/, 'dist/shared.esm-bundler.js'),
        '@vue/server-renderer': vueReq
          .resolve('@vue/server-renderer')
          .replace(/index\.js$/, 'dist/server-renderer.esm-bundler.js'),
        '@vue/runtime-vapor': vueReq.resolve('@vue/runtime-vapor'),
      },
      server: {
        deps: {
          inline: [/@vue/, /vue/],
        },
      },
    },
  }),
)
