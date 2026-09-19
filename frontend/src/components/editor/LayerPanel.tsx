/** 右栏面板：图层（选择/变换/排序）与调色（11 滑杆）互斥切换（editorUi.panel）。
 * 画布右侧浮层（绝对定位 + 滑入动画），开合不推动画布。
 * 滑杆协议：onInput 拖动实时驱动画布预览，onCommit 松手/键盘/双击复位落库；
 * 指针捕获 + lostpointercapture 兜底——拖出控件松手必提交；label 双击复位 origin。
 * 预览是渲染态：文档回传新值即撤（value 变化的 effect），失败/切层/切面板/卸载兜底清空。
 * 调色应用后表单值清空，避免"上次数值残留再应用"。 */
import { useEffect, useRef, useState } from 'react'

import { actionLabel } from '@/api/sessions'
import type { SessionDetail } from '@/api/sessions'
import { formatBytes, formatDateTime } from '@/lib/format'
import { ADJUST_PREVIEW_KEYS, type AdjustPreviewValues } from '@/lib/adjustPreview'
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

type AdjustKey = (typeof ADJUST_FIELDS)[number]['key']
type AdjustDraft = Partial<Record<AdjustKey, number>>

const EMPTY_DRAFT: AdjustDraft = {}

const toPreviewValues = (draft: AdjustDraft): AdjustPreviewValues => {
  const values = {} as AdjustPreviewValues
  for (const key of ADJUST_PREVIEW_KEYS) {
    values[key] = draft[key] ?? 0
  }
  return values
}

/** 滑杆：onInput 拖动实时（驱动预览），onCommit 落库。提交时机=lostpointercapture
 * （指针捕获下拖出控件松手仍触发，onPointerUp 兜底）；键盘调节松开按键即提交；
 * label 双击复位 origin。step ≥ 1 显示整数，否则两位小数。 */
function SliderField({
  label,
  min,
  max,
  step,
  value,
  origin,
  disabled,
  onInput,
  onCommit,
}: {
  label: string
  min: number
  max: number
  step: number
  value: number
  origin: number
  disabled: boolean
  onInput: (value: number) => void
  onCommit: (value: number) => void
}) {
  const [draft, setDraft] = useState(value)
  const [lastValue, setLastValue] = useState(value)
  // 指针交互提交闸：一次拖动只提交一次（pointerup 与 lostpointercapture 双触发兜底）
  const commitGateRef = useRef(true)
  if (lastValue !== value) {
    setLastValue(value)
    setDraft(value)
  }

  const commitViaPointer = (next: number) => {
    if (commitGateRef.current) return
    commitGateRef.current = true
    if (next !== value) onCommit(next)
  }

  const commitDirect = (next: number) => {
    if (next !== value) onCommit(next)
  }

  return (
    <div className="flex items-center gap-2 text-xs">
      <span
        role="button"
        tabIndex={-1}
        title={`双击「${label}」复位`}
        onDoubleClick={() => {
          setDraft(origin)
          onInput(origin)
          commitDirect(origin)
        }}
        className="w-16 shrink-0 cursor-pointer select-none text-muted"
      >
        {label}
      </span>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={draft}
        disabled={disabled}
        aria-label={label}
        onPointerDown={(event) => {
          event.currentTarget.setPointerCapture(event.pointerId)
          commitGateRef.current = false
        }}
        onPointerUp={(event) => commitViaPointer(Number(event.currentTarget.value))}
        onLostPointerCapture={(event) => commitViaPointer(Number(event.currentTarget.value))}
        onChange={(event) => {
          const next = Number(event.target.value)
          setDraft(next)
          onInput(next)
        }}
        onKeyUp={() => commitDirect(draft)}
        className="h-4 min-w-0 flex-1"
      />
      <span className="w-10 shrink-0 text-right text-ink tabular-nums">
        {draft.toFixed(step >= 1 ? 0 : 2)}
      </span>
    </div>
  )
}

export default function LayerPanel({ detail, history, tools, onClose }: LayerPanelProps) {
  const panel = useEditorUi((state) => state.panel)
  const setPanel = useEditorUi((state) => state.setPanel)
  const selectedLayerId = useEditorUi((state) => state.selectedLayerId)
  const selectLayer = useEditorUi((state) => state.selectLayer)
  const setAdjustPreview = useEditorUi((state) => state.setAdjustPreview)
  const setLayerPreview = useEditorUi((state) => state.setLayerPreview)
  const [adjustDraft, setAdjustDraft] = useState<AdjustDraft>(EMPTY_DRAFT)
  const busyRef = useRef(tools.busy)

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

  // 预览生命周期：文档回传新值即撤——变换三要素任一变化的 effect 显式关闭
  const selectedValueKey = selected
    ? `${selected.id}:${selected.opacity}:${selected.transform.rotation}:${Math.abs(selected.transform.scale_x)}`
    : null
  useEffect(() => {
    setLayerPreview(null)
  }, [selectedValueKey, setLayerPreview])

  // 兜底撤预览：一轮交互结束（busy 落下）但文档没变（失败/无可撤）时不留残影
  useEffect(() => {
    if (busyRef.current && !busy) {
      setLayerPreview(null)
    }
    busyRef.current = busy
  }, [busy, setLayerPreview])

  // 切页签只保留当前页签的预览；卸载全部清空
  useEffect(() => {
    if (panel === 'adjust') {
      setLayerPreview(null)
    } else {
      setAdjustPreview(null)
    }
  }, [panel, setLayerPreview, setAdjustPreview])
  useEffect(
    () => () => {
      setLayerPreview(null)
      setAdjustPreview(null)
    },
    [setLayerPreview, setAdjustPreview],
  )

  const invokeWithLayer = (tool: string, params: Record<string, unknown>) => {
    if (!selected) return
    tools.invoke(tool, { ...params, layer_id: selected.id })
  }

  const updateAdjust = (key: AdjustKey, value: number) => {
    const next = { ...adjustDraft, [key]: value }
    setAdjustDraft(next)
    setAdjustPreview(toPreviewValues(next))
  }

  const clearAdjust = () => {
    setAdjustDraft(EMPTY_DRAFT)
    setAdjustPreview(null)
  }

  const adjustTouched = ADJUST_FIELDS.some((field) => (adjustDraft[field.key] ?? 0) !== 0)

  const applyAdjust = () => {
    const params = Object.fromEntries(
      Object.entries(adjustDraft).filter(([, value]) => value !== 0),
    )
    if (Object.keys(params).length === 0) return
    tools.invoke('adjust_image', params)
    clearAdjust() // 应用后表单归零：避免"上次数值残留再应用"
  }

  return (
    <aside className="absolute inset-y-0 right-0 z-20 flex w-72 flex-col overflow-hidden border-l border-line bg-paper shadow-panel animate-slide-in">
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

      <div className="scrollbar-slim flex min-h-0 flex-1 flex-col divide-y divide-line overflow-y-auto">
        {panel === 'adjust' ? (
          <>
            <section className="flex flex-col gap-2 px-4 py-3">
              <h3 className="text-xs font-medium text-muted">调色（拖动实时预览，应用后归零）</h3>
              {ADJUST_FIELDS.map((field) => (
                <SliderField
                  key={field.key}
                  label={field.label}
                  min={field.min}
                  max={1}
                  step={0.05}
                  value={adjustDraft[field.key] ?? 0}
                  origin={0}
                  disabled={busy}
                  onInput={(value) => updateAdjust(field.key, value)}
                  onCommit={(value) => updateAdjust(field.key, value)}
                />
              ))}
              <p className="text-xs text-faint">锐化与清晰度不参与实时预览，应用后可见。</p>
            </section>
            <section className="flex gap-2 px-4 py-3">
              <button
                type="button"
                onClick={clearAdjust}
                disabled={busy || !adjustTouched}
                title="恢复全部调色滑杆为 0"
                className="flex-1 rounded-control border border-line px-3 py-1.5 text-xs text-muted transition-colors hover:bg-brand-soft hover:text-brand-strong disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent disabled:hover:text-muted"
              >
                重置
              </button>
              <button
                type="button"
                onClick={applyAdjust}
                disabled={busy || !adjustTouched}
                title="把当前调色应用到当前图"
                className="flex-1 rounded-control bg-brand px-3 py-1.5 text-xs font-medium text-paper shadow-control transition-colors hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-brand"
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
                <h3 className="text-xs font-medium text-muted">变换（拖动实时预览，松手提交）</h3>
                <SliderField
                  label="透明度"
                  min={0}
                  max={1}
                  step={0.01}
                  value={selected.opacity}
                  origin={1}
                  disabled={busy}
                  onInput={(value) => setLayerPreview({ id: selected.id, opacity: value })}
                  onCommit={(value) => invokeWithLayer('set_layer_opacity', { opacity: value })}
                />
                <SliderField
                  label="图层缩放"
                  min={0.1}
                  max={3}
                  step={0.05}
                  value={Math.abs(selected.transform.scale_x)}
                  origin={1}
                  disabled={busy}
                  onInput={(value) => setLayerPreview({ id: selected.id, scale: value })}
                  onCommit={(value) => invokeWithLayer('scale_layer', { scale_x: value, scale_y: value })}
                />
                <SliderField
                  label="旋转"
                  min={-180}
                  max={180}
                  step={1}
                  value={selected.transform.rotation}
                  origin={0}
                  disabled={busy}
                  onInput={(value) => setLayerPreview({ id: selected.id, rotation: value })}
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
