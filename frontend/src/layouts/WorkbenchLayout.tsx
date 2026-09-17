import { NavLink, Outlet } from 'react-router-dom'

const NAV_ITEMS = [
  {
    to: '/create',
    label: '创作',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <path d="M12 4l1.8 5.2L19 11l-5.2 1.8L12 18l-1.8-5.2L5 11l5.2-1.8Z" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    to: '/editor',
    label: '编辑器',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <rect x="4" y="4" width="16" height="16" rx="3" />
        <path d="M4 14l4-4 5 5 3-3 4 4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    to: '/batch',
    label: '批量',
    icon: (
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" aria-hidden="true">
        <rect x="4" y="4" width="7" height="7" rx="2" />
        <rect x="13" y="4" width="7" height="7" rx="2" />
        <rect x="4" y="13" width="7" height="7" rx="2" />
        <rect x="13" y="13" width="7" height="7" rx="2" />
      </svg>
    ),
  },
]

/** 工作台布局：左侧导航默认 w-16 仅图标，悬停展开 w-52 显示文字。 */
export default function WorkbenchLayout() {
  return (
    <div className="flex min-h-screen">
      <nav className="group flex w-16 flex-col gap-2 overflow-hidden border-r border-line bg-paper p-3 transition-[width] duration-200 hover:w-52">
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            className="flex items-center gap-3 rounded-control px-2.5 py-2 text-sm text-muted hover:bg-brand-soft hover:text-brand-strong aria-[current=page]:bg-brand-soft aria-[current=page]:text-brand-strong"
          >
            <span className="h-5 w-5 shrink-0">{item.icon}</span>
            <span className="whitespace-nowrap opacity-0 transition-opacity group-hover:opacity-100">
              {item.label}
            </span>
          </NavLink>
        ))}
      </nav>
      <main className="min-w-0 flex-1">
        <Outlet />
      </main>
    </div>
  )
}
