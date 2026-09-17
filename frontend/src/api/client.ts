/** 统一请求封装：base 路径 /api，非 2xx 抛 ApiError，204 返回 undefined。 */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

const BASE_PATH = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T | undefined> {
  const response = await fetch(`${BASE_PATH}${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (response.status === 204) {
    return undefined
  }

  if (!response.ok) {
    let payload: unknown = null
    try {
      payload = await response.json()
    } catch {
      // 响应体不是 JSON 时退回状态文本
    }
    const detail = (payload as { detail?: string } | null)?.detail
    throw new ApiError(response.status, detail ?? response.statusText)
  }

  return (await response.json()) as T
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: 'PATCH', body: body === undefined ? undefined : JSON.stringify(body) }),
  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
}
