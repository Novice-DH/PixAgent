import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { api } from '@/api/client'

interface HealthStatus {
  api: string
  database: string
}

type HealthState = 'ok' | 'error' | 'unreachable'

const DOT_COLOR: Record<HealthState, string> = {
  ok: 'bg-success',
  error: 'bg-danger',
  unreachable: 'bg-danger',
}

function StatusDot({ label, state }: { label: string; state: HealthState }) {
  return (
    <div className="flex items-center gap-2">
      <span className={`inline-block h-2.5 w-2.5 rounded-full ${DOT_COLOR[state]}`} />
      <span className="text-sm text-muted">
        {label}: {state}
      </span>
    </div>
  )
}

/** 落地页：本期最小版，后续期次会拆组件重构。 */
export default function LandingPage() {
  const healthQuery = useQuery({
    queryKey: ['health'],
    queryFn: () => api.get<HealthStatus>('/health'),
  })

  const health = healthQuery.data
  const apiState: HealthState = health ? (health.api === 'ok' ? 'ok' : 'error') : 'unreachable'
  const dbState: HealthState = health ? (health.database === 'ok' ? 'ok' : 'error') : 'unreachable'

  return (
    <main className="mx-auto flex min-h-screen max-w-3xl flex-col justify-center gap-8 px-6 py-16">
      <header className="flex flex-col gap-3">
        <h1 className="text-4xl font-semibold tracking-tight">AI 修图智能体</h1>
        <p className="max-w-xl text-base text-muted">
          一句话生成商品图，或上传后继续编辑，自动串联抠图、换背景、局部修改与多尺寸导出。
        </p>
      </header>

      <div>
        <Link
          to="/create"
          className="inline-flex items-center gap-2 rounded-control bg-brand px-5 py-2.5 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
        >
          进入工作台
        </Link>
      </div>

      <section className="rounded-card border border-line bg-paper p-5 shadow-card">
        <h2 className="mb-3 text-sm font-medium text-ink">服务健康</h2>
        <div className="flex flex-col gap-2">
          <StatusDot label="api" state={apiState} />
          <StatusDot label="database" state={dbState} />
        </div>
      </section>
    </main>
  )
}
