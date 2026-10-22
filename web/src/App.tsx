import { useCallback, useEffect, useState } from 'react'

import { api, ApiError } from './api'
import { Message } from './components'
import Analysis from './pages/Analysis'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Portfolio from './pages/Portfolio'
import Screener from './pages/Screener'
import Settings from './pages/Settings'
import PinScreen from './PinScreen'
import Sidebar, { type Page } from './Sidebar'
import type { AnalyzeOut, PinStatus, ScreenOut } from './types'

const PAGES: Page[] = ['dashboard', 'portfolio', 'screener', 'analysis', 'history', 'settings']

/** '#history/HZO' -> ['history', 'HZO']: page plus an optional argument. */
function routeFromHash(): [Page, string] {
  const [p, arg = ''] = decodeURIComponent(window.location.hash.slice(1)).split('/')
  return PAGES.includes(p as Page) ? [p as Page, arg] : ['dashboard', '']
}

export default function App() {
  const [status, setStatus] = useState<PinStatus | null>(null)
  const [error, setError] = useState('')
  const [[page, arg], setRoute] = useState(routeFromHash)
  // Latest analysis of this session, shared by Analysis and Dashboard (not stored on disk).
  const [lastRun, setLastRun] = useState<AnalyzeOut | null>(null)
  const [lastScreen, setLastScreen] = useState<ScreenOut | null>(null)

  const refresh = useCallback(() => {
    api.pinStatus().then(setStatus, (e: Error) => setError(e.message))
  }, [])

  useEffect(refresh, [refresh])

  useEffect(() => {
    const onHash = () => {
      setRoute(routeFromHash())
      window.scrollTo(0, 0) // each page opens at its top
    }
    window.addEventListener('hashchange', onHash)
    return () => window.removeEventListener('hashchange', onHash)
  }, [])

  // Any 401 from a page means the session ended (server restart, PIN changed elsewhere).
  const onApiError = useCallback(
    (e: unknown) => {
      if (e instanceof ApiError && e.status === 401) refresh()
    },
    [refresh],
  )

  if (error) {
    return (
      <main className="mx-auto max-w-xl p-10">
        <Message kind="error">
          Cannot reach the local server ({error}). Start it with <code>ilovestock serve</code> and reload.
        </Message>
      </main>
    )
  }
  if (!status) return null
  if (!status.configured) return <PinScreen mode="setup" onUnlocked={refresh} />
  if (!status.unlocked) return <PinScreen mode="unlock" onUnlocked={refresh} />

  async function lock() {
    await api.lock()
    setLastRun(null) // locked means nothing stays on screen or in page memory
    setLastScreen(null)
    refresh()
  }

  return (
    <>
      <Sidebar page={page} onLock={lock} />
      <main className="px-4 py-8 md:ml-60 md:px-10 md:py-10">
        <div className="max-w-[1200px]">
        {page === 'dashboard' && <Dashboard run={lastRun} />}
        {page === 'portfolio' && <Portfolio />}
        {page === 'screener' && <Screener result={lastScreen} onResult={setLastScreen} onApiError={onApiError} />}
        {page === 'analysis' && (
          <Analysis initialTickers={arg} run={lastRun} onRun={setLastRun} onApiError={onApiError} />
        )}
        {page === 'history' && <History ticker={arg} onApiError={onApiError} />}
        {page === 'settings' && <Settings onApiError={onApiError} />}
        </div>
      </main>
    </>
  )
}
