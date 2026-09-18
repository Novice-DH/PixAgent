/** 候选页：进度条（SSE 推进）→ 宫格选图 →「进入编辑」。
 * 状态机：notFound → 失效提示；failed/canceled → 失败原因 + 返回重试；
 * 未终态 → 进度；succeeded → 宫格。刷新恢复靠快照（useRun 双源合并）。 */
import { useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import type { RunCandidate } from '@/api/runs'
import { useRun } from '@/hooks/useRun'

/** 进度条视觉下限：0% 也呈现"有进度"的形态，避免与未加载混淆。 */
const MIN_VISUAL_PROGRESS = 4

export default function CandidatesPage() {
  const { runId } = useParams<{ runId: string }>()
  const navigate = useNavigate()
  const { run, notFound, isPending } = useRun(runId)
  const [picked, setPicked] = useState<string | null>(null)

  if (notFound) {
    return (
      <Centered>
        <h1 className="text-xl font-semibold tracking-tight">任务不存在</h1>
        <p className="text-sm text-muted">这个生成任务已失效或不属于当前账号。</p>
        <Link to="/create" className="text-sm text-brand-strong hover:underline">
          ← 返回创作页
        </Link>
      </Centered>
    )
  }

  if (isPending && !run) {
    return (
      <Centered>
        <p className="text-sm text-muted">正在加载任务…</p>
      </Centered>
    )
  }

  if (!run) {
    return (
      <Centered>
        <p className="text-sm text-muted">任务状态暂时未知，请刷新重试。</p>
      </Centered>
    )
  }

  if (run.status === 'failed' || run.status === 'canceled') {
    return (
      <Centered>
        <h1 className="text-xl font-semibold tracking-tight">
          {run.status === 'canceled' ? '任务已取消' : '生成失败'}
        </h1>
        {run.error && <p className="max-w-md text-sm text-danger">{run.error}</p>}
        <Link
          to="/create"
          className="rounded-control bg-brand px-4 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
        >
          返回重试
        </Link>
      </Centered>
    )
  }

  if (run.status !== 'succeeded') {
    const progress = Math.max(run.progress, MIN_VISUAL_PROGRESS)
    return (
      <Centered>
        <h1 className="text-xl font-semibold tracking-tight">正在生成候选图</h1>
        <div
          role="progressbar"
          aria-valuemin={0}
          aria-valuemax={100}
          aria-valuenow={run.progress}
          className="h-2 w-full max-w-md overflow-hidden rounded-control bg-canvas"
        >
          <div
            className="h-full rounded-control bg-brand transition-[width] duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
        <p className="text-sm text-muted">
          {run.stage} · {run.progress}%
        </p>
      </Centered>
    )
  }

  return (
    <div className="mx-auto flex w-full max-w-5xl flex-col gap-6 px-6 py-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">挑选一张候选图</h1>
          <p className="mt-1 text-sm text-muted">点选一张进入编辑器继续加工。</p>
        </div>
        <button
          type="button"
          disabled={!picked}
          onClick={() => picked && navigate(`/editor?asset=${picked}`)}
          className="rounded-control bg-brand px-4 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong disabled:opacity-50"
        >
          进入编辑
        </button>
      </header>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {run.candidates.map((candidate, index) => (
          <CandidateCard
            key={candidate.id}
            candidate={candidate}
            index={index + 1}
            picked={picked === candidate.id}
            onPick={() => setPicked(candidate.id)}
          />
        ))}
      </div>
    </div>
  )
}

function CandidateCard({
  candidate,
  index,
  picked,
  onPick,
}: {
  candidate: RunCandidate
  index: number
  picked: boolean
  onPick: () => void
}) {
  return (
    <button
      type="button"
      aria-pressed={picked}
      onClick={onPick}
      className={`relative overflow-hidden rounded-card border-2 bg-paper shadow-card transition-all ${
        picked ? 'border-brand ring-2 ring-brand/40' : 'border-transparent hover:border-line-strong'
      }`}
    >
      <img
        src={candidate.url}
        alt={`候选图 ${index}`}
        loading="lazy"
        className="aspect-[4/5] w-full object-cover"
      />
      <span className="absolute left-2 top-2 flex h-6 w-6 items-center justify-center rounded-full bg-dark/70 text-xs font-medium text-paper">
        {index}
      </span>
      {picked && (
        <span className="absolute bottom-2 left-1/2 -translate-x-1/2 rounded-control bg-brand px-2.5 py-0.5 text-xs font-medium text-paper">
          已选
        </span>
      )}
    </button>
  )
}

function Centered({ children }: { children: React.ReactNode }) {
  return (
    <section className="flex min-h-[60vh] flex-col items-center justify-center gap-3 px-6 text-center">
      {children}
    </section>
  )
}
