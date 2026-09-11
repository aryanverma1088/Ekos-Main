import { useState } from 'react'
import { NavLink, Outlet, useLocation } from 'react-router-dom'

const NAV_ITEMS = [
  { to: '/', label: 'Dashboard', end: true },
  { to: '/search', label: 'Search' },
  { to: '/graph', label: 'Knowledge Graph' },
  { to: '/integrity', label: 'Integrity Center' },
  { to: '/documents', label: 'Documents' },
]

function SidebarContent({ onNavigate }) {
  return (
    <>
      <div className="px-5 py-6 border-b border-border-soft">
        <div className="flex items-center gap-3">
          <span className="brand-mark">E/</span>
          <div>
            <p className="font-display text-[22px] text-paper tracking-tight leading-none">EKOS</p>
            <p className="text-[10px] font-mono text-muted mt-1 uppercase tracking-[0.16em]">
              Knowledge OS
            </p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-5 flex flex-col gap-1">
        <p className="px-3 pb-2 text-[10px] font-mono uppercase tracking-[0.16em] text-muted-soft">
          Workspace
        </p>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={({ isActive }) =>
              `px-3 py-2 rounded-md text-sm transition-colors ${
                isActive
                  ? 'bg-verified-soft text-verified-paper font-medium shadow-sm'
                  : 'text-muted hover:text-paper hover:bg-ink-soft'
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>

      <div className="px-5 py-4 border-t border-border-soft">
        <div className="flex items-center gap-2 text-[11px] font-mono text-muted-soft">
          <span className="inline-block w-1.5 h-1.5 rounded-full bg-verified" />
          <span>System operational</span>
        </div>
      </div>
    </>
  )
}

export default function Layout() {
  const [mobileOpen, setMobileOpen] = useState(false)
  const location = useLocation()

  return (
    <div className="app-shell min-h-screen flex bg-ink">
      {/* Desktop rail */}
      <aside className="app-rail hidden md:flex w-60 shrink-0 border-r border-border-soft flex-col">
        <SidebarContent />
      </aside>

      {/* Mobile top bar */}
      <div className="md:hidden fixed top-0 left-0 right-0 z-30 flex items-center justify-between px-4 h-14 border-b border-border-soft bg-surface/95 backdrop-blur">
        <div className="flex items-center gap-2"><span className="brand-mark !w-8 !h-8">E/</span><p className="font-display text-lg text-paper">EKOS</p></div>
        <button
          onClick={() => setMobileOpen(true)}
          aria-label="Open navigation"
          className="text-paper p-2 -mr-2"
        >
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
            <path d="M2 5h16M2 10h16M2 15h16" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
        </button>
      </div>

      {/* Mobile drawer */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-40 flex">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setMobileOpen(false)}
          />
          <aside className="app-rail relative w-64 bg-surface border-r border-border-soft flex flex-col z-50">
            <SidebarContent onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      )}

      <main className="flex-1 min-w-0 pt-14 md:pt-0">
        <div key={location.pathname} className="page-transition">
          <Outlet />
        </div>
      </main>
    </div>
  )
}
