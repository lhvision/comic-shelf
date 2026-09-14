import { fileURLToPath } from 'node:url'
import { mergeConfig, defineConfig, configDefaults } from 'vite-plus'
import viteConfig from './vite.config'

export default mergeConfig(
  viteConfig,
  defineConfig({
    test: {
      environment: 'jsdom',
      exclude: [...configDefaults.exclude, 'e2e/**'],
      root: fileURLToPath(new URL('./', import.meta.url)),
      alias: {
        vue: 'vue/dist/vue.runtime-with-vapor.esm-browser.js',
      },
      server: {
        deps: {
          inline: [/vue/],
        },
      },
    },
  }),
)
