/** 会话侧栏（编辑页左缘）：对象域导航——「新对话」+ 会话列表（服务端按更新时间倒序）。
 * 应用域导航在 WorkbenchLayout，这里只管"哪个会话"；当前高亮由 NavLink 按 URL 匹配。 */
import { Link, NavLink } from 'react-router-dom'

import { useSessions } from '@/hooks/useSessions'

export default function SessionSidebar() {
  const sessionsQuery = useSessions()
  const sessions = sessionsQuery.data ?? []

  return (
    <aside className="flex w-52 shrink-0 flex-col overflow-hidden border-r border-line bg-paper">
      <div className="border-b border-line p-3">
        <Link
          to="/create"
          className="flex items-center justify-center rounded-control bg-brand px-3 py-2 text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
        >
          新对话
        </Link>
      </div>

      <nav className="flex min-h-0 flex-1 flex-col gap-0.5 overflow-y-auto p-2" aria-label="会话列表">
        {sessionsQuery.isPending && <p className="px-2 py-1 text-xs text-muted">正在加载会话…</p>}
        {!sessionsQuery.isPending && sessions.length === 0 && (
          <p className="px-2 py-1 text-xs text-muted">还没有会话，先去创作一张。</p>
        )}
        {sessions.map((session) => (
          <NavLink
            key={session.id}
            to={`/editor/${session.id}`}
            className="rounded-control px-2.5 py-2 text-sm text-muted hover:bg-brand-soft hover:text-brand-strong aria-[current=page]:bg-brand-soft aria-[current=page]:text-brand-strong"
          >
            <span className="block truncate" title={session.title}>
              {session.title}
            </span>
          </NavLink>
        ))}
      </nav>
    </aside>
  )
}
