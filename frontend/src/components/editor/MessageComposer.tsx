/** 输入区：textarea rows=2；Enter（非 Shift、非输入法组合态）发送并清空，
 * Shift+Enter 换行；空白或 pending 禁用；按钮文案 pending「思考中…」。 */
import { useState } from 'react'

interface MessageComposerProps {
  pending: boolean
  onSend: (text: string) => void
}

export default function MessageComposer({ pending, onSend }: MessageComposerProps) {
  const [text, setText] = useState('')
  const canSend = text.trim().length > 0 && !pending

  function submit() {
    if (!canSend) return
    onSend(text.trim())
    setText('')
  }

  return (
    <form
      className="shrink-0 border-t border-line p-3"
      onSubmit={(event) => {
        event.preventDefault()
        submit()
      }}
    >
      <textarea
        rows={2}
        value={text}
        placeholder="描述你想做的修改，例如「换成纯白背景」"
        aria-label="对话输入"
        onChange={(event) => setText(event.target.value)}
        onKeyDown={(event) => {
          // 输入法组合态回车是选字不是发送（交互硬规则）
          if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
            event.preventDefault()
            submit()
          }
        }}
        className="w-full resize-none rounded-control border border-line bg-paper px-2.5 py-2 text-sm text-ink placeholder:text-faint focus:border-brand focus:outline-none"
      />
      <button
        type="submit"
        disabled={!canSend}
        className="mt-2 w-full rounded-control bg-brand px-3 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong disabled:cursor-not-allowed disabled:opacity-50"
      >
        {pending ? '思考中…' : '发送'}
      </button>
    </form>
  )
}
