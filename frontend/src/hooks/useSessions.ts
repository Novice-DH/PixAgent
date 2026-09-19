/** 会话钩子：列表 / 详情 / 历史 + 建会话 / 改会话 / 工具调用与撤销重做。
 * 查询键族：['sessions'] / ['session', id] / ['session', id, 'history']；
 * 写成功后 setQueryData 写详情 + invalidate 列表（patch 再 invalidate 历史）。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect } from 'react'

import { isTerminal } from '@/api/runs'
import type { SessionDetail, SessionPatchInput } from '@/api/sessions'
import { sessionsApi } from '@/api/sessions'
import { useRun } from '@/hooks/useRun'

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
 * busy 覆盖全部交互禁用面（工具栏/滑杆/图片墙），pendingStage 供顶部提示条。 */
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

  const pixelPending = Boolean(asyncRunId && tracked.run && !isTerminal(tracked.run.status))
  return {
    invoke,
    undo,
    redo,
    /** 全部交互的统一禁用面 */
    busy: invoke.isPending || undo.isPending || redo.isPending || pixelPending,
    /** 像素工具执行中的阶段与百分比（顶部提示条用） */
    pendingStage: pixelPending ? (tracked.run?.stage ?? '处理中') : null,
    pendingProgress: pixelPending ? (tracked.run?.progress ?? 0) : 0,
  }
}
