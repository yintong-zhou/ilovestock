import type { ReactNode } from 'react'

export type Page = 'dashboard' | 'portfolio' | 'screener' | 'analysis' | 'history' | 'watchlist' | 'settings'

// Consistent line icons (brand: line iconography), 20px, stroke = currentColor.
function Icon({ children }: { children: ReactNode }) {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.75"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0">
      {children}
    </svg>
  )
}

const NAV: { page: Page; label: string; icon: ReactNode }[] = [
  { page: 'dashboard', label: 'Dashboard', icon: <Icon><path d="M4 20V10M10 20V4M16 20v-7M22 20H2" /></Icon> },
  { page: 'portfolio', label: 'Portfolio', icon: <Icon><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" /></Icon> },
  { page: 'screener', label: 'Screener', icon: <Icon><path d="M3 4h18l-7 8v6l-4 2v-8z" /></Icon> },
  { page: 'analysis', label: 'Analysis', icon: <Icon><circle cx="11" cy="11" r="7" /><path d="m20 20-3.5-3.5" /></Icon> },
  { page: 'history', label: 'History', icon: <Icon><circle cx="12" cy="12" r="9" /><path d="M12 7v5l3 2" /></Icon> },
  { page: 'watchlist', label: 'Watchlist', icon: <Icon><path d="M6 3h12v18l-6-4-6 4z" /></Icon> },
  { page: 'settings', label: 'Settings', icon: <Icon><circle cx="12" cy="12" r="3" /><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9l2.1 2.1M17 17l2.1 2.1M4.9 19.1 7 17M17 7l2.1-2.1" /></Icon> },
]

export function Wordmark() {
  return (
    <span className="inline-flex items-center gap-2 font-heading text-xl font-bold tracking-tight">
      <img src="/logo.png" alt="" width={32} height={32} />
      iLoveStock
    </span>
  )
}

/** Left column on desktop, top bar below 768px. */
export default function Sidebar({ page, onLock }: { page: Page; onLock: () => void }) {
  return (
    <nav
      aria-label="Main"
      className="flex items-center gap-4 overflow-x-auto bg-navy px-4 py-2 md:fixed md:inset-y-0 md:left-0 md:w-60 md:flex-col md:items-stretch md:gap-0 md:overflow-visible md:p-0"
    >
      <div className="shrink-0 md:flex md:h-20 md:items-center md:pl-[26px]">
        <Wordmark />
      </div>
      <ul className="flex gap-1 md:mt-2 md:flex-1 md:flex-col md:px-3">
        {NAV.map((item) => {
          const active = page === item.page
          return (
            <li key={item.page}>
              <a
                href={`#${item.page}`}
                aria-current={active ? 'page' : undefined}
                className={`flex h-10 items-center gap-3 rounded-sm border-l-2 px-3 whitespace-nowrap transition-colors ${
                  active
                    ? 'border-teal-tint bg-white/10 font-semibold text-text'
                    : 'border-transparent text-text/75 hover:bg-white/5 hover:text-text'
                }`}
              >
                {item.icon}
                {item.label}
              </a>
            </li>
          )
        })}
      </ul>
      <div className="ml-auto shrink-0 md:ml-0 md:border-t md:border-white/10 md:px-3 md:py-4">
        <button
          onClick={onLock}
          className="flex h-10 w-full items-center gap-3 rounded-sm border-l-2 border-transparent px-3 text-text/75 transition-colors hover:bg-white/5 hover:text-text"
        >
          <Icon><rect x="5" y="11" width="14" height="10" rx="2" /><path d="M8 11V7a4 4 0 0 1 8 0v4" /></Icon>
          Lock
        </button>
        <p className="mt-4 hidden pl-[14px] text-xs leading-relaxed text-text/60 md:block">
          Educational screening tool, not financial advice.
        </p>
      </div>
    </nav>
  )
}
