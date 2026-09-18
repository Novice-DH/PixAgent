/** 编辑器页：会话侧栏 + 工具栏 + 画布 + 图片墙 + 图层面板。
 * 满高应用式布局：根部直接用 h-screen 建立高度链（WorkbenchLayout 内容区由
 * min-h-screen 拉伸而来，百分比高度链解析不可靠），页面级不出现滚动条，
 * 滚动只发生在侧栏/面板/墙内部。 */
import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'

import CanvasStage from '@/components/editor/CanvasStage'
import EditorToolbar from '@/components/editor/EditorToolbar'
import ImageWall from '@/components/editor/ImageWall'
import LayerPanel from '@/components/editor/LayerPanel'
import SessionSidebar from '@/components/editor/SessionSidebar'
import { ApiError } from '@/api/client'
import { useCanvasView } from '@/stores/canvasView'
import { errorMessage } from '@/hooks/useAuth'
import {
  usePatchSession,
  useSession,
  useSessionHistory,
} from '@/hooks/useSessions'

export default function EditorPage() {
  const { sessionId } = useParams()
  const detailQuery = useSession(sessionId)
  const historyQuery = useSessionHistory(sessionId)
  const patchSession = usePatchSession()
  const fit = useCanvasView((state) => state.fit)
  const [layersOpen, setLayersOpen] = useState(true)
  // 改名失败回退信号：递增触发工具栏把输入框重置回服务端标题
  const [renameFailTick, setRenameFailTick] = useState(0)

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

  const currentAsset = detail.wall.find((entry) => entry.asset.id === detail.current_asset_id)
  const switchPending = patchSession.isPending

  return (
    <div className="flex h-screen overflow-hidden">
      <SessionSidebar />

      <div className="flex min-w-0 flex-1 flex-col">
        <EditorToolbar
          title={detail.title}
          docWidth={detail.document.width}
          docHeight={detail.document.height}
          revision={detail.revision}
          layersOpen={layersOpen}
          renameFailTick={renameFailTick}
          onRename={(title) =>
            patchSession.mutate(
              { sessionId, input: { title } },
              { onError: () => setRenameFailTick((tick) => tick + 1) },
            )
          }
          onToggleLayers={() => setLayersOpen((open) => !open)}
          onFit={() => fit(detail.document.width, detail.document.height)}
        />
        {patchSession.error && (
          <p role="alert" className="shrink-0 bg-danger/10 px-4 py-1 text-xs text-danger">
            {errorMessage(patchSession.error)}
          </p>
        )}

        <div className="min-h-0 flex-1">
          <CanvasStage
            sessionId={sessionId}
            document={detail.document}
            imageUrl={currentAsset?.asset.url ?? null}
          />
        </div>

        <ImageWall
          wall={detail.wall}
          currentAssetId={detail.current_asset_id}
          disabled={switchPending}
          onSwitch={(assetId) => patchSession.mutate({ sessionId, input: { current_asset_id: assetId } })}
        />
      </div>

      {layersOpen && (
        <LayerPanel
          detail={detail}
          history={historyQuery.data ?? []}
          onClose={() => setLayersOpen(false)}
        />
      )}
    </div>
  )
}
