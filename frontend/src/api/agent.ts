/** 对话 API：Turn / PlanStep 类型 + agentApi；全部走统一 client（Cookie 自动携带）。 */
import { api } from '@/api/client'
import type { RunStatus } from '@/api/runs'

/** 一步工具调用：run_id 可空——校验被拒的步骤没有 run。 */
export interface PlanStep {
  tool: string
  label: string
  run_id: string | null
}

/** 一轮对话：status 只表示规划本身成败；执行状态在 PlanStep.run_id 对应的 Run 里。 */
export interface Turn {
  id: string
  revision: number
  goal: string
  reply: string
  status: RunStatus
  error: string | null
  created_at: string
  steps: PlanStep[]
}

export const agentApi = {
  turns: (sessionId: string) => api.get<Turn[]>(`/sessions/${sessionId}/messages`),
  send: (sessionId: string, text: string) =>
    api.post<Turn>(`/sessions/${sessionId}/messages`, { text }),
}
