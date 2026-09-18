/** 会话侧栏（对话化左栏）：顶部「新对话」+「历史」开关（默认收起，纵向空间留给对话）；
 * 历史列表限高滚动；无 activeId 显示引导文案；有 activeId 时下半部为
 * AgentConversation + MessageComposer——"会话"从数据结构成为交互主体。 */
import { useState } from 'react'
import { Link, NavLink, useParams } from 'react-router-dom'

import AgentConversation from '@/components/editor/AgentConversation'
import MessageComposer from '@/components/editor/MessageComposer'
import { errorMessage } from '@/hooks/useAuth'
import { useAgentTurns, useSendMessage } from '@/hooks/useAgent'
import { useSessions } from '@/hooks/useSessions'

export default function SessionSidebar() {
  const { sessionId } = useParams()
  const sessionsQuery = useSessions()
  const sessions = sessionsQuery.data ?? []
  const turnsQuery = useAgentTurns(sessionId)
  const sendMessage = useSendMessage(sessionId)
  // 历史开关默认收起：用户在对话里的时间是绝大多数，纵向空间给最高频的职能
  const [historyOpen, setHistoryOpen] = useState(false)

  return (
    <aside className="flex w-72 shrink-0 flex-col overflow-hidden border-r border-line bg-paper">
      <div className="flex shrink-0 gap-2 border-b border-line p-3">
        <Link
          to="/create"
          className="flex-1 rounded-control bg-brand px-3 py-2 text-center text-sm font-medium text-paper shadow-control transition-colors hover:bg-brand-strong"
        >
          新对话
        </Link>
        <button
          type="button"
          aria-pressed={historyOpen}
          onClick={() => setHistoryOpen((open) => !open)}
          className="rounded-control border border-line px-3 py-2 text-sm text-muted transition-colors hover:bg-brand-soft hover:text-brand-strong aria-pressed:bg-brand-soft aria-pressed:text-brand-strong"
        >
          历史
        </button>
      </div>

      {historyOpen && (
        <nav
          className="max-h-48 shrink-0 overflow-y-auto border-b border-line p-2"
          aria-label="历史会话"
        >
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
      )}

      {sessionId ? (
        <>
          <AgentConversation turns={turnsQuery.data ?? []} sessionId={sessionId} />
          {sendMessage.error && (
            <p role="alert" className="shrink-0 bg-danger/10 px-3 py-1 text-xs text-danger">
              {errorMessage(sendMessage.error)}
            </p>
          )}
          <MessageComposer
            pending={sendMessage.isPending}
            onSend={(text) => sendMessage.mutate(text)}
          />
        </>
      ) : (
        <div className="flex flex-1 items-center justify-center p-4 text-center">
          <p className="text-xs text-muted">
            在画布中打开一个会话，就能用一句话修图。
          </p>
        </div>
      )}
    </aside>
  )
}
