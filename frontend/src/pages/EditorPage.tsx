/** 编辑器页：会话侧栏 + 工具栏 + 画布 + 图片墙 + 右栏面板。
 * 满高应用式布局：根部直接用 h-screen 建立高度链（WorkbenchLayout 内容区由
 * min-h-screen 拉伸而来，百分比高度链解析不可靠），页面级不出现滚动条，
 * 滚动只发生在侧栏/面板/墙内部。
 * 全局键盘：Cmd/Ctrl+Z 撤销、+Shift 或 +Y 重做、Escape 关裁剪/对比；
 * 焦点在 input/textarea 时全部跳过（快捷键吞输入是演示现场事故）。 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import CanvasStage from '@/components/editor/CanvasStage'
import EditorToolbar from '@/components/editor/EditorToolbar'
import ImageWall from '@/components/editor/ImageWall'
import LayerPanel from '@/components/editor/LayerPanel'
import SessionSidebar from '@/components/editor/SessionSidebar'
import { ApiError } from '@/api/client'
import { useCanvasView } from '@/stores/canvasView'
import { useEditorUi } from '@/stores/editorUi'
import { errorMessage } from '@/hooks/useAuth'
import {
  usePatchSession,
  useSession,
  useSessionHistory,
  useSessionTools,
} from '@/hooks/useSessions'

function isTypingTarget(target: EventTarget | null): boolean {
  return (
    target instanceof HTMLInputElement ||
    target instanceof HTMLTextAreaElement ||
    (target instanceof HTMLElement && target.isContentEditable)
  )
}

export default function EditorPage() {
  const { sessionId } = useParams()
  const detailQuery = useSession(sessionId)
  const historyQuery = useSessionHistory(sessionId)
  const patchSession = usePatchSession()
  const tools = useSessionTools(sessionId)
  const fit = useCanvasView((state) => state.fit)
  const cropOpen = useEditorUi((state) => state.cropOpen)
  const cropRatio = useEditorUi((state) => state.cropRatio)
  const cropRect = useEditorUi((state) => state.cropRect)
  const openCrop = useEditorUi((state) => state.openCrop)
  const setCropRatio = useEditorUi((state) => state.setCropRatio)
  const closeCrop = useEditorUi((state) => state.closeCrop)
  const compareOpen = useEditorUi((state) => state.compareOpen)
  const openCompare = useEditorUi((state) => state.openCompare)
  const closeCompare = useEditorUi((state) => state.closeCompare)
  const panel = useEditorUi((state) => state.panel)
  const setPanel = useEditorUi((state) => state.setPanel)
  const [layersPanelOpen, setLayersPanelOpen] = useState(true)
  // 改名失败回退信号：递增触发工具栏把输入框重置回服务端标题
  const [renameFailTick, setRenameFailTick] = useState(0)
  // mutate 引用稳定（react-query 保证）；解构出来供快捷键 effect 作依赖
  const { mutate: undoMutate } = tools.undo
  const { mutate: redoMutate } = tools.redo

  // 全局快捷键：无条件挂载（hooks 纪律），无会话上下文时在回调内短路；
  // 焦点在 input/textarea/contentEditable 时全部跳过
  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      if (!sessionId) return
      if (isTypingTarget(event.target)) return
      const mod = event.metaKey || event.ctrlKey
      if (mod && event.key.toLowerCase() === 'z') {
        event.preventDefault()
        if (event.shiftKey) {
          redoMutate()
        } else {
          undoMutate()
        }
        return
      }
      if (mod && event.key.toLowerCase() === 'y') {
        event.preventDefault()
        redoMutate()
        return
      }
      if (event.key === 'Escape') {
        closeCrop()
        closeCompare()
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [sessionId, redoMutate, undoMutate, closeCrop, closeCompare])

  // /editor 未选会话：空态引导去创作
  if (!sessionId) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-canvas">
        <p className="text-sm text-muted">还没有选择会话。</p>
        <Link
          to="/create"
          className="rounded-control bg-brand px-4 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
        >
          去创作
        </Link>
      </div>
    )
  }

  const invoke = tools.invoke.mutate

  const detail = detailQuery.data
  // 越权或不存在一律 404：显示「会话不存在」空态，不泄露存在性
  const notFound = detailQuery.error instanceof ApiError && detailQuery.error.status === 404

  if (notFound) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-canvas">
        <p className="text-sm text-muted">会话不存在</p>
        <Link
          to="/create"
          className="rounded-control bg-brand px-4 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
        >
          去创作
        </Link>
      </div>
    )
  }

  if (detailQuery.isPending || !detail) {
    return (
      <div className="flex h-screen items-center justify-center bg-canvas">
        <p className="text-sm text-muted">正在加载会话…</p>
      </div>
    )
  }

  const switchPending = patchSession.isPending

  // asset_id → 签名 URL：图片墙现算，前端只消费（画布与对比模式共用）
  const resolveAssetUrl = (assetId: string | null) =>
    assetId ? (detail.wall.find((entry) => entry.asset.id === assetId)?.asset.url ?? null) : null

  const confirmCrop = () => {
    if (!cropRect) return
    invoke({ tool: 'crop_canvas', params: { rect: cropRect } })
    closeCrop()
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <SessionSidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <EditorToolbar
          title={detail.title}
          docWidth={detail.document.width}
          docHeight={detail.document.height}
          revision={detail.revision}
          renameFailTick={renameFailTick}
          onRename={(title) =>
            patchSession.mutate(
              { sessionId, input: { title } },
              { onError: () => setRenameFailTick((tick) => tick + 1) },
            )
          }
          onFit={() => fit(detail.document.width, detail.document.height)}
          action={{
            busy: tools.busy,
            canUndo: detail.can_undo,
            canRedo: detail.can_redo,
            hasPrevious: detail.previous_document !== null,
          }}
          cropOpen={cropOpen}
          cropRatio={cropRatio}
          adjustOpen={panel === 'adjust'}
          layersOpen={layersPanelOpen && panel === 'layers'}
          compareOpen={compareOpen}
          onFlipHorizontal={() => invoke({ tool: 'flip_layer', params: { direction: 'horizontal' } })}
          onFlipVertical={() => invoke({ tool: 'flip_layer', params: { direction: 'vertical' } })}
          onRemoveBackground={() => invoke({ tool: 'remove_background' })}
          onToggleAdjust={() => setPanel('adjust')}
          onToggleLayers={() => {
            setLayersPanelOpen(panel !== 'layers' ? true : !layersPanelOpen)
            setPanel('layers')
          }}
          onUndo={() => tools.undo.mutate()}
          onRedo={() => tools.redo.mutate()}
          onToggleCompare={() => (compareOpen ? closeCompare() : openCompare())}
          onEnterCrop={() => openCrop(detail.document.width, detail.document.height)}
          onCropRatio={(ratio) => setCropRatio(ratio, detail.document.width, detail.document.height)}
          onCropConfirm={confirmCrop}
          onCropCancel={closeCrop}
        />
        {patchSession.error && (
          <p role="alert" className="shrink-0 bg-danger/10 px-4 py-1 text-xs text-danger">
            {errorMessage(patchSession.error)}
          </p>
        )}
        {tools.invoke.error && (
          <p role="alert" className="shrink-0 bg-danger/10 px-4 py-1 text-xs text-danger">
            {errorMessage(tools.invoke.error)}
          </p>
        )}

        {/* 像素工具执行中：顶部提示条（阶段 · 百分比），进度条视觉最小 4% */}
        {tools.pendingStage !== null && (
          <div
            role="status"
            aria-live="polite"
            className="shrink-0 bg-brand-soft px-4 py-1.5 text-xs text-brand-strong"
          >
            <div className="mb-1 flex justify-between tabular-nums">
              <span>{tools.pendingStage}</span>
              <span>{Math.max(4, tools.pendingProgress)}%</span>
            </div>
            <div className="h-1 overflow-hidden rounded-full bg-paper">
              <div
                className="h-full rounded-full bg-brand transition-[width]"
                style={{ width: `${Math.max(4, tools.pendingProgress)}%` }}
              />
            </div>
          </div>
        )}

        <div className="min-h-0 flex-1">
          <CanvasStage
            sessionId={sessionId}
            document={detail.document}
            previousDocument={detail.previous_document}
            resolveAssetUrl={resolveAssetUrl}
          />
        </div>

        <ImageWall
          wall={detail.wall}
          currentAssetId={detail.current_asset_id}
          disabled={switchPending || tools.busy}
          onSwitch={(assetId) => patchSession.mutate({ sessionId, input: { current_asset_id: assetId } })}
        />
      </div>

      {layersPanelOpen && panel !== null && (
        <LayerPanel
          detail={detail}
          history={historyQuery.data ?? []}
          tools={{ busy: tools.busy, invoke: (tool, params) => invoke({ tool, params }) }}
          onClose={() => {
            setLayersPanelOpen(false)
            setPanel(null)
          }}
        />
      )}
    </div>
  )
}
