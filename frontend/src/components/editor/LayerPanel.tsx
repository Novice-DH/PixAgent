/** 图层面板（右侧可开合）：三段只读展示——图层 / 属性 / 编辑记录。
 * 骨架期面板只看不动：没有任何图层操作或历史回放入口。 */
import type { SessionDetail } from '@/api/sessions'
import { actionLabel } from '@/api/sessions'
import { formatBytes, formatDateTime } from '@/lib/format'

interface LayerPanelProps {
  detail: SessionDetail
  history: { seq: number; action: string; created_at: string }[]
  onClose: () => void
}

export default function LayerPanel({ detail, history, onClose }: LayerPanelProps) {
  const currentAsset = detail.wall.find((entry) => entry.asset.id === detail.current_asset_id)?.asset

  return (
    <aside className="flex w-72 shrink-0 flex-col overflow-hidden border-l border-line bg-paper">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-line px-4">
        <h2 className="text-sm font-semibold text-ink">图层</h2>
        <button
          type="button"
          onClick={onClose}
          aria-label="收起图层面板"
          className="rounded-control px-2 py-1 text-xs text-muted hover:bg-brand-soft hover:text-brand-strong"
        >
          收起
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col divide-y divide-line overflow-y-auto">
        <section className="px-4 py-3">
          <h3 className="mb-2 text-xs font-medium text-muted">图层</h3>
          <ul className="flex flex-col gap-1.5">
            {detail.document.layers.map((layer) => (
              <li
                key={layer.id}
                className="flex items-center justify-between rounded-control bg-soft px-3 py-2 text-xs"
              >
                <span className="text-ink">{layer.name}</span>
                <span className="flex items-center gap-2 text-muted tabular-nums">
                  {layer.width}×{layer.height}
                  {layer.locked && <span title="已锁定">🔒</span>}
                </span>
              </li>
            ))}
          </ul>
        </section>

        <section className="px-4 py-3">
          <h3 className="mb-2 text-xs font-medium text-muted">属性</h3>
          <dl className="flex flex-col gap-1.5 text-xs">
            <div className="flex justify-between">
              <dt className="text-muted">画布尺寸</dt>
              <dd className="text-ink tabular-nums">
                {detail.document.width}×{detail.document.height}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">修订号</dt>
              <dd className="text-ink tabular-nums">{detail.revision}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">格式</dt>
              <dd className="text-ink">{currentAsset?.image_format ?? '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">大小</dt>
              <dd className="text-ink tabular-nums">
                {currentAsset ? formatBytes(currentAsset.size_bytes) : '—'}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-muted">透明通道</dt>
              <dd className="text-ink">{currentAsset?.has_alpha ? '有' : '无'}</dd>
            </div>
          </dl>
        </section>

        <section className="min-h-0 flex-1 px-4 py-3">
          <h3 className="mb-2 text-xs font-medium text-muted">编辑记录</h3>
          {history.length === 0 && <p className="text-xs text-muted">暂无编辑记录。</p>}
          <ol className="flex flex-col gap-1.5">
            {history.map((entry) => (
              <li
                key={entry.seq}
                className="flex items-center justify-between rounded-control bg-soft px-3 py-2 text-xs"
              >
                <span className="text-ink">{actionLabel(entry.action)}</span>
                <span className="text-muted tabular-nums">{formatDateTime(entry.created_at)}</span>
              </li>
            ))}
          </ol>
        </section>
      </div>
    </aside>
  )
}
