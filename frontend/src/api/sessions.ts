/** 编辑会话 API：镜像后端全部结构（LayerDocument / 详情 / 图片墙 / 历史）。
 * 全部走统一 client（Cookie 自动携带）；签名 URL 由后端现算，前端只消费。 */
import type { Asset } from '@/api/assets'
import type { Run } from '@/api/runs'
import { api } from '@/api/client'

export type LayerKind = 'image' | 'text' | 'shape'

/** 图层形变：x/y 画布坐标，scale 倍率不是像素，rotation 角度。 */
export interface LayerTransform {
  x: number
  y: number
  scale_x: number
  scale_y: number
  rotation: number
}

export interface Layer {
  id: string
  kind: LayerKind
  name: string
  width: number
  height: number
  asset_id: string | null
  transform: LayerTransform
  opacity: number
  visible: boolean
  locked: boolean
}

/** 画布文档：当前状态的权威描述——渲染按它画，工具改它；视图缩放永不写入。 */
export interface LayerDocument {
  width: number
  height: number
  layers: Layer[]
}

export interface Session {
  id: string
  title: string
  revision: number
  /** 撤销指针：当前所处历史位置 */
  history_seq: number
  current_asset_id: string
  created_at: string
  updated_at: string
}

export interface WallAsset {
  position: number
  asset: Asset
}

export interface SessionDetail extends Session {
  document: LayerDocument
  wall: WallAsset[]
  /** 当前条目的 before 快照文档——对比模式的"前"侧；无快照为 null */
  previous_document: LayerDocument | null
  can_undo: boolean
  can_redo: boolean
}

export interface ToolInvokeResult {
  run: Run
  session: SessionDetail
}

export interface HistoryEntry {
  seq: number
  action: string
  params: Record<string, unknown>
  result: Record<string, unknown>
  created_at: string
}

/** 编辑动作中文案（编辑记录/步骤卡用；与后端注册表 label 手工同步）。 */
export const ACTION_LABELS: Record<string, string> = {
  create_session: '新建会话',
  switch_current: '切换当前图',
  generate_image: '生成图片',
  replace_background: '换背景',
  expand_canvas: '扩图',
  upscale_image: '超分',
  remove_background: '去背景',
  adjust_image: '调色',
  crop_canvas: '裁剪',
  flip_layer: '翻转',
  set_layer_opacity: '透明度',
  reorder_layer: '图层顺序',
  scale_layer: '缩放',
  rotate_layer: '旋转',
}

export function actionLabel(action: string): string {
  return ACTION_LABELS[action] ?? action
}

/** 素材分类中文角标（图片墙用），与后端 AssetKind 七值一一对应。 */
export const KIND_LABELS: Record<string, string> = {
  original: '原图',
  generated: '生成',
  subject: '主体',
  background: '背景',
  mask: '遮罩',
  marketing: '营销',
  export: '导出',
}

export interface SessionCreateInput {
  current_asset_id: string
  asset_ids?: string[]
  title?: string
}

export interface SessionPatchInput {
  title?: string
  current_asset_id?: string
}

// 会话端点恒有 JSON 响应（无 204 路径），api 层把 client 的 T|undefined 收窄为 T
async function expectJson<T>(promise: Promise<T | undefined>): Promise<T> {
  const body = await promise
  if (body === undefined) {
    throw new Error('会话接口响应缺失')
  }
  return body
}

export const sessionsApi = {
  create: (input: SessionCreateInput) => expectJson(api.post<SessionDetail>('/sessions', input)),
  list: (limit = 50) => expectJson(api.get<Session[]>(`/sessions?limit=${limit}`)),
  get: (sessionId: string) => expectJson(api.get<SessionDetail>(`/sessions/${sessionId}`)),
  patch: (sessionId: string, input: SessionPatchInput) =>
    expectJson(api.patch<SessionDetail>(`/sessions/${sessionId}`, input)),
  history: (sessionId: string) => expectJson(api.get<HistoryEntry[]>(`/sessions/${sessionId}/history`)),
  invoke: (sessionId: string, tool: string, params: Record<string, unknown> = {}) =>
    expectJson(
      api.post<ToolInvokeResult>(`/sessions/${sessionId}/tools`, { tool, params }),
    ),
  undo: (sessionId: string) =>
    expectJson(api.post<SessionDetail>(`/sessions/${sessionId}/undo`)),
  redo: (sessionId: string) =>
    expectJson(api.post<SessionDetail>(`/sessions/${sessionId}/redo`)),
}
