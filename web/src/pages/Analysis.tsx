import { type FormEvent, useState } from 'react'

import { api } from '../api'
import {
  Button,
  CriteriaTable,
  Field,
  inputClass,
  Message,
  PageHeader,
  Panel,
  PlanDetails,
  RuleLegend,
  RuleMatrix,
  VerdictBadge,
} from '../components'
import { fmt } from '../format'
import type { AnalyzeOut, TickerAnalysis } from '../types'

function fundamentalRules(r: TickerAnalysis) {
  return [...r.fundamental, ...(r.earnings ? [r.earnings] : [])]
}

function Detail({ r }: { r: TickerAnalysis }) {
  return (
    <div className="border-t border-line bg-canvas/40 px-6 py-6">
      <div className="mb-6 flex flex-wrap items-baseline gap-4">
        <h3 className="font-heading text-xl font-bold">{r.ticker}</h3>
        <VerdictBadge verdict={r.verdict} />
        <span className="text-sm text-muted">Data as of {r.data_date ?? 'N/D'}</span>
      </div>
      {r.error ? (
        <Message kind="error">Data error: {r.error}</Message>
      ) : (
        <div className="grid gap-8 xl:grid-cols-[1fr_360px]">
          <div className="flex min-w-0 flex-col gap-8">
            {r.reasons.length > 0 && (
              <div>
                <h3 className="mb-2 font-semibold text-muted">Why not BUY</h3>
                <ul className="list-disc space-y-1 pl-5">
                  {r.reasons.map((reason) => (
                    <li key={reason}>{reason}</li>
                  ))}
                </ul>
              </div>
            )}
            <CriteriaTable title="Fundamental" items={fundamentalRules(r)} />
            <CriteriaTable title="Technical" items={r.technical} />
          </div>
          {r.plan && <PlanDetails plan={r.plan} />}
        </div>
      )}
    </div>
  )
}

export default function Analysis({
  run,
  onRun,
  onApiError,
}: {
  run: AnalyzeOut | null
  onRun: (run: AnalyzeOut) => void
  onApiError: (e: unknown) => void
}) {
  const [tickers, setTickers] = useState('')
  const [finvizUrl, setFinvizUrl] = useState('')
  const [allowMissing, setAllowMissing] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [open, setOpen] = useState<string | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const list = tickers.split(/[\s,;]+/).filter(Boolean)
      onRun(await api.analyze(list, finvizUrl.trim() || null, allowMissing))
      setOpen(null)
    } catch (err) {
      setError((err as Error).message)
      onApiError(err)
    } finally {
      setBusy(false)
    }
  }

  const cols = ['Ticker', 'Verdict', 'Rules', 'Entry', 'Stop', 'Target', 'Shares']
  return (
    <>
      <PageHeader title="Analysis" aside={run && `Data as of ${run.data_date}`}>
        Checks each US ticker against the method&apos;s fundamental and technical rules and builds
        a trade plan.
      </PageHeader>

      <Panel>
        <form onSubmit={submit} className="flex flex-col gap-6">
          <div className="grid gap-4 lg:grid-cols-[1fr_1fr_auto] lg:items-start">
            <Field label="Tickers" hint="Separate with spaces or commas">
              <input className={inputClass} placeholder="HZO NIO" value={tickers}
                onChange={(e) => setTickers(e.target.value)} />
            </Field>
            <Field label="Finviz screener URL" hint="Optional: copy it from Finviz after setting the filters">
              <input className={inputClass} placeholder="https://finviz.com/screener.ashx?..." value={finvizUrl}
                onChange={(e) => setFinvizUrl(e.target.value)} />
            </Field>
            <Button type="submit" className="lg:mt-7" disabled={busy || (!tickers.trim() && !finvizUrl.trim())}>
              {busy ? 'Analyzing…' : 'Analyze'}
            </Button>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-teal" checked={allowMissing}
              onChange={(e) => setAllowMissing(e.target.checked)} />
            Missing fundamental data (N/D) does not block a BUY
          </label>
        </form>
        {busy && <Message kind="info">Downloading data takes a few seconds per ticker.</Message>}
        {error && <Message kind="error">{error}</Message>}
      </Panel>

      {run && (
        <Panel title={`${run.results.length} tickers analyzed`} aside={<RuleLegend />}>
          <div className="-m-6 overflow-x-auto">
            <table className="w-full min-w-[720px] text-left">
              <thead className="text-sm text-muted">
                <tr className="border-b border-line">
                  {cols.map((h, i) => (
                    <th key={h} className={`px-6 py-3 font-normal ${i >= 3 ? 'text-right' : ''}`}>
                      {h === 'Rules' ? (
                        <span title="8 fundamental rules, then 4 technical rules">Rules</span>
                      ) : (
                        h
                      )}
                    </th>
                  ))}
                </tr>
              </thead>
              {run.results.map((r) => {
                const isOpen = open === r.ticker
                return (
                  <tbody key={r.ticker} className="border-b border-line last:border-0">
                    <tr className={isOpen ? 'bg-well' : 'hover:bg-well/60'}>
                      <td className="px-6 py-3">
                        <button
                          type="button"
                          className="flex items-center gap-2 font-semibold text-teal-tint hover:text-text"
                          onClick={() => setOpen(isOpen ? null : r.ticker)}
                          aria-expanded={isOpen}
                        >
                          <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"
                            className={`transition-transform ${isOpen ? 'rotate-90' : ''}`}>
                            <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" />
                          </svg>
                          {r.ticker}
                        </button>
                      </td>
                      <td className="px-6 py-3">
                        <VerdictBadge verdict={r.verdict} />
                      </td>
                      <td className="px-6 py-3">
                        {r.error ? (
                          <span className="text-sm text-fail">Data error</span>
                        ) : (
                          <RuleMatrix fundamental={fundamentalRules(r)} technical={r.technical} />
                        )}
                      </td>
                      <td className="px-6 py-3 text-right">{fmt(r.plan?.entry)}</td>
                      <td className="px-6 py-3 text-right">{fmt(r.plan?.stop)}</td>
                      <td className="px-6 py-3 text-right">{fmt(r.plan?.target)}</td>
                      <td className="px-6 py-3 text-right">{r.plan?.shares ?? 'N/D'}</td>
                    </tr>
                    {isOpen && (
                      <tr>
                        <td colSpan={cols.length} className="p-0">
                          <Detail r={r} />
                        </td>
                      </tr>
                    )}
                  </tbody>
                )
              })}
            </table>
          </div>
        </Panel>
      )}

      {run && (
        <footer className="space-y-1 text-sm text-muted">
          <p>{run.disclaimer} Recheck entry and stop on the live price before trading.</p>
          {run.sources.map((s) => (
            <p key={s}>Source: {s}</p>
          ))}
          <p>{run.finviz_warning}</p>
        </footer>
      )}
    </>
  )
}
