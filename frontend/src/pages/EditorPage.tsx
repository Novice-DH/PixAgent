/** 编辑器页：会话侧栏 + 工具栏 + 画布 + 图片墙 + 画布右侧浮层面板。
 * 满高应用式布局：根部直接用 h-screen 建立高度链（WorkbenchLayout 内容区由
 * min-h-screen 拉伸而来，百分比高度链解析不可靠），页面级不出现滚动条，
 * 滚动只发生在侧栏/面板/墙内部。
 * 全局键盘：Cmd/Ctrl+Z 撤销、+Shift 或 +Y 重做、Escape 关裁剪/对比；
 * 0 适应、1 实际像素、+/− 缩放（无修饰键才生效）；焦点在 input/textarea 时全部跳过
 * （快捷键吞输入是演示现场事故）。 */
import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import CanvasStage from '@/components/editor/CanvasStage'
import CanvasHint from '@/components/editor/CanvasHint'
import EditorToolbar from '@/components/editor/EditorToolbar'
import ImageWall from '@/components/editor/ImageWall'
import LayerPanel from '@/components/editor/LayerPanel'
import SessionSidebar from '@/components/editor/SessionSidebar'
import { ApiError } from '@/api/client'
import { ZOOM_STEP, useCanvasView } from '@/stores/canvasView'
import { useEditorUi } from '@/stores/editorUi'
import { errorMessage } from '@/hooks/useAuth'
import { useSelection } from '@/hooks/useSelection'
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
  const stepZoom = useCanvasView((state) => state.stepZoom)
  const zoomTo = useCanvasView((state) => state.zoomTo)
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
  const selectMode = useEditorUi((state) => state.selectMode)
  const setSelectMode = useEditorUi((state) => state.setSelectMode)
  const selection = useEditorUi((state) => state.selection)
  const setSelection = useEditorUi((state) => state.setSelection)
  // 会话切换（侧栏导航不重挂载页面）：选区属于旧会话的画布，切会话即清——
  // 防止跨会话的幽灵遮罩与选区形状误用（revision 恰好相等时服务端拦不住）
  useEffect(() => {
    setSelection(null)
  }, [sessionId, setSelection])
  // 选区 mutation：revision 变化（撤销/切图/重做）时本地选区立即作废（hook 内 effect）
  const {
    addPoint,
    addStroke,
    clearSelection,
    busy: selectionBusy,
  } = useSelection(sessionId, detailQuery.data?.revision)
  // 改名失败回退信号：递增触发工具栏把输入框重置回服务端标题
  const [renameFailTick, setRenameFailTick] = useState(0)
  // mutate 引用稳定（react-query 保证）；解构出来供快捷键 effect 作依赖
  const { mutate: undoMutate } = tools.undo
  const { mutate: redoMutate } = tools.redo

  // 快捷键所需的画幅尺寸进 effect 依赖（会话/画幅变化才重挂监听，action 引用稳定）
  const docWidth = detailQuery.data?.document.width
  const docHeight = detailQuery.data?.document.height

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
        // Esc 退出选区模式（选区数据保留，由 revision 与一次性消费管理）
        setSelectMode(null)
        return
      }
      // 视图快捷键只在无修饰键时生效（按住 meta/shift/alt 不触发）；
      // 裁剪态与选区态同纪律：视图操作全部让位给当前模式
      if (event.metaKey || event.ctrlKey || event.altKey || event.shiftKey) return
      if (cropOpen || selectMode !== null) return
      if (event.key === '0') {
        if (docWidth && docHeight) {
          event.preventDefault()
          fit(docWidth, docHeight)
        }
        return
      }
      if (event.key === '1') {
        event.preventDefault()
        zoomTo(1)
        return
      }
      if (event.key === '+' || event.key === '=') {
        event.preventDefault()
        stepZoom(ZOOM_STEP)
        return
      }
      if (event.key === '-' || event.key === '_') {
        event.preventDefault()
        stepZoom(1 / ZOOM_STEP)
      }
    }
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [
    sessionId,
    redoMutate,
    undoMutate,
    closeCrop,
    closeCompare,
    setSelectMode,
    zoomTo,
    stepZoom,
    fit,
    docWidth,
    docHeight,
    cropOpen,
    selectMode,
  ])

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

  // 加载/错误单返回：isPending、isError、404 共用一个空态壳，文案按态分派
  if (detailQuery.isPending || detailQuery.isError || !detail) {
    return (
      <div className="flex h-screen flex-col items-center justify-center gap-3 bg-canvas">
        {notFound ? (
          <>
            <p className="text-sm text-muted">会话不存在</p>
            <Link
              to="/create"
              className="rounded-control bg-brand px-4 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
            >
              去创作
            </Link>
          </>
        ) : detailQuery.isError ? (
          <>
            <p className="text-sm text-danger">{errorMessage(detailQuery.error)}</p>
            <Link
              to="/create"
              className="rounded-control bg-brand px-4 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
            >
              去创作
            </Link>
          </>
        ) : (
          <p className="text-sm text-muted">正在加载会话…</p>
        )}
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
          layersOpen={panel === 'layers'}
          compareOpen={compareOpen}
          backgroundOpen={panel === 'background'}
          expandOpen={panel === 'expand'}
          onFlipHorizontal={() => invoke({ tool: 'flip_layer', params: { direction: 'horizontal' } })}
          onFlipVertical={() => invoke({ tool: 'flip_layer', params: { direction: 'vertical' } })}
          onRemoveBackground={() => invoke({ tool: 'remove_background' })}
          onToggleAdjust={() => setPanel('adjust')}
          onToggleLayers={() => setPanel('layers')}
          onToggleBackground={() => setPanel('background')}
          onToggleExpand={() => setPanel('expand')}
          onUpscale={() => invoke({ tool: 'upscale_image', params: { scale: 2 } })}
          onUndo={() => tools.undo.mutate()}
          onRedo={() => tools.redo.mutate()}
          onToggleCompare={() => (compareOpen ? closeCompare() : openCompare())}
          onEnterCrop={() => openCrop(detail.document.width, detail.document.height)}
          onCropRatio={(ratio) => setCropRatio(ratio, detail.document.width, detail.document.height)}
          onCropConfirm={confirmCrop}
          onCropCancel={closeCrop}
          selectMode={selectMode}
          hasSelection={selection !== null}
          onSelectMode={(mode) => setSelectMode(mode)}
          onEraseRegion={() => {
            if (!selection) return
            invoke({
              tool: 'erase_region',
              params: { mask_asset_id: selection.maskId, revision: selection.revision },
            })
          }}
          onReplaceRegion={() => setPanel('replace')}
          onClearSelection={clearSelection}
        />
        {patchSession.error && (
          <p role="alert" className="shrink-0 bg-danger/10 px-4 py-1 text-xs text-danger">
            {errorMessage(patchSession.error)}
          </p>
        )}

        {/* 画布区：面板与情境提示都是画布上的浮层（覆盖式），开合不推动画布 */}
        <div className="relative min-h-0 flex-1">
          <CanvasStage
            sessionId={sessionId}
            document={detail.document}
            previousDocument={detail.previous_document}
            resolveAssetUrl={resolveAssetUrl}
            selectMode={selectMode}
            selectionBusy={selectionBusy || tools.busy}
            onPointSelect={addPoint}
            onStrokeCommit={addStroke}
          />
          <CanvasHint
            busyStage={tools.pendingStage}
            busyProgress={tools.pendingProgress}
            cropOpen={cropOpen}
            compareOpen={compareOpen}
            selectMode={selectMode}
          />
          {panel !== null && (
            <LayerPanel
              detail={detail}
              history={historyQuery.data ?? []}
              tools={{ busy: tools.busy, invoke: (tool, params) => invoke({ tool, params }) }}
              onClose={() => setPanel(null)}
            />
          )}
        </div>

        <ImageWall
          wall={detail.wall}
          currentAssetId={detail.current_asset_id}
          disabled={switchPending || tools.busy}
          onSwitch={(assetId) => patchSession.mutate({ sessionId, input: { current_asset_id: assetId } })}
        />
      </div>
    </div>
  )
}
