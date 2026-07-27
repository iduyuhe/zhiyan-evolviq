import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { TenantProvider } from './tenant/TenantContext'
import { ErrorBoundary } from './components/ErrorBoundary'
import { installRuntimeGuard } from './lib/runtimeGuard'

// 注入构建版本水印（即使 React 渲染失败，DOM 上仍可看到）
declare const __APP_VERSION__: string
const version = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : 'unknown'

// 运行期兜底守卫：全局错误 / 动态 chunk 加载失败 → 自动恢复一次，杜绝白屏。
// 白屏 = 对外通信中断（战略底线），必须在渲染前装好。
installRuntimeGuard()

const marker = document.getElementById('zhiyan-build-marker')
if (marker) {
  marker.textContent = `build: ${version}`
  marker.setAttribute('data-version', version)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ErrorBoundary version={version}>
      <TenantProvider>
        <App />
      </TenantProvider>
    </ErrorBoundary>
  </StrictMode>,
)
