/** 会话钩子：认证态是数据不是异常——/me 401 返回 null 不抛错，守卫加载期保持中性画面。 */
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'

import { authApi, type User } from '@/api/auth'
import { ApiError } from '@/api/client'

export const AUTH_ME_KEY = ['auth', 'me'] as const

export function useCurrentUser() {
  return useQuery({
    queryKey: AUTH_ME_KEY,
    queryFn: async (): Promise<User | null> => {
      try {
        return await authApi.me()
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          return null
        }
        throw error
      }
    },
    retry: false,
    staleTime: Infinity,
  })
}

export function useAuthActions() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()

  const handleAuthenticated = (user: User) => {
    // 注册即建会话：登录/注册成功直接写入缓存，不等二次 /me
    queryClient.setQueryData(AUTH_ME_KEY, user)
    navigate('/create', { replace: true })
  }

  const login = useMutation({ mutationFn: authApi.login, onSuccess: handleAuthenticated })
  const register = useMutation({ mutationFn: authApi.register, onSuccess: handleAuthenticated })

  const logout = useMutation({
    mutationFn: authApi.logout,
    onSuccess: () => {
      // 登出清空整个查询缓存：换账号后任何残留缓存都是跨账号串号
      queryClient.clear()
      navigate('/', { replace: true })
    },
  })

  return { login, register, logout }
}

/** 表单错误文案提取：ApiError 的 detail（后端中文消息）优先，后续表单复用。 */
export function errorMessage(error: unknown): string | null {
  if (error instanceof ApiError) return error.message
  if (error) return '请求失败，请稍后再试'
  return null
}
