import { useEffect, useState } from 'react'

import { api } from '../api'
import { Message, PageHeader, Panel, RuleLegend, RuleMatrix, VerdictBadge } from '../components'
import { groups, latestByTicker, when } from '../format'
import type { HistoryRow } from '../types'

const RECENT = 10
const INTRO = 'The latest analysis of every ticker you analyzed, from the web app and from the terminal.'

export default function Dashboard({ onApiError }: { onApiError: (e: unknown) => void }) {
  const [rows, setRows] = useState<HistoryRow[] | null>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api.history().then(
      (all) => setRows(latestByTicker(all)),
      (e: Error) => {
        setError(e.message)
        onApiError(e)
      },
    )
  }, [onApiError])

  if (!rows?.length) {
    return (
      <>
        <PageHeader title="Dashboard">{INTRO}</PageHeader>
        {error && <Message kind="error">{error}</Message>}
        {rows && (
          <Panel>
            <p>
              No analysis yet. Run one from{' '}
              <a className="font-semibold text-teal-tint underline underline-offset-4" href="#analysis">
                Analysis
              </a>{' '}
              and the statistics appear here.
            </p>
          </Panel>
        )}
      </>
    )
  }

  const count = (v: string) => rows.filter((r) => r.verdict === v).length
  // How often each criterion blocked a BUY: the method's bottlenecks across your tickers.
  const blocking = new Map<string, number>()
  for (const r of rows) {
    if (r.verdict !== 'NO-BUY') continue // BUY* reasons are allowed N/D, not blockers
    for (const reason of r.reasons) {
      const name = reason.split(':')[0]
      blocking.set(name, (blocking.get(name) ?? 0) + 1)
    }
  }
  const ranked = [...blocking.entries()].sort((a, b) => b[1] - a[1])
  const stats: [string, number, string][] = [
    ['Tickers', rows.length, 'text-text'],
    ['BUY', count('BUY'), 'text-pass'],
    ['BUY* (incomplete)', count('BUY*'), 'text-nd'],
    ['NO-BUY', count('NO-BUY'), 'text-text'],
  ]

  return (
    <>
      <PageHeader title="Dashboard" aside={`Last analysis ${when(rows[0].analyzed_at)}`}>
        {INTRO}
      </PageHeader>

      <dl className="mb-6 grid grid-cols-2 overflow-hidden rounded-md border border-line bg-panel lg:grid-cols-4">
        {stats.map(([label, value, color]) => (
          <div key={label} className="border-line p-6 not-last:border-r max-lg:even:border-r-0 max-lg:nth-[-n+2]:border-b">
            <dt className="text-sm text-muted">{label}</dt>
            <dd className={`mt-2 text-4xl font-semibold ${color}`}>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Criteria that blocked a BUY" aside={`out of ${rows.length} tickers`}>
          {ranked.length === 0 ? (
            <p className="text-muted">No criterion blocked a BUY.</p>
          ) : (
            <ul className="flex flex-col gap-4">
              {ranked.map(([name, count]) => (
                <li key={name}>
                  <div className="mb-1 flex justify-between gap-4 text-sm">
                    <span>{name}</span>
                    <span className="text-muted">{count}</span>
                  </div>
                  <div className="h-2 rounded-full bg-well">
                    <div className="h-2 rounded-full bg-teal" style={{ width: `${(count / rows.length) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Latest tickers" aside={<RuleLegend />}>
          <ul className="flex flex-col">
            {rows.slice(0, RECENT).map((r) => {
              const { fundamental, technical } = groups(r.criteria)
              return (
                <li key={r.ticker} className="flex items-center gap-4 border-b border-line py-3 first:pt-0 last:border-0 last:pb-0">
                  <a href={`#history/${encodeURIComponent(r.ticker)}`} className="w-16 font-semibold text-teal-tint hover:underline">
                    {r.ticker}
                  </a>
                  <span className="w-20">
                    <VerdictBadge verdict={r.verdict} />
                  </span>
                  <RuleMatrix fundamental={fundamental} technical={technical} />
                </li>
              )
            })}
          </ul>
          <p className="mt-6 text-sm">
            <a href="#history" className="text-teal-tint hover:underline">See all in History</a>
          </p>
        </Panel>
      </div>
    </>
  )
}
