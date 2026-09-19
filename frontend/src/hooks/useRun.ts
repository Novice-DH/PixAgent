/** 生图任务钩子：useGenerate（提交）+ useRun（双源合并进度）。
 *
 * 双源合并：EventSource 实时帧驱动界面，react-query 快照是可恢复的事实源——
 * 终态关连接并 invalidate（候选图来自快照）；切任务校验帧 id，旧连接的迟到帧不得污染新任务。
 * S11 修订（对 S5「连接出错回退快照」的取代）：快照已终态不建 SSE——刷新已完成的
 * 任务不再走"建连→收一帧→关连→重放签名 URL"的无谓循环（签名现算是真实成本）；
 * 连接错误交给 EventSource 自动重连（重连后服务端先重播快照帧），终态帧自带快照失效。
 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import { ApiError } from '@/api/client'
import { isTerminal, runsApi, type Run, type RunFrame } from '@/api/runs'

export function useGenerate() {
  return useMutation({ mutationFn: runsApi.generate })
}

function runKey(runId: string) {
  return ['runs', runId] as const
}

/** SSE 帧 → Run 视图：快照提供候选与元数据，帧覆盖实时进度字段。 */
function merge(snap: Run | undefined, live: RunFrame | null): Run | null {
  if (live) {
    const base: Run = snap ?? {
      id: live.id,
      tool: live.tool,
      status: live.status,
      progress: live.progress,
      stage: live.stage,
      error: live.error,
      candidates: [],
      prompt: null, // 快照兜底构造：prompt 只来自快照，帧合并不涉及
      created_at: '',
      started_at: null,
      finished_at: null,
    }
    return { ...base, status: live.status, progress: live.progress, stage: live.stage, error: live.error }
  }
  return snap ?? null
}

export function useRun(runId: string | undefined) {
  const queryClient = useQueryClient()
  const [live, setLive] = useState<RunFrame | null>(null)
  // 切任务时在渲染期重置实时帧（React 认可的"随 props 调整 state"模式）
  const [lastRunId, setLastRunId] = useState(runId)
  if (lastRunId !== runId) {
    setLastRunId(runId)
    setLive(null)
  }

  const query = useQuery({
    queryKey: runKey(runId ?? 'none'),
    queryFn: () => runsApi.get(runId!),
    enabled: Boolean(runId),
  })

  const snapshotStatus = query.data?.status
  const snapshotTerminal = snapshotStatus !== undefined && isTerminal(snapshotStatus)

  useEffect(() => {
    // 终态短路：快照已终态（或尚未取得快照）不建连——终态会话零 SSE 连接
    if (!runId || !snapshotStatus || snapshotTerminal) return

    const source = new EventSource(`/events/runs/${runId}`)
    source.onmessage = (event) => {
      const frame = JSON.parse(event.data as string) as RunFrame
      if (frame.id !== runId) return // 帧校验：旧任务的迟到帧不渲染
      setLive(frame)
      if (isTerminal(frame.status)) {
        source.close()
        // 候选图列表来自快照而非事件：终态帧只负责触发快照失效
        queryClient.invalidateQueries({ queryKey: runKey(runId) })
      }
    }
    // 无 onerror 兜底：EventSource 自带自动重连（服务端重连先播快照帧），
    // 主动 close+invalidate 会让断连期间界面失去实时性
    return () => source.close()
  }, [runId, snapshotStatus, snapshotTerminal, queryClient])

  const run = useMemo(() => merge(query.data, live), [query.data, live])

  return {
    run,
    /** 快照 404（任务不存在/非本人）时为 true。 */
    notFound: query.error instanceof ApiError && query.error.status === 404,
    isPending: query.isPending,
  }
}
