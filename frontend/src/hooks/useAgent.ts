/** 对话钩子：turns 查询（挂会话键族）+ useSendMessage。
 * turns key ['session', id, 'messages'] 与 detail/history 同族——
 * 终态一次 invalidate 前缀 ['session', id] 全刷，自立门户的 key 会漏掉消息列表。
 * 发送成功（规划 201）也 invalidate 会话前缀：回复即时进详情缓存。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { agentApi } from '@/api/agent'
import { sessionKey } from '@/hooks/useSessions'

export const sessionMessagesKey = (id: string) => ['session', id, 'messages'] as const

export function useAgentTurns(sessionId: string | undefined) {
  return useQuery({
    queryKey: sessionMessagesKey(sessionId ?? 'none'),
    queryFn: () => agentApi.turns(sessionId!),
    enabled: Boolean(sessionId),
  })
}

export function useSendMessage(sessionId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (text: string) => agentApi.send(sessionId!, text),
    onSuccess: () => {
      // 前缀命中详情/历史/消息（与工具终态刷新同族）
      if (sessionId) queryClient.invalidateQueries({ queryKey: sessionKey(sessionId) })
    },
  })
}
