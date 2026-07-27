import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
  version?: string
}

interface State {
  hasError: boolean
  message?: string
}

/**
 * 全局渲染兜底。任何子树渲染期抛错都显示可读面板，绝不留下空白 #root。
 *
 * 战略背景：白屏 = 对外通信中断（杜总战略底线）。因此：
 *  - 兜底 UI 必须是纯 DOM（不引入 hooks / 子组件），自身不能再抛错，否则会二次卸载变白屏。
 *  - 提供「重新加载」按钮，让用户一键自愈，而不是卡死在空白页。
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, message: error?.message || String(error) }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // 仅记录，绝不向外界再抛，避免二次崩溃整树卸载。
    try {
      // eslint-disable-next-line no-console
      console.error('[ErrorBoundary] render error caught:', error, info.componentStack)
    } catch {
      /* 忽略日志异常 */
    }
  }

  private reload = () => {
    // 清掉 chunk 重试标记，确保重新加载是干净的一次
    try {
      sessionStorage.removeItem('zhiyan_chunk_reload')
    } catch {
      /* ignore */
    }
    window.location.reload()
  }

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 14,
            padding: 24,
            background: '#f8fafc',
            fontFamily:
              "system-ui,-apple-system,'Segoe UI',Roboto,'PingFang SC','Microsoft YaHei',sans-serif",
            color: '#475569',
            textAlign: 'center',
          }}
        >
          <div style={{ fontSize: 18, fontWeight: 600, color: '#0f172a' }}>
            智衍 EvolvIQ · 页面遇到一点问题
          </div>
          <div style={{ fontSize: 14, maxWidth: 420, lineHeight: 1.6 }}>
            系统仍在运行。点击下方按钮即可恢复；如持续出现，请刷新页面或联系技术支持。
          </div>
          <button
            onClick={this.reload}
            style={{
              marginTop: 4,
              padding: '10px 22px',
              fontSize: 14,
              fontWeight: 600,
              color: '#fff',
              background: '#2563eb',
              border: 'none',
              borderRadius: 8,
              cursor: 'pointer',
            }}
          >
            重新加载
          </button>
          <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'ui-monospace,Menlo,Consolas,monospace' }}>
            build: {this.props.version || 'unknown'}
          </div>
        </div>
      )
    }
    return this.props.children
  }
}
