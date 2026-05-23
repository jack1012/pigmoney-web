import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [vue(), tailwindcss()],
  // GitHub Pages 部署在 https://USER.github.io/pigmoney-web/，需要 base path
  base: '/pigmoney-web/',
})
