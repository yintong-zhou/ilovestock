import { useCallback, useEffect, useState } from 'react'

import { api, ApiError } from './api'
import { Message } from './components'
import Analysis from './pages/Analysis'
import Dashboard from './pages/Dashboard'
import Portfolio from './pages/Portfolio'
import Settings from './pages/Settings'
import PinScreen from './PinScreen'
import Sidebar, { type Page } from './Sidebar'
import type { AnalyzeOut, PinStatus } from './types'

const PAGES: Page[] = ['dashboard', 'portfolio', 'analysis', 'settings']

function pageFromHash(): Page {
  const p = window.location.hash.slice(1) as Page
  return PAGES.includes(p) ? p : 'dashboard'
}

export default function App() {
  const [status, setStatus] = useState<PinStatus | null>(null)
  const [error, setError] = useState('')
  const [page, setPage] = useState<Page>(pageFromHash)
  // Latest analysis of this session, shared by Analysis and Dashboard (not stored on disk).
  const [lastRun, setLastRun] = useState<AnalyzeOut | null>(null)

  const refresh = useCallback(() => {
    api.pinStatus().then(setStatus, (e: Error) => setError(e.message))
  }, [])

  useEffect(refresh, [refresh])

  useEffect(() => {
    const onHash = () => {
      setPage(pageFromHash())
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
    refresh()
  }

  return (
    <>
      <Sidebar page={page} onLock={lock} />
      <main className="px-4 py-8 md:ml-60 md:px-10 md:py-10">
        <div className="max-w-[1200px]">
        {page === 'dashboard' && <Dashboard run={lastRun} />}
        {page === 'portfolio' && <Portfolio />}
        {page === 'analysis' && <Analysis run={lastRun} onRun={setLastRun} onApiError={onApiError} />}
        {page === 'settings' && <Settings onApiError={onApiError} />}
        </div>
      </main>
    </>
  )
}
