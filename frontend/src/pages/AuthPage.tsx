/** 认证页：login / register 双模式由 ?mode= 驱动，注册即建会话，成功一律进 /create。
 * 本期仅视觉包装（品牌卡片面板），表单行为契约逐项保留。 */
import { useState } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'

import BrandMark from '@/components/BrandMark'
import { errorMessage, useAuthActions, useCurrentUser } from '@/hooks/useAuth'

type AuthMode = 'login' | 'register'

const USERNAME_PATTERN = /^\w+$/

function validate(username: string, password: string): string | null {
  const trimmed = username.trim()
  if (trimmed.length < 3 || trimmed.length > 32 || !USERNAME_PATTERN.test(trimmed)) {
    return '用户名需为 3–32 位字母、数字或下划线'
  }
  if (password.length < 6 || password.length > 64) {
    return '密码长度需为 6–64 位'
  }
  // 与后端一致：bcrypt 只接受 72 字节以内，多字节字符提前拦下
  if (new TextEncoder().encode(password).length > 72) {
    return '密码过长（UTF-8 编码需不超过 72 字节）'
  }
  return null
}

export default function AuthPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const mode: AuthMode = searchParams.get('mode') === 'register' ? 'register' : 'login'
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [clientError, setClientError] = useState<string | null>(null)

  const { data: user, isPending } = useCurrentUser()
  const { login, register } = useAuthActions()
  const mutation = mode === 'login' ? login : register

  // 会话还在加载时不渲染表单，避免已登录用户先看到表单再被重定向的闪烁
  if (isPending) {
    return (
      <main className="flex min-h-screen items-center justify-center text-sm text-muted">
        正在检查登录状态…
      </main>
    )
  }
  // 已登录访问 /auth → 直接进工作台
  if (user) {
    return <Navigate to="/create" replace />
  }

  const switchMode = (next: AuthMode) => {
    setClientError(null)
    setSearchParams(next === 'register' ? { mode: 'register' } : {})
  }

  const handleSubmit = (event: React.FormEvent) => {
    event.preventDefault()
    const problem = validate(username, password)
    if (problem) {
      setClientError(problem)
      return
    }
    setClientError(null)
    mutation.mutate({ username: username.trim(), password })
  }

  const bannerError = clientError ?? errorMessage(mutation.error)

  return (
    <main className="relative flex min-h-screen items-center justify-center bg-glow px-4 py-12">
      <div className="relative w-full max-w-sm">
        <div className="rounded-panel border border-line bg-paper p-6 shadow-panel sm:p-8">
          <div className="mb-6 text-center">
            <div className="mb-3 flex justify-center">
              <BrandMark size="md" />
            </div>
            <h1 className="text-xl font-semibold tracking-tight">
              {mode === 'login' ? '登录' : '创建账号'}
            </h1>
            <p className="mt-1 text-sm text-muted">
              {mode === 'login' ? '继续你的修图工作台' : '一句话生成可投放的商品图'}
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-muted">用户名</span>
              <input
                name="username"
                autoComplete="username"
                placeholder="3–32 位字母、数字或下划线"
                value={username}
                onChange={(event) => setUsername(event.target.value)}
                className="rounded-control border border-line bg-soft px-3 py-2 text-ink outline-none placeholder:text-faint focus:border-brand"
              />
            </label>

            <label className="flex flex-col gap-1.5 text-sm">
              <span className="text-muted">密码</span>
              <input
                name="password"
                type="password"
                autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                placeholder="6–64 位"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                className="rounded-control border border-line bg-soft px-3 py-2 text-ink outline-none placeholder:text-faint focus:border-brand"
              />
            </label>

            {bannerError && (
              <p role="alert" className="rounded-control bg-danger/10 px-3 py-2 text-sm text-danger">
                {bannerError}
              </p>
            )}

            <button
              type="submit"
              disabled={mutation.isPending}
              className="rounded-control bg-brand px-4 py-2.5 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong disabled:opacity-60"
            >
              {mutation.isPending ? '请稍候…' : mode === 'login' ? '登录' : '注册并开始'}
            </button>
          </form>
        </div>

        <p className="mt-4 text-center text-sm text-muted">
          {mode === 'login' ? '还没有账号？' : '已有账号？'}
          <button
            type="button"
            onClick={() => switchMode(mode === 'login' ? 'register' : 'login')}
            className="ml-1 text-brand-strong hover:underline"
          >
            {mode === 'login' ? '免费注册' : '直接登录'}
          </button>
        </p>

        <Link to="/" className="mt-2 block text-center text-sm text-faint transition-colors hover:text-ink">
          ← 返回首页
        </Link>
      </div>
    </main>
  )
}
