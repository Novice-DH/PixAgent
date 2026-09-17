/** 顶栏：sticky 置顶 + 半透明模糊；左品牌链接，右登录态账户入口。 */
import { Link } from 'react-router-dom'

import BrandMark from '@/components/BrandMark'
import type { User } from '@/api/auth'

type LandingHeaderProps = {
  user: User | null
  isPending: boolean
}

export default function LandingHeader({ user, isPending }: LandingHeaderProps) {
  return (
    <header className="sticky top-0 z-20 border-b border-line/70 bg-paper/80 backdrop-blur">
      <div className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-3.5">
        <Link to="/" className="flex items-center" aria-label="AI 修图智能体 首页">
          <BrandMark size="sm" withText />
        </Link>

        {/* 登录态感知：加载期保持中性占位，避免已登录用户看到「登录」闪一下 */}
        {isPending ? (
          <span className="h-9 w-24 animate-pulse rounded-control bg-soft" aria-hidden="true" />
        ) : user ? (
          <Link
            to="/create"
            className="rounded-control bg-brand px-4 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
          >
            {user.username} · 进入工作台
          </Link>
        ) : (
          <Link
            to="/auth"
            className="rounded-control border border-line-strong bg-paper px-4 py-2 text-sm font-medium text-ink transition-colors hover:border-brand hover:text-brand-strong"
          >
            登录
          </Link>
        )}
      </div>
    </header>
  )
}
