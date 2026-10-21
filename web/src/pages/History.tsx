import { type FormEvent, useCallback, useEffect, useState } from 'react'

import { api } from '../api'
import { Button, CriteriaTable, Field, inputClass, Message, PageHeader, Panel, StatusText, VerdictBadge } from '../components'
import { fmt } from '../format'
import type { HistoryEdit, HistoryRow, Status, Verdict } from '../types'

const VERDICTS: Verdict[] = ['BUY', 'BUY*', 'NO-BUY']
const NUMBER_FIELDS = ['price', 'entry', 'stop', 'target'] as const

/** '2026-10-20T15:04:00' -> '2026-10-20 15:04' */
const when = (iso: string) => iso.replace('T', ' ').slice(0, 16)

function byTicker(rows: HistoryRow[]): Map<string, HistoryRow[]> {
  const groups = new Map<string, HistoryRow[]>()
  for (const r of [...rows].sort((a, b) => a.analyzed_at.localeCompare(b.analyzed_at))) {
    groups.set(r.ticker, [...(groups.get(r.ticker) ?? []), r])
  }
  return groups // each ticker: oldest first
}

function TickerList({ rows }: { rows: HistoryRow[] }) {
  const tickers = [...byTicker(rows)].sort(([, a], [, b]) => b.at(-1)!.analyzed_at.localeCompare(a.at(-1)!.analyzed_at))
  return (
    <Panel title="Analyzed tickers" aside={`${rows.length} analyses`}>
      <div className="overflow-x-auto">
        <table className="w-full text-left text-sm">
          <thead className="text-muted">
            <tr className="border-b border-line">
              <th className="py-2 pr-4 font-normal">Ticker</th>
              <th className="py-2 pr-4 font-normal">Last verdict</th>
              <th className="py-2 pr-4 font-normal">Previous</th>
              <th className="py-2 pr-4 text-right font-normal">Analyses</th>
              <th className="py-2 font-normal">Last analysis</th>
            </tr>
          </thead>
          <tbody>
            {tickers.map(([ticker, list]) => {
              const last = list.at(-1)!
              const prev = list.at(-2)
              return (
                <tr key={ticker} className="border-b border-line/60 last:border-0 hover:bg-white/5">
                  <td className="py-3 pr-4">
                    <a href={`#history/${encodeURIComponent(ticker)}`} className="font-semibold text-teal-tint hover:underline">
                      {ticker}
                    </a>
                  </td>
                  <td className="py-3 pr-4"><VerdictBadge verdict={last.verdict} /></td>
                  <td className="py-3 pr-4">
                    {prev ? (
                      <span className="flex items-center gap-2">
                        <VerdictBadge verdict={prev.verdict} />
                        {prev.verdict !== last.verdict && <span className="text-sm font-semibold text-teal-tint">changed</span>}
                      </span>
                    ) : (
                      <span className="text-muted">first analysis</span>
                    )}
                  </td>
                  <td className="py-3 pr-4 text-right">{list.length}</td>
                  <td className="py-3 text-muted">{when(last.analyzed_at)}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </Panel>
  )
}

/** Verdict, criteria status and price changes since the previous analysis. */
function Changes({ cur, prev }: { cur: HistoryRow; prev: HistoryRow }) {
  const before = new Map(prev.criteria.map((c) => [c.name, c.status]))
  const flips = cur.criteria.filter((c) => before.has(c.name) && before.get(c.name) !== c.status)
  const items = [
    ...(cur.verdict !== prev.verdict
      ? [<span key="v" className="flex items-center gap-2">Verdict <VerdictBadge verdict={prev.verdict} /> → <VerdictBadge verdict={cur.verdict} /></span>]
      : []),
    ...flips.map((c) => (
      <span key={c.name}>
        {c.name} <StatusText status={before.get(c.name) as Status} /> → <StatusText status={c.status} />
      </span>
    )),
    ...(cur.price !== prev.price ? [<span key="p">Price {fmt(prev.price)} → {fmt(cur.price)}</span>] : []),
  ]
  return (
    <div className="ml-4 border-l-2 border-teal-tint/60 py-3 pl-4 text-sm">
      <p className="mb-1 text-muted">What changed since {when(prev.analyzed_at)}</p>
      {items.length ? (
        <div className="flex flex-wrap gap-x-6 gap-y-2">{items}</div>
      ) : (
        <p className="text-muted">Nothing: same verdict, criteria and price.</p>
      )}
    </div>
  )
}

function EditForm({ row, onSave, onCancel }: { row: HistoryRow; onSave: (c: HistoryEdit) => Promise<void>; onCancel: () => void }) {
  const text = (v: number | null) => (v === null ? '' : String(v))
  const [verdict, setVerdict] = useState<Verdict>(row.verdict)
  const [numbers, setNumbers] = useState(Object.fromEntries(NUMBER_FIELDS.map((k) => [k, text(row[k])])))
  const [shares, setShares] = useState(text(row.shares))
  const [note, setNote] = useState(row.note)
  const [error, setError] = useState('')

  async function submit(e: FormEvent) {
    e.preventDefault()
    setError('')
    const num = (v: string) => (v.trim() === '' ? null : Number(v))
    try {
      await onSave({
        verdict,
        ...Object.fromEntries(NUMBER_FIELDS.map((k) => [k, num(numbers[k])])),
        shares: num(shares),
        note,
      })
    } catch (err) {
      setError((err as Error).message)
    }
  }

  return (
    <form onSubmit={submit} className="mt-4 border-t border-line pt-4">
      <p className="mb-4 text-sm text-muted">
        Changing verdict, price or levels marks this analysis as edited. The note is yours and does not.
      </p>
      <div className="grid gap-4 sm:grid-cols-3 lg:grid-cols-6">
        <Field label="Verdict">
          <select className={inputClass} value={verdict} onChange={(e) => setVerdict(e.target.value as Verdict)}>
            {VERDICTS.map((v) => <option key={v}>{v}</option>)}
          </select>
        </Field>
        {NUMBER_FIELDS.map((k) => (
          <Field key={k} label={k[0].toUpperCase() + k.slice(1)}>
            <input className={inputClass} type="number" step="0.01" min="0" value={numbers[k]}
              onChange={(e) => setNumbers({ ...numbers, [k]: e.target.value })} />
          </Field>
        ))}
        <Field label="Shares">
          <input className={inputClass} type="number" step="1" min="0" value={shares} onChange={(e) => setShares(e.target.value)} />
        </Field>
      </div>
      <div className="mt-4">
        <Field label="Note">
          <textarea className={`${inputClass} h-20 py-2`} maxLength={1000} value={note} onChange={(e) => setNote(e.target.value)}
            placeholder="e.g. bought at 24.50" />
        </Field>
      </div>
      {error && <Message kind="error">{error}</Message>}
      <div className="mt-4 flex gap-2">
        <Button type="submit">Save</Button>
        <Button type="button" variant="quiet" onClick={onCancel}>Cancel</Button>
      </div>
    </form>
  )
}

function AnalysisCard({ row, onEdit, onDelete }: { row: HistoryRow; onEdit: (c: HistoryEdit) => Promise<void>; onDelete: () => void }) {
  const [open, setOpen] = useState(false)
  const [editing, setEditing] = useState(false)
  const levels: [string, string][] = [
    ['Price', fmt(row.price)],
    ['Entry', fmt(row.entry)],
    ['Stop', fmt(row.stop)],
    ['Target', fmt(row.target)],
    ['Shares', row.shares === null ? 'N/D' : String(row.shares)],
  ]
  return (
    <article className="rounded-md border border-line bg-panel p-6">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <h3 className="font-semibold">{when(row.analyzed_at)}</h3>
        <VerdictBadge verdict={row.verdict} />
        <span className="text-sm text-muted">Data as of {row.data_date ?? 'N/D'}</span>
        {row.edited_at && (
          <span className="rounded-sm border border-nd/60 px-2 py-0.5 text-xs font-semibold text-nd" title="Verdict, price or levels changed by hand">
            edited {when(row.edited_at)}
          </span>
        )}
        <div className="ml-auto flex gap-2">
          <Button variant="quiet" className="h-8 px-3 text-sm" onClick={() => setOpen(!open)} aria-expanded={open}>
            {open ? 'Hide criteria' : 'Criteria'}
          </Button>
          <Button variant="quiet" className="h-8 px-3 text-sm" onClick={() => setEditing(!editing)}>Edit</Button>
          <Button variant="quiet" className="h-8 px-3 text-sm hover:border-fail hover:text-fail" onClick={onDelete}>Delete</Button>
        </div>
      </div>
      <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-5">
        {levels.map(([label, value]) => (
          <div key={label}>
            <dt className="text-sm text-muted">{label}</dt>
            <dd className="mt-1 text-lg font-semibold">{value}</dd>
          </div>
        ))}
      </dl>
      {row.note && <p className="mt-4 rounded-sm bg-well px-4 py-2 text-sm whitespace-pre-wrap">{row.note}</p>}
      {open && (
        <div className="mt-6 flex flex-col gap-6">
          {row.reasons.length > 0 && (
            <div>
              <h4 className="mb-2 font-semibold text-muted">{row.verdict === 'BUY*' ? 'N/D allowed' : 'Why not BUY'}</h4>
              <ul className="list-disc space-y-1 pl-5 text-sm">
                {row.reasons.map((r) => <li key={r}>{r}</li>)}
              </ul>
            </div>
          )}
          <CriteriaTable title="Criteria at that date" items={row.criteria} />
        </div>
      )}
      {editing && (
        <EditForm row={row} onCancel={() => setEditing(false)}
          onSave={async (c) => { await onEdit(c); setEditing(false) }} />
      )}
    </article>
  )
}

export default function History({ ticker, onApiError }: { ticker: string; onApiError: (e: unknown) => void }) {
  const [rows, setRows] = useState<HistoryRow[] | null>(null)
  const [error, setError] = useState('')

  const load = useCallback(() => {
    api.history().then(setRows, (e: Error) => {
      setError(e.message)
      onApiError(e)
    })
  }, [onApiError])

  useEffect(load, [load])

  async function act(action: () => Promise<unknown>) {
    setError('')
    try {
      await action()
      load()
    } catch (err) {
      setError((err as Error).message)
      onApiError(err)
      throw err // the edit form shows it next to the fields
    }
  }

  const list = rows && ticker ? [...(byTicker(rows).get(ticker) ?? [])].reverse() : []

  return (
    <>
      <PageHeader title={ticker ? `History: ${ticker}` : 'History'} aside={ticker && <a href="#history" className="text-teal-tint hover:underline">← All tickers</a>}>
        {ticker
          ? 'Every saved analysis of this ticker, newest first, with what changed between one and the next.'
          : 'Every analysis is saved, from the web app and from the terminal. Pick a ticker to see how its verdict changed over time.'}
      </PageHeader>
      {error && <Message kind="error">{error}</Message>}
      {rows === null ? null : !ticker ? (
        rows.length ? (
          <TickerList rows={rows} />
        ) : (
          <Panel>
            <p className="text-muted">No analyses yet. Run one from <a href="#analysis" className="text-teal-tint hover:underline">Analysis</a> and it appears here.</p>
          </Panel>
        )
      ) : list.length === 0 ? (
        <Panel>
          <p className="text-muted">No saved analyses for {ticker}.</p>
        </Panel>
      ) : (
        <>
          <div className="mb-4 flex justify-end">
            <Button variant="quiet" className="hover:border-fail hover:text-fail"
              onClick={() => {
                if (window.confirm(`Delete all ${list.length} analyses of ${ticker}? This cannot be undone.`))
                  act(() => api.deleteTickerHistory(ticker)).catch(() => {})
              }}>
              Delete history
            </Button>
          </div>
          <div className="flex flex-col">
            {list.map((row, i) => (
              <div key={row.id}>
                <AnalysisCard row={row}
                  onEdit={(c) => act(() => api.editHistory(row.id, c))}
                  onDelete={() => {
                    if (window.confirm(`Delete the analysis of ${when(row.analyzed_at)}? This cannot be undone.`))
                      act(() => api.deleteHistory(row.id)).catch(() => {})
                  }} />
                {list[i + 1] && <Changes cur={row} prev={list[i + 1]} />}
              </div>
            ))}
          </div>
        </>
      )}
    </>
  )
}
