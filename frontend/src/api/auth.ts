/** 认证 API：四方法复用统一 client 与 ApiError；凭据经 httpOnly Cookie 自动携带，前端零令牌管理。 */
import { api } from '@/api/client'

export interface User {
  id: string
  username: string
}

export interface CredentialsInput {
  username: string
  password: string
}

/** register/login/me 恒有响应体（204 仅出现在 logout），缺失视为异常而非 undefined。 */
async function withBody<T>(promise: Promise<T | undefined>): Promise<T> {
  const data = await promise
  if (data === undefined) {
    throw new Error('认证响应缺失数据')
  }
  return data
}

export const authApi = {
  register: (body: CredentialsInput) => withBody(api.post<User>('/auth/register', body)),
  login: (body: CredentialsInput) => withBody(api.post<User>('/auth/login', body)),
  logout: () => api.post<void>('/auth/logout'),
  me: () => withBody(api.get<User>('/auth/me')),
}
