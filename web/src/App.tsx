import { useCallback, useEffect, useRef, useState } from 'react'

import { api, ApiError } from './api'
import { Message } from './components'
import Analysis from './pages/Analysis'
import Dashboard from './pages/Dashboard'
import History from './pages/History'
import Log from './pages/Log'
import Portfolio from './pages/Portfolio'
import Screener from './pages/Screener'
import Settings from './pages/Settings'
import Watchlist from './pages/Watchlist'
import PinScreen from './PinScreen'
import Sidebar, { type Page } from './Sidebar'
import type { AnalyzeOut, PinStatus, ScreenOut } from './types'

const PAGES: Page[] = ['dashboard', 'portfolio', 'screener', 'analysis', 'history', 'watchlist', 'log', 'settings']

/** '#history/HZO' -> ['history', 'HZO']: page plus an optional argument. */
function routeFromHash(): [Page, string] {
  const [p, arg = ''] = decodeURIComponent(window.location.hash.slice(1)).split('/')
  return PAGES.includes(p as Page) ? [p as Page, arg] : ['dashboard', '']
}

export default function App() {
  const [status, setStatus] = useState<PinStatus | null>(null)
  const [error, setError] = useState('')
  const [[page, arg], setRoute] = useState(routeFromHash)
  // Latest analysis of this session: the Analysis page keeps it while you visit other pages.
  const [lastRun, setLastRun] = useState<AnalyzeOut | null>(null)
  const [lastScreen, setLastScreen] = useState<ScreenOut | null>(null)
  // A screen takes minutes, so it runs here, not in the page: leaving the page keeps it busy
  // (no second search in parallel), and a result landing after Lock belongs to an ended session.
  const [screening, setScreening] = useState(false)
  const [screenError, setScreenError] = useState('') // here too: a failure may land on another page
  const locks = useRef(0)

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

  const runScreen = useCallback(
    async (max: number, includeLarge: boolean) => {
      const session = locks.current
      setScreening(true)
      setScreenError('')
      try {
        const out = await api.screen(max, includeLarge)
        if (session === locks.current) setLastScreen(out)
      } catch (e) {
        if (session === locks.current) setScreenError((e as Error).message)
        onApiError(e)
      } finally {
        if (session === locks.current) setScreening(false)
      }
    },
    [onApiError],
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
    setScreenError('')
    locks.current += 1
    setScreening(false)
    refresh()
  }

  return (
    <>
      <Sidebar page={page} onLock={lock} />
      <main className="px-4 py-8 md:ml-60 md:px-10 md:py-10">
        <div className="max-w-[1200px]">
        {page === 'dashboard' && <Dashboard onApiError={onApiError} />}
        {page === 'portfolio' && <Portfolio />}
        {page === 'screener' && (
          <Screener result={lastScreen} busy={screening} error={screenError} onSearch={runScreen} />
        )}
        {page === 'analysis' && (
          // keyed on the route: a new '#analysis/A,B' refills the form instead of keeping the old one
          <Analysis key={arg} initialTickers={arg} run={lastRun} onRun={setLastRun} onApiError={onApiError} />
        )}
        {page === 'history' && <History ticker={arg} onApiError={onApiError} />}
        {page === 'watchlist' && <Watchlist onApiError={onApiError} />}
        {page === 'log' && <Log onApiError={onApiError} />}
        {page === 'settings' && <Settings onApiError={onApiError} />}
        </div>
      </main>
    </>
  )
}
