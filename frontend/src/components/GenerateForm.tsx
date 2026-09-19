/** 生成表单：受控表单（prompt / 比例 / 数量 / 负向提示词折叠区）。
 * Enter 提交（isComposing 排除输入法组合态）、Shift+Enter 换行，经 requestSubmit 触发表单。 */
import { useRef, useState } from 'react'

import { RATIO_LABELS, RATIOS, type GenerateInput, type Ratio } from '@/api/runs'

const COUNT_OPTIONS = [1, 2, 4, 6]

interface GenerateFormProps {
  defaultPrompt?: string
  pending: boolean
  onSubmit: (input: GenerateInput) => void
}

export default function GenerateForm({ defaultPrompt = '', pending, onSubmit }: GenerateFormProps) {
  const [prompt, setPrompt] = useState(defaultPrompt)
  const [ratio, setRatio] = useState<Ratio>('1:1')
  const [count, setCount] = useState(4)
  const [negativePrompt, setNegativePrompt] = useState('')
  const [showNegative, setShowNegative] = useState(false)
  const formRef = useRef<HTMLFormElement>(null)

  const canSubmit = prompt.trim().length > 0 && !pending

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter' || event.shiftKey) return
    // 输入法组合态（选词中）回车仅上屏文字，不提交
    if (event.nativeEvent.isComposing) return
    event.preventDefault()
    if (canSubmit) formRef.current?.requestSubmit()
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    if (!canSubmit) return
    const negative = negativePrompt.trim()
    onSubmit({
      prompt: prompt.trim(),
      ratio,
      count,
      ...(negative ? { negative_prompt: negative } : {}),
    })
  }

  return (
    <form
      ref={formRef}
      onSubmit={handleSubmit}
      className="flex flex-col gap-4 rounded-card border border-line bg-paper p-5 shadow-card"
    >
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">画面描述</span>
        <textarea
          value={prompt}
          onChange={(event) => setPrompt(event.target.value)}
          onKeyDown={handleKeyDown}
          rows={3}
          maxLength={1500}
          placeholder="一句话描述想要的画面，例如：白瓷茶壶放在原木桌面，晨光，浅色背景"
          className="resize-none rounded-control border border-line bg-soft px-3 py-2 text-ink outline-none placeholder:text-faint focus:border-brand"
        />
      </label>

      <div className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">比例</span>
        <div role="group" aria-label="选择画面比例" className="flex flex-wrap gap-2">
          {RATIOS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={ratio === value}
              title={`按 ${RATIO_LABELS[value]} 生成`}
              onClick={() => setRatio(value)}
              className={`rounded-control border px-3 py-1.5 text-sm transition-colors ${
                ratio === value
                  ? 'border-brand bg-brand-soft font-medium text-brand-strong'
                  : 'border-line bg-paper text-muted hover:border-brand hover:text-ink'
              }`}
            >
              {RATIO_LABELS[value]}
            </button>
          ))}
        </div>
      </div>

      <div className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">生成数量</span>
        <div role="group" aria-label="选择生成数量" className="flex gap-2">
          {COUNT_OPTIONS.map((value) => (
            <button
              key={value}
              type="button"
              aria-pressed={count === value}
              title={`一次生成 ${value} 张候选`}
              onClick={() => setCount(value)}
              className={`h-9 w-12 rounded-control border text-sm transition-colors ${
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

      <div className="flex flex-col gap-2 text-sm">
        <button
          type="button"
          aria-expanded={showNegative}
          onClick={() => setShowNegative((open) => !open)}
          className="w-fit text-muted transition-colors hover:text-ink"
        >
          {showNegative ? '▾' : '▸'} 负向提示词（可选）
        </button>
        {showNegative && (
          <textarea
            value={negativePrompt}
            onChange={(event) => setNegativePrompt(event.target.value)}
            rows={2}
            maxLength={1500}
            placeholder="不希望出现的元素，例如：文字、水印、多余的手"
            className="resize-none rounded-control border border-line bg-soft px-3 py-2 text-ink outline-none placeholder:text-faint focus:border-brand"
          />
        )}
      </div>

      <button
        type="submit"
        disabled={!canSubmit}
        className="rounded-control bg-brand px-4 py-2.5 text-sm font-medium text-paper shadow-control transition-[color,background-color,transform] duration-150 hover:bg-brand-strong active:scale-[0.99] disabled:opacity-60"
      >
        {pending ? '正在提交…' : '开始生成'}
      </button>
    </form>
  )
}
