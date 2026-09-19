/** 生成式修图两表单：换背景（描述 + 1/2/4 张）与扩图（五比例点选）。
 * 挂在 LayerPanel 浮层内容区（与调色同层），提交走 useSessionTools.invoke——
 * 单张产出由服务端直接采用上画布，多张全进图片墙由用户点选采用（语义见文案）。 */
import { useState } from 'react'

/** 与后端 Ratio 枚举对齐的扩图五比例（默认 16:9）。 */
const EXPAND_RATIOS = ['1:1', '4:5', '3:4', '9:16', '16:9'] as const

export type ExpandRatio = (typeof EXPAND_RATIOS)[number]

const COUNT_OPTIONS = [1, 2, 4] as const

interface BackgroundFormProps {
  busy: boolean
  onSubmit: (prompt: string, count: number) => void
}

export function BackgroundForm({ busy, onSubmit }: BackgroundFormProps) {
  const [prompt, setPrompt] = useState('')
  const [count, setCount] = useState<number>(1)
  const canSubmit = prompt.trim().length > 0 && !busy

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!canSubmit) return
    onSubmit(prompt.trim(), count)
    setPrompt('') // 提交后清空：上次数值/描述残留再生成是反直觉的
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-2">
      <label className="flex flex-col gap-1.5 text-xs">
        <span className="font-medium text-muted">新背景描述</span>
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          rows={3}
          maxLength={500}
          disabled={busy}
          placeholder="浅木色桌面，晨光从左侧照入"
          className="resize-none rounded-control border border-line bg-soft px-3 py-2 text-xs text-ink outline-none placeholder:text-faint focus:border-brand"
        />
      </label>
      <div className="flex flex-col gap-1.5 text-xs">
        <span className="font-medium text-muted">生成张数</span>
        <div role="group" aria-label="选择生成张数" className="flex gap-2">
          {COUNT_OPTIONS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={count === value}
              title={`一次生成 ${value} 张候选`}
              disabled={busy}
              onClick={() => setCount(value)}
              className={`h-8 w-12 rounded-control border text-xs transition-colors disabled:opacity-40 ${
                count === value
                  ? 'border-brand bg-brand-soft font-medium text-brand-strong'
                  : 'border-line bg-paper text-muted hover:border-brand hover:text-ink'
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      <button
        type="submit"
        disabled={!canSubmit}
        title="按描述生成新背景"
        className="rounded-control bg-brand px-3 py-1.5 text-xs font-medium text-paper shadow-control transition-colors hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-40"
      >
        生成
      </button>
      <p className="text-xs text-faint">一张直接上画布；多张进图片墙，点选采用</p>
    </form>
  )
}

interface ExpandFormProps {
  busy: boolean
  onSubmit: (ratio: ExpandRatio) => void
}

export function ExpandForm({ busy, onSubmit }: ExpandFormProps) {
  const [ratio, setRatio] = useState<ExpandRatio>('16:9')

  return (
    <form
      onSubmit={(event) => {
        event.preventDefault()
        if (!busy) onSubmit(ratio)
      }}
      className="flex flex-col gap-2"
    >
      <div className="flex flex-col gap-1.5 text-xs">
        <span className="font-medium text-muted">目标比例（画面自然延伸，主体不裁切）</span>
        <div role="group" aria-label="选择扩图目标比例" className="flex flex-wrap gap-2">
          {EXPAND_RATIOS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={ratio === value}
              title={`扩展到 ${value}`}
              disabled={busy}
              onClick={() => setRatio(value)}
              className={`rounded-control border px-3 py-1.5 text-xs transition-colors disabled:opacity-40 ${
                ratio === value
                  ? 'border-brand bg-brand-soft font-medium text-brand-strong'
                  : 'border-line bg-paper text-muted hover:border-brand hover:text-ink'
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      <button
        type="submit"
        disabled={busy}
        title="把画布扩展到所选比例"
        className="rounded-control bg-brand px-3 py-1.5 text-xs font-medium text-paper shadow-control transition-colors hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-40"
      >
        扩展
      </button>
    </form>
  )
}
