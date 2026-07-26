import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'node:child_process'

// 构建时注入短 commit hash 作为版本号，水印渲染用（便于用户判断自己拿到的是不是最新版）
function shortSha(): string {
  try {
    return execSync('git rev-parse --short HEAD', { cwd: __dirname })
      .toString()
      .trim()
  } catch {
    return 'dev'
  }
}
const APP_VERSION = shortSha()

export default defineConfig({
  define: {
    __APP_VERSION__: JSON.stringify(APP_VERSION),
  },
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
