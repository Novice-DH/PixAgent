/** 路由守卫：isLoading 渲染中性加载态（已登录用户刷新不被闪踢），未登录才跳 /auth。 */
import { Navigate, Outlet } from 'react-router-dom'

import { useCurrentUser } from '@/hooks/useAuth'

export default function RequireAuth() {
  const { data: user, isPending } = useCurrentUser()

  if (isPending) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-muted">
        正在进入工作台…
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/auth" replace />
  }

  return <Outlet />
}
