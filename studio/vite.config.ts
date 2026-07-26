import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { execSync } from 'node:child_process'
import { dirname } from 'node:path'
import { fileURLToPath } from 'node:url'

// ESM 兼容：取当前配置文件所在目录
const __dirname = dirname(fileURLToPath(import.meta.url))

// 构建时注入短 commit hash 作为版本号，水印渲染用（便于用户判断自己拿到的是不是最新版）
// 优先级：Docker build arg 注入的 VITE_APP_VERSION > 本地 git rev-parse > dev
function resolveVersion(): string {
  const fromEnv = process.env.VITE_APP_VERSION
  if (fromEnv && fromEnv !== 'dev') return fromEnv
  try {
    return execSync('git rev-parse --short HEAD', { cwd: __dirname })
      .toString()
      .trim()
  } catch {
    return 'dev'
  }
}
const APP_VERSION = resolveVersion()

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
