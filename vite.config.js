import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // GitHub Pages 部署在 https://USER.github.io/pigmoney-web/，需要 base path
  base: '/pigmoney-web/',
  define: {
    // 打包時間戳注入前端，讓錯誤回報能確認線上跑的是哪一次 build
    __BUILD_TIME__: JSON.stringify(new Date().toISOString()),
  },
})
