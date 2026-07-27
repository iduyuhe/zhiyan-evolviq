/**
 * 运行期兜底守卫。在 React 挂载前 / 后的全局错误、动态 chunk 加载失败，
 * 都转化为「自动恢复」而非白屏。
 *
 * 战略背景：白屏 = 对外通信中断（杜总战略底线），绝不接受。
 * 本模块只做两件事：
 *   1) 动态 import 的 chunk 加载失败（典型：部署后旧 HTML 指向已删除的 hash bundle）→
 *      自动整页重载一次（带去重标记，避免死循环），多数情况刷新即得新 bundle。
 *   2) 其它全局 JS 错误 / 未处理 rejection → 仅记录，不抛出、不空白（渲染期错误由 ErrorBoundary 兜底）。
 */

const RELOAD_FLAG = 'zhiyan_chunk_reload'

function isChunkError(msg?: string): boolean {
  if (!msg) return false
  return (
    msg.includes('Failed to fetch dynamically imported module') ||
    msg.includes('Importing a module script failed') ||
    msg.includes('Failed to resolve module specifier') ||
    msg.includes('error loading dynamically imported module') ||
    msg.includes('Failed to load module script')
  )
}

function safeReload() {
  try {
    if (sessionStorage.getItem(RELOAD_FLAG)) return // 已经重试过，避免刷新死循环
    sessionStorage.setItem(RELOAD_FLAG, '1')
  } catch {
    /* sessionStorage 不可用时直接放行重载 */
  }
  // 注意：用 location.reload 而非 location.href=，避免附加查询参数污染
  window.location.reload()
}

export function installRuntimeGuard() {
  if (typeof window === 'undefined') return

  window.addEventListener(
    'error',
    (e: ErrorEvent) => {
      // 资源加载失败（script / link 404 等）视为可恢复，自动重载一次
      const target = e.target as unknown as { tagName?: string } | null
      if (target && (target.tagName === 'SCRIPT' || target.tagName === 'LINK')) {
        safeReload()
        return
      }
      if (isChunkError(e.message)) {
        safeReload()
        return
      }
      // 其它 JS 错误：仅记录（不抛、不空白）
      // eslint-disable-next-line no-console
      console.error('[runtimeGuard] window error:', e.message)
    },
    true,
  )

  window.addEventListener('unhandledrejection', (e: PromiseRejectionEvent) => {
    const reason = e.reason as { message?: string } | string | undefined
    const msg = (reason && typeof reason === 'object' ? reason.message : String(reason)) || ''
    if (isChunkError(msg)) {
      safeReload()
      return
    }
    // eslint-disable-next-line no-console
    console.error('[runtimeGuard] unhandled rejection:', msg)
  })
}
