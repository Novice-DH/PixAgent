/** 编辑器工具栏：标题内联编辑 + 画布尺寸/修订号 + 缩放组 + 图层开关。
 * 视图数值全部来自 canvasView store（tabular-nums 数字列）。 */
import { useRef, useState } from 'react'

import { useCanvasView, ZOOM_STEP } from '@/stores/canvasView'

interface EditorToolbarProps {
  title: string
  docWidth: number
  docHeight: number
  revision: number
  layersOpen: boolean
  /** 改名失败计数：每次 +1，输入框回退到服务端标题（未持久化的草稿不留存） */
  renameFailTick: number
  onRename: (title: string) => void
  onToggleLayers: () => void
  onFit: () => void
}

export default function EditorToolbar({
  title,
  docWidth,
  docHeight,
  revision,
  layersOpen,
  renameFailTick,
  onRename,
  onToggleLayers,
  onFit,
}: EditorToolbarProps) {
  // 视图状态按字段订阅：缩放百分比随 scale 更新，动作引用稳定
  const scale = useCanvasView((state) => state.scale)
  const zoomBy = useCanvasView((state) => state.zoomBy)
  const zoomTo = useCanvasView((state) => state.zoomTo)
  // value 跟随服务端标题（改名回包后同步）；cancelledRef 标记 Escape 还原，
  // 防止紧随其后的 blur 事件把草稿当提交
  const [value, setValue] = useState(title)
  const [lastTitle, setLastTitle] = useState(title)
  const [lastFailTick, setLastFailTick] = useState(renameFailTick)
  const cancelledRef = useRef(false)
  if (lastTitle !== title || lastFailTick !== renameFailTick) {
    // 渲染期同步 props → state（React 认可的模式，与 useRun 同款）
    setLastTitle(title)
    setLastFailTick(renameFailTick)
    setValue(title)
  }

  const commit = () => {
    const trimmed = value.trim()
    if (trimmed && trimmed !== title) {
      onRename(trimmed)
    } else {
      setValue(title)
    }
  }

  const handleKeyDown = (event: React.KeyboardEvent<HTMLInputElement>) => {
    if (event.key === 'Enter') {
      // 输入法组合态回车仅上屏不提交
      if (!event.nativeEvent.isComposing) {
        event.currentTarget.blur() // 触发 onBlur 提交
      }
      return
    }
    if (event.key === 'Escape') {
      cancelledRef.current = true
      setValue(title)
      event.currentTarget.blur()
    }
  }

  const handleBlur = () => {
    if (cancelledRef.current) {
      cancelledRef.current = false
      return
    }
    commit()
  }

  return (
    <div className="flex h-12 shrink-0 items-center gap-3 border-b border-line bg-paper px-4">
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        aria-label="会话标题"
        className="min-w-0 max-w-72 flex-1 rounded-control border border-transparent bg-transparent px-2 py-1 text-sm font-medium text-ink outline-none hover:border-line focus:border-brand"
      />

      <span className="shrink-0 text-xs text-muted tabular-nums">
        {docWidth}×{docHeight}
      </span>
      <span className="shrink-0 rounded-control bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand-strong tabular-nums">
        第 {revision} 版
      </span>

      <div className="ml-auto flex shrink-0 items-center gap-1">
        <button
          type="button"
          aria-label="缩小"
          onClick={() => zoomBy(1 / ZOOM_STEP)}
          className="rounded-control px-2 py-1 text-sm text-muted hover:bg-brand-soft hover:text-brand-strong"
        >
          −
        </button>
        <button
          type="button"
          onClick={() => zoomTo(1)}
          title="点击回到实际像素"
          className="min-w-14 rounded-control px-2 py-1 text-sm text-muted tabular-nums hover:bg-brand-soft hover:text-brand-strong"
        >
          {Math.round(scale * 100)}%
        </button>
        <button
          type="button"
          aria-label="放大"
          onClick={() => zoomBy(ZOOM_STEP)}
          className="rounded-control px-2 py-1 text-sm text-muted hover:bg-brand-soft hover:text-brand-strong"
        >
          ＋
        </button>
        <button
          type="button"
          onClick={onFit}
          className="rounded-control px-2 py-1 text-sm text-muted hover:bg-brand-soft hover:text-brand-strong"
        >
          适应
        </button>
        <button
          type="button"
          aria-pressed={layersOpen}
          onClick={onToggleLayers}
          className="ml-2 rounded-control px-3 py-1 text-sm text-muted hover:bg-brand-soft hover:text-brand-strong aria-pressed:bg-brand-soft aria-pressed:text-brand-strong"
        >
          图层
        </button>
      </div>
    </div>
  )
}
