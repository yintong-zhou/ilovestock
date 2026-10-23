import { Fragment, useCallback, useEffect, useState } from 'react'

import { api } from '../api'
import { Button, Message, PageHeader, Panel, RuleGroup, VerdictBadge } from '../components'
import { fmt, groups, latestByTicker, when } from '../format'
import type { HistoryRow } from '../types'

const MAX = 50 // watchlist.MAX on the server

function Level({ value, color }: { value: number | null; color: string }) {
  return <td className={`py-3 pr-4 text-right ${value === null ? 'text-muted' : color}`}>{fmt(value)}</td>
}

export default function Watchlist({ onApiError }: { onApiError: (e: unknown) => void }) {
  const [tickers, setTickers] = useState<string[] | null>(null)
  const [latest, setLatest] = useState(new Map<string, HistoryRow>())
  const [busy, setBusy] = useState<string[]>([])
  const [failed, setFailed] = useState<Record<string, string>>({})
  const [error, setError] = useState('')

  const fail = useCallback(
    (e: unknown) => {
      setError((e as Error).message)
      onApiError(e)
    },
    [onApiError],
  )
  const loadHistory = useCallback(
    () => api.history().then((rows) => setLatest(new Map(latestByTicker(rows).map((r) => [r.ticker, r]))), fail),
    [fail],
  )

  useEffect(() => {
    api.watchlist().then(setTickers, fail)
    loadHistory()
  }, [fail, loadHistory])

  // Same rules and settings as the Analysis page; the new analysis lands in History like any other.
  async function refresh(ticker: string) {
    setBusy((b) => [...b, ticker])
    setFailed((f) => ({ ...f, [ticker]: '' }))
    try {
      const [r] = (await api.analyze([ticker], null, false)).results
      if (r.error) setFailed((f) => ({ ...f, [ticker]: r.error! }))
      await loadHistory()
    } catch (e) {
      setFailed((f) => ({ ...f, [ticker]: (e as Error).message }))
      onApiError(e)
    } finally {
      setBusy((b) => b.filter((t) => t !== ticker))
    }
  }

  async function remove(ticker: string) {
    setError('')
    try {
      setTickers(await api.unwatch(ticker))
    } catch (e) {
      fail(e)
    }
  }

  const link = 'text-teal-tint hover:underline'
  return (
    <>
      <PageHeader title="Watchlist" aside={tickers && `${tickers.length} of ${MAX}`}>
        Stocks you might buy. Refresh runs the analysis again on the latest close and saves it in History.
      </PageHeader>
      {error && <Message kind="error">{error}</Message>}
      {tickers === null ? null : tickers.length === 0 ? (
        <Panel>
          <p className="text-muted">
            Your watchlist is empty. Open a result in <a href="#analysis" className={link}>Analysis</a> or a ticker
            in <a href="#history" className={link}>History</a> and choose Add to watchlist.
          </p>
        </Panel>
      ) : (
        <Panel>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-sm">
              <thead className="text-muted">
                <tr className="border-b border-line">
                  <th className="py-2 pr-4 font-normal">Ticker</th>
                  <th className="py-2 pr-4 font-normal">Verdict</th>
                  <th className="py-2 pr-4 font-normal">Fundamental</th>
                  <th className="py-2 pr-4 font-normal">Technical</th>
                  <th className="py-2 pr-4 text-right font-normal">Price</th>
                  <th className="py-2 pr-4 text-right font-normal">Entry</th>
                  <th className="py-2 pr-4 text-right font-normal">Stop</th>
                  <th className="py-2 pr-4 text-right font-normal">Target</th>
                  <th className="py-2 pr-4 font-normal">Last analysis</th>
                  <th className="py-2 font-normal"><span className="sr-only">Actions</span></th>
                </tr>
              </thead>
              <tbody>
                {tickers.map((t) => {
                  const row = latest.get(t)
                  const working = busy.includes(t)
                  return (
                    <Fragment key={t}>
                      <tr className="border-b border-line/60">
                        <td className="py-3 pr-4">
                          <a href={`#history/${encodeURIComponent(t)}`} className={`font-semibold ${link}`}>{t}</a>
                        </td>
                        {row ? (
                          <>
                            <td className="py-3 pr-4"><VerdictBadge verdict={row.verdict} /></td>
                            <td className="py-3 pr-4"><RuleGroup title="Fundamental" items={groups(row.criteria).fundamental} /></td>
                            <td className="py-3 pr-4"><RuleGroup title="Technical" items={groups(row.criteria).technical} /></td>
                            <Level value={row.price} color="text-text" />
                            <Level value={row.entry} color="text-text" />
                            <Level value={row.stop} color="text-fail" />
                            <Level value={row.target} color="text-pass" />
                            <td className="py-3 pr-4 whitespace-nowrap text-muted">{when(row.analyzed_at)}</td>
                          </>
                        ) : (
                          <td colSpan={8} className="py-3 pr-4 text-muted">No saved analysis: Refresh runs one.</td>
                        )}
                        <td className="py-3 whitespace-nowrap">
                          <span className="flex justify-end gap-2">
                            <Button variant="quiet" className="h-8 px-3 text-sm" disabled={working} onClick={() => refresh(t)}>
                              {working ? 'Refreshing…' : 'Refresh'}
                            </Button>
                            <Button variant="quiet" className="h-8 px-3 text-sm hover:border-fail hover:text-fail" disabled={working}
                              onClick={() => remove(t)}>
                              Remove
                            </Button>
                          </span>
                        </td>
                      </tr>
                      {failed[t] && (
                        <tr className="border-b border-line/60">
                          <td colSpan={10} role="alert" className="pb-3 text-fail">
                            {row ? 'Refresh failed, the last saved analysis is still shown' : 'Refresh failed'}: {failed[t]}
                          </td>
                        </tr>
                      )}
                    </Fragment>
                  )
                })}
              </tbody>
            </table>
          </div>
        </Panel>
      )}
    </>
  )
}
