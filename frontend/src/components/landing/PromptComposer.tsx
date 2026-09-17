/** 需求输入面板（展示型、受控）：不 import 路由，提交后去哪由页面层决定。
 * Enter 提交必须排除输入法组合态——选词回车是中文用户最日常的操作。 */
import type { KeyboardEvent, RefObject } from 'react'

type PromptComposerProps = {
  value: string
  onChange: (value: string) => void
  onSubmit: () => void
  onAttach: () => void
  submitLabel: string
  placeholder: string
  inputRef: RefObject<HTMLTextAreaElement | null>
}

export default function PromptComposer({
  value,
  onChange,
  onSubmit,
  onAttach,
  submitLabel,
  placeholder,
  inputRef,
}: PromptComposerProps) {
  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key !== 'Enter') return
    // 输入法组合态（选词中）回车只上屏文字，不提交
    if (event.nativeEvent.isComposing) return
    // Shift + Enter 保留默认换行
    if (event.shiftKey) return
    event.preventDefault()
    onSubmit()
  }

  return (
    <div className="rounded-panel border border-line-strong bg-paper p-3 shadow-lift transition-colors focus-within:border-brand">
      <textarea
        ref={inputRef}
        rows={3}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        onKeyDown={handleKeyDown}
        placeholder={placeholder}
        className="block w-full resize-none bg-transparent px-2 py-1.5 text-sm leading-relaxed text-ink outline-none placeholder:text-faint"
      />
      <div className="mt-1.5 flex flex-wrap items-center justify-between gap-2">
        <button
          type="button"
          onClick={onAttach}
          className="flex items-center gap-1.5 rounded-control border border-line bg-soft px-3 py-1.5 text-xs font-medium text-muted transition-colors hover:border-brand hover:text-brand-strong"
        >
          <svg
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.8"
            aria-hidden="true"
            className="h-3.5 w-3.5"
          >
            <path
              d="M20 11.5l-7.6 7.6a4.6 4.6 0 0 1-6.5-6.5l7.8-7.8a3.1 3.1 0 0 1 4.4 4.4l-7.8 7.8a1.55 1.55 0 0 1-2.2-2.2l7.2-7.2"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          上传商品图
        </button>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-faint sm:inline">Enter 发送 · Shift + Enter 换行</span>
          <button
            type="button"
            onClick={onSubmit}
            className="rounded-control bg-brand px-4 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
          >
            {submitLabel}
          </button>
        </div>
      </div>
    </div>
  )
}
