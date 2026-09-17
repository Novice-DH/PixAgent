/** 素材 API：multipart 上传与列表走裸 fetch（统一 client 的默认 JSON 头会破坏 multipart 边界），
 * 错误语义仍抛 ApiError 保持一致；凭据经 httpOnly Cookie 自动携带。 */
import { ApiError } from '@/api/client'

export interface Asset {
  id: string
  kind: string
  source: string
  image_format: string
  width: number
  height: number
  size_bytes: number
  has_alpha: boolean
  created_at: string
  url: string
}

/** 与后端 probe 白名单保持一致（硬约束：两端白名单必须一致） */
export const ACCEPTED_TYPES: readonly string[] = ['image/jpeg', 'image/png', 'image/webp']
export const MAX_UPLOAD_BYTES = 20 * 1024 * 1024

async function toApiError(response: Response): Promise<ApiError> {
  let detail: string | undefined
  try {
    const payload = (await response.json()) as { detail?: string } | null
    detail = payload?.detail
  } catch {
    // 响应体不是 JSON 时退回状态文本
  }
  return new ApiError(response.status, detail ?? response.statusText)
}

export const assetsApi = {
  async upload(file: File): Promise<Asset> {
    const body = new FormData()
    body.append('file', file) // 不手写 Content-Type，让浏览器写 multipart boundary
    const response = await fetch('/api/assets', { method: 'POST', body })
    if (!response.ok) {
      throw await toApiError(response)
    }
    return (await response.json()) as Asset
  },

  async list(limit = 50): Promise<Asset[]> {
    const response = await fetch(`/api/assets?limit=${limit}`)
    if (!response.ok) {
      throw await toApiError(response)
    }
    return (await response.json()) as Asset[]
  },
}
