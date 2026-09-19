/** 会话钩子：列表 / 详情 / 历史 + 建会话 / 改会话 / 工具调用与撤销重做。
 * 查询键族：['sessions'] / ['session', id] / ['session', id, 'history']；
 * 写成功后 setQueryData 写详情 + invalidate 列表（patch 再 invalidate 历史）。
 * 反馈挂点（S11）：invoke/undo/redo 网络失败弹 danger toast；像素工具经 SSE
 * 到终态时 failed→danger（错误文案）、成功→阶段完成文案（撤销/重做失败此前无任何提示）。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useRef } from 'react'

import { actionLabel } from '@/api/sessions'
import { isTerminal } from '@/api/runs'
import type { SessionDetail, SessionPatchInput } from '@/api/sessions'
import { sessionsApi } from '@/api/sessions'
import { errorMessage } from '@/hooks/useAuth'
import { useRun } from '@/hooks/useRun'
import { toast } from '@/stores/toasts'

export const SESSIONS_KEY = ['sessions'] as const
export const sessionKey = (id: string) => ['session', id] as const
export const sessionHistoryKey = (id: string) => ['session', id, 'history'] as const

export function useSessions() {
  return useQuery({ queryKey: SESSIONS_KEY, queryFn: () => sessionsApi.list() })
}

export function useSession(sessionId: string | undefined) {
  return useQuery({
    queryKey: sessionKey(sessionId ?? 'none'),
    queryFn: () => sessionsApi.get(sessionId!),
    enabled: Boolean(sessionId),
  })
}

export function useSessionHistory(sessionId: string | undefined) {
  return useQuery({
    queryKey: sessionHistoryKey(sessionId ?? 'none'),
    queryFn: () => sessionsApi.history(sessionId!),
    enabled: Boolean(sessionId),
  })
}

export function useCreateSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: sessionsApi.create,
    onSuccess: (detail: SessionDetail) => {
      queryClient.setQueryData(sessionKey(detail.id), detail)
      queryClient.invalidateQueries({ queryKey: SESSIONS_KEY })
    },
  })
}

export function usePatchSession() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: ({ sessionId, input }: { sessionId: string; input: SessionPatchInput }) =>
      sessionsApi.patch(sessionId, input),
    onSuccess: (detail: SessionDetail) => {
      queryClient.setQueryData(sessionKey(detail.id), detail)
      queryClient.invalidateQueries({ queryKey: SESSIONS_KEY })
      queryClient.invalidateQueries({ queryKey: sessionHistoryKey(detail.id) })
    },
  })
}

/** 工具调用与撤销/重做：202 受理即完成也是受理——同步文档工具响应内已带终态
 * run 与新会话（零轮询）；像素工具 run 非终态时挂 useRun 双源跟踪，终态再失效。
 * busy 覆盖全部交互禁用面（工具栏/滑杆/图片墙），pendingStage 供画布情境提示。 */
export function useSessionTools(sessionId: string | undefined) {
  const queryClient = useQueryClient()
  const invoke = useMutation({
    mutationFn: ({ tool, params }: { tool: string; params?: Record<string, unknown> }) => {
      if (!sessionId) return Promise.reject(new Error('未选择会话'))
      return sessionsApi.invoke(sessionId, tool, params)
    },
    onSuccess: (result) => {
      queryClient.setQueryData(sessionKey(result.session.id), result.session)
      queryClient.invalidateQueries({ queryKey: SESSIONS_KEY })
      queryClient.invalidateQueries({ queryKey: sessionHistoryKey(result.session.id) })
    },
    onError: (error) => {
      toast(errorMessage(error) ?? '调用失败，请重试', 'danger')
    },
  })
  const undo = useMutation({
    mutationFn: () => {
      if (!sessionId) return Promise.reject(new Error('未选择会话'))
      return sessionsApi.undo(sessionId)
    },
    onSuccess: (detail: SessionDetail) => {
      queryClient.setQueryData(sessionKey(detail.id), detail)
      queryClient.invalidateQueries({ queryKey: SESSIONS_KEY })
      queryClient.invalidateQueries({ queryKey: sessionHistoryKey(detail.id) })
    },
    onError: (error) => {
      toast(errorMessage(error) ?? '撤销失败', 'danger')
    },
  })
  const redo = useMutation({
    mutationFn: () => {
      if (!sessionId) return Promise.reject(new Error('未选择会话'))
      return sessionsApi.redo(sessionId)
    },
    onSuccess: (detail: SessionDetail) => {
      queryClient.setQueryData(sessionKey(detail.id), detail)
      queryClient.invalidateQueries({ queryKey: SESSIONS_KEY })
      queryClient.invalidateQueries({ queryKey: sessionHistoryKey(detail.id) })
    },
    onError: (error) => {
      toast(errorMessage(error) ?? '重做失败', 'danger')
    },
  })

  // 像素工具走队列：受理响应内 run 非终态 → 挂双源进度，终态失效详情/历史
  const asyncRunId =
    invoke.data && !isTerminal(invoke.data.run.status) ? invoke.data.run.id : undefined
  const tracked = useRun(asyncRunId)
  const trackedStatus = tracked.run?.status
  useEffect(() => {
    if (!sessionId || !asyncRunId || !trackedStatus || !isTerminal(trackedStatus)) return
    queryClient.invalidateQueries({ queryKey: sessionKey(sessionId) }) // 前缀命中详情/历史/消息
    queryClient.invalidateQueries({ queryKey: SESSIONS_KEY })
  }, [sessionId, asyncRunId, trackedStatus, queryClient])

  // 像素工具终态通知（每个 run 只弹一次）：失败含错误文案，成功弹阶段完成文案
  const notifiedRunRef = useRef<string | null>(null)
  useEffect(() => {
    const run = tracked.run
    if (!asyncRunId || !run || !isTerminal(run.status)) return
    if (notifiedRunRef.current === asyncRunId) return
    notifiedRunRef.current = asyncRunId
    const label = invoke.data ? actionLabel(invoke.data.run.tool) : '处理'
    if (run.status === 'failed') {
      toast(`${label}失败：${run.error ?? '请重试'}`, 'danger')
    } else if (run.status === 'succeeded') {
      toast(`${label}完成`, 'ok')
    } else {
      toast(`${label}已取消`, 'ok')
    }
  }, [tracked.run, asyncRunId, invoke.data])

  const pixelPending = Boolean(asyncRunId && tracked.run && !isTerminal(tracked.run.status))
  return {
    invoke,
    undo,
    redo,
    /** 全部交互的统一禁用面 */
    busy: invoke.isPending || undo.isPending || redo.isPending || pixelPending,
    /** 像素工具执行中的阶段与百分比（画布情境提示用） */
    pendingStage: pixelPending ? (tracked.run?.stage ?? '处理中') : null,
    pendingProgress: pixelPending ? (tracked.run?.progress ?? 0) : 0,
  }
}
