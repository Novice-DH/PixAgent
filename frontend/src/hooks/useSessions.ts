/** 会话钩子：列表 / 详情 / 历史 + 建会话 / 改会话。
 * 查询键族：['sessions'] / ['session', id] / ['session', id, 'history']；
 * 写成功后 setQueryData 写详情 + invalidate 列表（patch 再 invalidate 历史）。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import type { SessionDetail, SessionPatchInput } from '@/api/sessions'
import { sessionsApi } from '@/api/sessions'

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
