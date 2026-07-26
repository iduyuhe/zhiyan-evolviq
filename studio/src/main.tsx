import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App'
import { TenantProvider } from './tenant/TenantContext'

// 注入构建版本水印（即使 React 渲染失败，DOM 上仍可看到）
declare const __APP_VERSION__: string
const marker = document.getElementById('zhiyan-build-marker')
if (marker) {
  const ver = typeof __APP_VERSION__ !== 'undefined' ? __APP_VERSION__ : 'unknown'
  marker.textContent = `build: ${ver}`
  marker.setAttribute('data-version', ver)
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <TenantProvider>
      <App />
    </TenantProvider>
  </StrictMode>,
)
