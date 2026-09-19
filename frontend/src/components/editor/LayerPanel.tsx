/** 右栏面板：图层（选择/变换/排序）与调色（11 滑杆）互斥切换（editorUi.panel）。
 * 滑杆纪律：本地 draft，onPointerUp 才提交——拖动过程不发请求；
 * 调色应用后表单值清空，避免"上次数值残留再应用"。 */
import { useEffect, useState } from 'react'

import { actionLabel } from '@/api/sessions'
import type { SessionDetail } from '@/api/sessions'
import { formatBytes, formatDateTime } from '@/lib/format'
import { useEditorUi } from '@/stores/editorUi'

/** 与 useSessionTools 返回形态对齐的最小面（避免整包导入）。 */
interface PanelTools {
  busy: boolean
  invoke: (tool: string, params?: Record<string, unknown>) => void
}

interface LayerPanelProps {
  detail: SessionDetail
  history: { seq: number; action: string; created_at: string }[]
  tools: PanelTools
  onClose: () => void
}

const ADJUST_FIELDS = [
  { key: 'brightness', label: '亮度', min: -1 },
  { key: 'contrast', label: '对比度', min: -1 },
  { key: 'highlights', label: '高光', min: -1 },
  { key: 'shadows', label: '阴影', min: -1 },
  { key: 'temperature', label: '色温', min: -1 },
  { key: 'tint', label: '色调', min: -1 },
  { key: 'saturation', label: '饱和度', min: -1 },
  { key: 'vibrance', label: '自然饱和度', min: -1 },
  { key: 'sharpness', label: '锐化', min: -1 },
  { key: 'clarity', label: '清晰度', min: -1 },
  { key: 'vignette', label: '晕影', min: 0 },
] as const

type AdjustDraft = Partial<Record<(typeof ADJUST_FIELDS)[number]['key'], number>>

const EMPTY_DRAFT: AdjustDraft = {}

function Slider({
  label,
  min,
  max,
  step,
  value,
  disabled,
  onCommit,
}: {
  label: string
  min: number
  max: number
  step: number
  value: number
  disabled: boolean
  onCommit: (value: number) => void
}) {
  const [draft, setDraft] = useState(value)
  const [lastValue, setLastValue] = useState(value)
  if (lastValue !== value) {
    setLastValue(value)
    setDraft(value)
  }
  return (
    <label className="flex items-center gap-2 text-xs">
      <span className="w-16 shrink-0 text-muted">{label}</span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={draft}
        disabled={disabled}
        onChange={(event) => setDraft(Number(event.target.value))}
        onPointerUp={() => {
          if (draft !== value) onCommit(draft)
        }}
        className="h-1 min-w-0 flex-1 accent-brand disabled:opacity-40"
      />
      <span className="w-10 shrink-0 text-right text-ink tabular-nums">{draft.toFixed(2)}</span>
    </label>
  )
}

export default function LayerPanel({ detail, history, tools, onClose }: LayerPanelProps) {
  const panel = useEditorUi((state) => state.panel)
  const setPanel = useEditorUi((state) => state.setPanel)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selectLayer = useEditorUi((state) => state.selectLayer)
  const [adjustDraft, setAdjustDraft] = useState<AdjustDraft>(EMPTY_DRAFT)

  // 默认选中层表最后一层（视觉最前）；图层增减后若选中层不存在则回落
  const layers = detail.document.layers
  const fallbackId = layers.length > 0 ? layers[layers.length - 1]!.id : null
  useEffect(() => {
    if (!selectedLayerId || !layers.some((layer) => layer.id === selectedLayerId)) {
      selectLayer(fallbackId)
    }
  }, [selectedLayerId, layers, fallbackId, selectLayer])

  const selected =
    layers.find((layer) => layer.id === selectedLayerId) ??
    (fallbackId ? layers.find((layer) => layer.id === fallbackId) : undefined)
  const busy = tools.busy
  const currentAsset = detail.wall.find((entry) => entry.asset.id === detail.current_asset_id)?.asset

  const invokeWithLayer = (tool: string, params: Record<string, unknown>) => {
    if (!selected) return
    tools.invoke(tool, { ...params, layer_id: selected.id })
  }

  const applyAdjust = () => {
    const params = Object.fromEntries(
      Object.entries(adjustDraft).filter(([, value]) => value !== 0),
    )
    if (Object.keys(params).length === 0) return
    tools.invoke('adjust_image', params)
    setAdjustDraft(EMPTY_DRAFT) // 应用后表单归零：避免"上次数值残留再应用"
  }

  return (
    <aside className="flex w-72 shrink-0 flex-col overflow-hidden border-l border-line bg-paper">
      <div className="flex h-12 shrink-0 items-center justify-between border-b border-line px-4">
        <div className="flex items-center gap-1">
          <button
            type="button"
            aria-pressed={panel === 'layers'}
            onClick={() => setPanel('layers')}
            className="rounded-control px-2 py-1 text-sm text-muted hover:bg-brand-soft hover:text-brand-strong aria-pressed:bg-brand-soft aria-pressed:text-brand-strong"
          >
            图层
          </button>
          <button
            type="button"
            aria-pressed={panel === 'adjust'}
            onClick={() => setPanel('adjust')}
            className="rounded-control px-2 py-1 text-sm text-muted hover:bg-brand-soft hover:text-brand-strong aria-pressed:bg-brand-soft aria-pressed:text-brand-strong"
          >
            调色
          </button>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="收起面板"
          className="rounded-control px-2 py-1 text-xs text-muted hover:bg-brand-soft hover:text-brand-strong"
        >
          收起
        </button>
      </div>

      <div className="flex min-h-0 flex-1 flex-col divide-y divide-line overflow-y-auto">
        {panel === 'adjust' ? (
          <>
            <section className="flex flex-col gap-2 px-4 py-3">
              <h3 className="text-xs font-medium text-muted">调色（应用后归零）</h3>
              {ADJUST_FIELDS.map((field) => (
                <Slider
                  key={field.key}
                  label={field.label}
                  min={field.min}
                  max={1}
                  step={0.05}
                  value={adjustDraft[field.key] ?? 0}
                  disabled={busy}
                  onCommit={(value) => setAdjustDraft((draft) => ({ ...draft, [field.key]: value }))}
                />
              ))}
            </section>
            <section className="flex gap-2 px-4 py-3">
              <button
                type="button"
                onClick={() => setAdjustDraft(EMPTY_DRAFT)}
                disabled={busy}
                className="flex-1 rounded-control border border-line px-3 py-1.5 text-xs text-muted transition-colors hover:bg-brand-soft hover:text-brand-strong disabled:opacity-40"
              >
                重置
              </button>
              <button
                type="button"
                onClick={applyAdjust}
                disabled={busy}
                className="flex-1 rounded-control bg-brand px-3 py-1.5 text-xs font-medium text-paper shadow-control transition-colors hover:bg-brand-strong disabled:opacity-40"
              >
                应用
              </button>
            </section>
          </>
        ) : (
          <>
            <section className="px-4 py-3">
              <h3 className="mb-2 text-xs font-medium text-muted">图层（视觉最前在上）</h3>
              <ul className="flex flex-col gap-1.5">
                {[...layers].reverse().map((layer) => (
                  <li key={layer.id}>
                    <button
                      type="button"
                      aria-pressed={selected?.id === layer.id}
                      onClick={() => selectLayer(layer.id)}
                      className="flex w-full items-center justify-between rounded-control bg-soft px-3 py-2 text-xs transition-colors hover:bg-brand-soft aria-pressed:bg-brand-soft"
                    >
                      <span className="text-ink">{layer.name}</span>
                      <span className="flex items-center gap-2 text-muted tabular-nums">
                        {layer.width}×{layer.height}
                        {layer.locked && <span title="已锁定">🔒</span>}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            </section>

            {selected && (
              <section className="flex flex-col gap-2 px-4 py-3">
                <h3 className="text-xs font-medium text-muted">变换（松手提交）</h3>
                <Slider
                  label="透明度"
                  min={0}
                  max={1}
                  step={0.01}
                  value={selected.opacity}
                  disabled={busy}
                  onCommit={(value) => invokeWithLayer('set_layer_opacity', { opacity: value })}
                />
                <Slider
                  label="图层缩放"
                  min={0.1}
                  max={3}
                  step={0.05}
                  value={Math.abs(selected.transform.scale_x)}
                  disabled={busy}
                  onCommit={(value) => invokeWithLayer('scale_layer', { scale_x: value, scale_y: value })}
                />
                <Slider
                  label="旋转"
                  min={-180}
                  max={180}
                  step={1}
                  value={selected.transform.rotation}
                  disabled={busy}
                  onCommit={(value) => invokeWithLayer('rotate_layer', { rotation: value })}
                />
                <div className="mt-1 grid grid-cols-4 gap-1">
                  {(
                    [
                      ['置顶', 'top'],
                      ['上移', 'up'],
                      ['下移', 'down'],
                      ['置底', 'bottom'],
                    ] as const
                  ).map(([label, place]) => (
                    <button
                      key={place}
                      type="button"
                      disabled={busy}
                      onClick={() => invokeWithLayer('reorder_layer', { place })}
                      className="rounded-control bg-soft px-2 py-1 text-xs text-muted transition-colors hover:bg-brand-soft hover:text-brand-strong disabled:opacity-40"
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </section>
            )}

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
          </>
        )}
      </div>
    </aside>
  )
}
