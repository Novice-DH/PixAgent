/** 步骤卡片：对话内一步工具执行的进度——useRun 双源合并（SSE 帧 + 快照兜底）零改造复用。
 * watched 纪律（S11）：invalidate 为"刚完成"这个事件服务，不是为"已终态"这个状态——
 * 只有亲眼经历过 queued/running 的步骤在终态才刷新会话键族；首屏渲染的已终态
 * 历史步骤不触发（否则打开编辑器就对每个历史步骤刷一遍墙）。可空 run_id 不启用查询。 */
import { useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import type { PlanStep } from '@/api/agent'
import { isTerminal } from '@/api/runs'
import { sessionKey } from '@/hooks/useSessions'
import { useRun } from '@/hooks/useRun'

/** 进度条视觉最小 4%：0% 也显示为有进度的形态（与候选页同一纪律）。 */
const MIN_PROGRESS_PERCENT = 4

export default function StepCard({ step, sessionId }: { step: PlanStep; sessionId: string }) {
  const queryClient = useQueryClient()
  const watchedRef = useRef(false)
  const { run, notFound } = useRun(step.run_id ?? undefined)

  useEffect(() => {
    if (!run) return
    if (!isTerminal(run.status)) {
      watchedRef.current = true // 亲眼见过它运行
      return
    }
    if (watchedRef.current) {
      watchedRef.current = false // 只在"运行→终态"事件触发一次
      queryClient.invalidateQueries({ queryKey: sessionKey(sessionId) })
    }
  }, [run, sessionId, queryClient])

  return (
    <div className="w-full max-w-[85%] rounded-card border border-line bg-soft px-3 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium text-ink">{step.label}</span>
        {run && !isTerminal(run.status) && (
          <span className="text-xs tabular-nums text-muted">{run.progress}%</span>
        )}
        {run?.status === 'succeeded' && (
          <span className="text-xs text-success">已完成</span>
        )}
      </div>

      {run && !isTerminal(run.status) && (
        <div
          className="mt-1.5 h-1.5 overflow-hidden rounded-control bg-line"
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={run.progress}
        >
          <div
            className="h-full bg-brand transition-colors"
            style={{ width: `${Math.max(run.progress, MIN_PROGRESS_PERCENT)}%` }}
          />
        </div>
      )}
      {run && !isTerminal(run.status) && run.stage && (
        <p className="mt-1 text-xs text-muted">{run.stage}</p>
      )}

      {run?.status === 'failed' && (
        <p className="mt-1 text-xs text-danger">{run.error ?? '执行失败，请重试'}</p>
      )}
      {notFound && <p className="mt-1 text-xs text-muted">任务不存在或已被清理</p>}
    </div>
  )
}
