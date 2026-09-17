/** 落地页：产品叙事页——品牌 header（登录态感知）+ hero + 四张能力卡。
 * 健康检查退位给 /api/health 与测试守护，界面不承载运维信息。 */
import { Link } from 'react-router-dom'

import { useCurrentUser } from '@/hooks/useAuth'

const CAPABILITIES = [
  {
    title: '一句话生成多候选',
    description: '描述商品与场景，一次产出四宫格候选图，挑最合适的一张继续打磨。',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M12 3l1.7 4.8L18.5 9.5l-4.8 1.7L12 16l-1.7-4.8L5.5 9.5l4.8-1.7Z" strokeLinejoin="round" />
        <path d="M18.5 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8Z" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: '主体级编辑，选区不外溢',
    description: '圈住主体说"改成 XX"，只动选区内的内容，背景与构图不受牵连。',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <rect x="4" y="4" width="16" height="16" rx="3" strokeDasharray="3 3" />
        <path d="M9 14l6-6" strokeLinecap="round" />
        <circle cx="14.5" cy="14.5" r="2.5" />
      </svg>
    ),
  },
  {
    title: '语义图层',
    description: '图层按内容理解拆分——商品、背景、文字各归其位，移动、替换、隐藏都听得懂。',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M12 3l9 5-9 5-9-5 9-5Z" strokeLinejoin="round" />
        <path d="M3 13l9 5 9-5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    title: '物料包多尺寸交付',
    description: '主图 1:1、详情 4:5、短视频封面 9:16，一张原图自动适配全渠道尺寸。',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <rect x="3" y="3" width="8" height="8" rx="2" />
        <rect x="13" y="3" width="8" height="6.5" rx="2" />
        <rect x="3" y="13" width="8" height="8" rx="2" />
        <rect x="13" y="11.5" width="5.5" height="9.5" rx="2" />
      </svg>
    ),
  },
]

export default function LandingPage() {
  const { data: user, isPending } = useCurrentUser()

  return (
    <div className="flex min-h-screen flex-col">
      <header className="mx-auto flex w-full max-w-5xl items-center justify-between px-6 py-5">
        <div className="flex items-center gap-2.5">
          <span className="flex h-8 w-8 items-center justify-center rounded-control bg-brand text-sm font-semibold text-paper">
            P
          </span>
          <span className="text-base font-semibold tracking-tight">AI 修图智能体</span>
        </div>

        {/* 登录态感知：加载期保持中性占位，避免已登录用户看到"登录"闪一下 */}
        {isPending ? (
          <span className="h-9 w-20 animate-pulse rounded-control bg-soft" aria-hidden="true" />
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
      </header>

      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col px-6">
        <section className="flex flex-col items-center gap-5 py-16 text-center md:py-24">
          <p className="rounded-control bg-brand-soft px-3 py-1 text-sm text-brand-strong">
            面向电商运营与内容创作者
          </p>
          <h1 className="max-w-2xl text-4xl font-semibold leading-tight tracking-tight md:text-5xl">
            一句话，生成可直接投放的商品图
          </h1>
          <p className="max-w-xl text-base text-muted">
            文生图起步，上传图片继续对话式编辑；抠图、换背景、局部修改与多尺寸导出自动串联，
            产出电商与营销物料。
          </p>
          <div className="mt-2 flex items-center gap-3">
            <Link
              to={user ? '/create' : '/auth?mode=register'}
              className="rounded-control bg-brand px-6 py-3 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
            >
              {user ? '进入工作台' : '免费开始'}
            </Link>
            {!user && (
              <Link to="/auth" className="px-2 py-3 text-sm text-muted hover:text-ink">
                已有账号？直接登录
              </Link>
            )}
          </div>
        </section>

        <section className="grid gap-4 pb-16 sm:grid-cols-2">
          {CAPABILITIES.map((capability) => (
            <article
              key={capability.title}
              className="flex flex-col gap-3 rounded-card border border-line bg-paper p-5 shadow-card"
            >
              <span className="flex h-10 w-10 items-center justify-center rounded-control bg-brand-soft text-brand-strong">
                {capability.icon}
              </span>
              <h2 className="text-base font-medium">{capability.title}</h2>
              <p className="text-sm leading-relaxed text-muted">{capability.description}</p>
            </article>
          ))}
        </section>
      </main>

      <footer className="border-t border-line py-5 text-center text-sm text-faint">
        PixAgent · 一句话生成商品图
      </footer>
    </div>
  )
}
