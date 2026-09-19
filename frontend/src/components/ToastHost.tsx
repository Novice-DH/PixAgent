/** 全局 toast 渲染：底部居中悬浮层。容器 pointer-events-none 不挡画布操作，
 * 单条 toast pointer-events-auto 可点击关闭；danger 红底 / ok 墨底。 */
import { useToasts } from '@/stores/toasts'

export default function ToastHost() {
  const toasts = useToasts((state) => state.toasts)
  const close = useToasts((state) => state.close)
  if (toasts.length === 0) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="pointer-events-none fixed bottom-6 left-1/2 z-50 flex -translate-x-1/2 flex-col items-center gap-2"
    >
      {toasts.map((item) => (
        <button
          key={item.id}
          type="button"
          onClick={() => close(item.id)}
          title="点击关闭"
          className={`pointer-events-auto rounded-control px-4 py-2 text-sm font-medium shadow-panel ${
            item.leaving ? 'animate-fade-out' : 'animate-pop'
          } ${
            item.tone === 'danger'
              ? 'bg-danger text-paper'
              : 'bg-dark text-paper'
          }`}
        >
          {item.text}
        </button>
      ))}
    </div>
  )
}
