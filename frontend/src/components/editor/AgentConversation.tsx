/** 对话区：turns 正序渲染，用户气泡与助手回复左右错开；turn.error 用 danger 色；
 * turns 变化滚动到底；空态引导文案举例并说明"选中才会替换当前图"。 */
import { useEffect, useRef } from 'react'

import type { Turn } from '@/api/agent'
import StepCard from '@/components/editor/StepCard'

export default function AgentConversation({ turns, sessionId }: { turns: Turn[]; sessionId: string }) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // behavior: 'auto'——prefers-reduced-motion 下不做平滑滚动
    bottomRef.current?.scrollIntoView({ block: 'end', behavior: 'auto' })
  }, [turns])

  if (turns.length === 0) {
    return (
      <div className="flex min-h-0 flex-1 flex-col items-center justify-center gap-2 p-4 text-center">
        <p className="text-sm text-muted">用一句话描述修改，例如</p>
        <p className="rounded-control bg-brand-soft px-3 py-1.5 text-sm text-brand-strong">
          「水平翻转」
        </p>
        <p className="mt-2 text-xs text-muted">
          裁剪、翻转、去背景等画布变换直接作用于当前图；生成类结果出现在下方图片墙，选中才会替换当前图。
        </p>
      </div>
    )
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-3">
      {turns.map((turn) => (
        <div key={turn.id} className="flex flex-col gap-2">
          <div className="flex justify-end">
            <p className="max-w-[85%] rounded-card rounded-br-control bg-brand px-3 py-1.5 text-sm text-paper">
              {turn.goal}
            </p>
          </div>
          <div className="flex flex-col items-start gap-2">
            {turn.reply && (
              <p className="max-w-[85%] rounded-card rounded-bl-control bg-soft px-3 py-1.5 text-sm text-ink">
                {turn.reply}
              </p>
            )}
            {turn.error && (
              <p
                role="alert"
                className="max-w-[85%] rounded-card rounded-bl-control bg-danger/10 px-3 py-1.5 text-xs text-danger"
              >
                {turn.error}
              </p>
            )}
            {turn.steps.map((step) => (
              <StepCard key={step.run_id ?? `${turn.id}-${step.tool}`} step={step} sessionId={sessionId} />
            ))}
          </div>
        </div>
      ))}
      <div ref={bottomRef} />
    </div>
  )
}
