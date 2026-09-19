/** 画布情境提示（画布顶部居中浮层，覆盖式不推动画布）：busy 进度 / 裁剪指引 / 对比指引三态。
 * pointer-events-none 不挡画布交互；animate-pop 入场。进度条视觉最小 4% 纪律保持。 */
const MIN_PROGRESS_PERCENT = 4

interface CanvasHintProps {
  busyStage: string | null
  busyProgress: number
  cropOpen: boolean
  compareOpen: boolean
}

export default function CanvasHint({ busyStage, busyProgress, cropOpen, compareOpen }: CanvasHintProps) {
  if (busyStage !== null) {
    return (
      <div
        role="status"
        aria-live="polite"
        className="pointer-events-none absolute left-1/2 top-3 z-10 w-64 max-w-[80%] -translate-x-1/2 animate-pop rounded-control bg-ink/85 px-3 py-1.5 text-xs text-paper"
      >
        <div className="mb-1 flex justify-between tabular-nums">
          <span>{busyStage}</span>
          <span>{Math.max(MIN_PROGRESS_PERCENT, busyProgress)}%</span>
        </div>
        <div className="h-1 overflow-hidden rounded-full bg-paper/25">
          <div
            className="h-full rounded-full bg-accent transition-[width]"
            style={{ width: `${Math.max(MIN_PROGRESS_PERCENT, busyProgress)}%` }}
          />
        </div>
      </div>
    )
  }

  if (cropOpen) {
    return (
      <p
        role="status"
        className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 animate-pop rounded-control bg-ink/85 px-3 py-1.5 text-xs text-paper"
      >
        拖动或缩放裁剪框，越界自动弹回；工具栏「确定」后生效
      </p>
    )
  }

  if (compareOpen) {
    return (
      <p
        role="status"
        className="pointer-events-none absolute left-1/2 top-3 z-10 -translate-x-1/2 animate-pop rounded-control bg-ink/85 px-3 py-1.5 text-xs text-paper"
      >
        左右拖动圆点对比修改前后
      </p>
    )
  }

  return null
}
