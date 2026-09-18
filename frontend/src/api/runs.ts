/** 生图任务 API：类型 + 比例文案 + runsApi；全部走统一 client（Cookie 自动携带）。 */
import { api } from '@/api/client'

export type Ratio = '1:1' | '4:5' | '3:4' | '9:16' | '16:9'

export type RunStatus = 'queued' | 'running' | 'succeeded' | 'failed' | 'canceled'

/** 比例 → 用户文案（表单分段选择器用）。 */
export const RATIO_LABELS: Record<Ratio, string> = {
  '1:1': '方形 1:1',
  '4:5': '竖版 4:5',
  '3:4': '竖版 3:4',
  '9:16': '长图 9:16',
  '16:9': '横版 16:9',
}

export const RATIOS: readonly Ratio[] = ['1:1', '4:5', '3:4', '9:16', '16:9']

export function isTerminal(status: RunStatus): boolean {
  return status === 'succeeded' || status === 'failed' || status === 'canceled'
}

export interface GenerateInput {
  prompt: string
  ratio: Ratio
  count: number
  negative_prompt?: string
}

export interface RunCandidate {
  id: string
  width: number
  height: number
  url: string
}

export interface Run {
  id: string
  tool: string
  status: RunStatus
  progress: number
  stage: string
  error: string | null
  candidates: RunCandidate[]
  /** 快照字段取自生成入参，候选页拿它当会话标题；SSE 帧六字段不变 */
  prompt: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
}

/** SSE 帧负载：快照字段，不含候选列表（候选图永远来自快照）。 */
export type RunFrame = Pick<Run, 'id' | 'tool' | 'status' | 'progress' | 'stage' | 'error'>

export const runsApi = {
  generate: (input: GenerateInput) => api.post<Run>('/generations', input),
  get: (runId: string) => api.get<Run>(`/runs/${runId}`),
}
