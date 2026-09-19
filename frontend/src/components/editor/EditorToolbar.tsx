/** 编辑器工具栏：标题 + 画布尺寸 + 修图工具组（裁剪/翻转/去背景/调色）+ 撤销重做/对比/缩放/图层。
 * 进入裁剪态后左侧整组切换为比例按钮 + 确定/取消；统一 ToolButton（aria-pressed、busy 禁用）。 */
import { useRef, useState } from 'react'

import { useCanvasView, ZOOM_STEP } from '@/stores/canvasView'
import type { CropRatio } from '@/stores/editorUi'

interface ToolAction {
  busy: boolean
  canUndo: boolean
  canRedo: boolean
  hasPrevious: boolean
}

interface EditorToolbarProps {
  title: string
  docWidth: number
  docHeight: number
  revision: number
  /** 改名失败计数：每次 +1，输入框回退到服务端标题（未持久化的草稿不留存） */
  renameFailTick: number
  onRename: (title: string) => void
  onFit: () => void
  action: ToolAction
  cropOpen: boolean
  cropRatio: CropRatio
  adjustOpen: boolean
  layersOpen: boolean
  compareOpen: boolean
  onFlipHorizontal: () => void
  onFlipVertical: () => void
  onRemoveBackground: () => void
  onToggleAdjust: () => void
  onToggleLayers: () => void
  onUndo: () => void
  onRedo: () => void
  onToggleCompare: () => void
  onEnterCrop: () => void
  onCropRatio: (ratio: CropRatio) => void
  onCropConfirm: () => void
  onCropCancel: () => void
}

function ToolButton({
  label,
  onClick,
  pressed = false,
  disabled = false,
  title,
}: {
  label: string
  onClick: () => void
  pressed?: boolean
  disabled?: boolean
  title?: string
}) {
  return (
    <button
      type="button"
      aria-pressed={pressed}
      title={title ?? label}
      disabled={disabled}
      onClick={onClick}
      className="rounded-control px-2.5 py-1 text-sm text-muted transition-colors hover:bg-brand-soft hover:text-brand-strong aria-pressed:bg-brand-soft aria-pressed:text-brand-strong disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted"
    >
      {label}
    </button>
  )
}

const RATIO_BUTTONS: readonly Exclude<CropRatio, 'free'>[] = ['1:1', '4:5', '9:16', '16:9']

export default function EditorToolbar({
  title,
  docWidth,
  docHeight,
  revision,
  renameFailTick,
  onRename,
  onFit,
  action,
  cropOpen,
  cropRatio,
  adjustOpen,
  layersOpen,
  compareOpen,
  onFlipHorizontal,
  onFlipVertical,
  onRemoveBackground,
  onToggleAdjust,
  onToggleLayers,
  onUndo,
  onRedo,
  onToggleCompare,
  onEnterCrop,
  onCropRatio,
  onCropConfirm,
  onCropCancel,
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
    <div className="flex h-12 shrink-0 items-center gap-2 border-b border-line bg-paper px-4">
      <input
        value={value}
        onChange={(event) => setValue(event.target.value)}
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        aria-label="会话标题"
        className="w-40 min-w-0 shrink-0 rounded-control border border-transparent bg-transparent px-2 py-1 text-sm font-medium text-ink outline-none hover:border-line focus:border-brand"
      />

      <span className="hidden shrink-0 text-xs text-muted tabular-nums sm:inline">
        {docWidth}×{docHeight}
      </span>
      <span className="hidden shrink-0 rounded-control bg-brand-soft px-2 py-0.5 text-xs font-medium text-brand-strong tabular-nums md:inline">
        第 {revision} 版
      </span>

      <div className="ml-2 flex shrink-0 items-center gap-0.5 border-l border-line pl-3">
        {cropOpen ? (
          <>
            <ToolButton
              label="自由"
              pressed={cropRatio === 'free'}
              onClick={() => onCropRatio('free')}
            />
            {RATIO_BUTTONS.map((ratio) => (
              <ToolButton
                key={ratio}
                label={ratio}
                pressed={cropRatio === ratio}
                onClick={() => onCropRatio(ratio)}
              />
            ))}
            <ToolButton label="确定" onClick={onCropConfirm} title="应用裁剪" />
            <ToolButton label="取消" onClick={onCropCancel} />
          </>
        ) : (
          <>
            <ToolButton label="裁剪" onClick={onEnterCrop} />
            <ToolButton label="水平翻转" onClick={onFlipHorizontal} disabled={action.busy} />
            <ToolButton label="垂直翻转" onClick={onFlipVertical} disabled={action.busy} />
            <ToolButton label="去背景" onClick={onRemoveBackground} disabled={action.busy} />
            <ToolButton
              label="调色"
              pressed={adjustOpen}
              onClick={onToggleAdjust}
              disabled={action.busy}
            />
          </>
        )}
      </div>

      <div className="ml-auto flex shrink-0 items-center gap-0.5">
        <ToolButton label="撤销" onClick={onUndo} disabled={action.busy || !action.canUndo} />
        <ToolButton label="重做" onClick={onRedo} disabled={action.busy || !action.canRedo} />
        <ToolButton
          label="对比"
          pressed={compareOpen}
          onClick={onToggleCompare}
          disabled={!action.hasPrevious}
        />
        <div className="mx-1 h-5 w-px bg-line" />
        <ToolButton label="−" onClick={() => zoomBy(1 / ZOOM_STEP)} title="缩小" />
        <ToolButton label={`${Math.round(scale * 100)}%`} onClick={() => zoomTo(1)} title="点击回到实际像素" />
        <ToolButton label="＋" onClick={() => zoomBy(ZOOM_STEP)} title="放大" />
        <ToolButton label="适应" onClick={onFit} />
        <ToolButton label="图层" pressed={layersOpen} onClick={onToggleLayers} />
      </div>
    </div>
  )
}
