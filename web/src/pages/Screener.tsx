import { type FormEvent, useState } from 'react'

import { Button, Field, inputClass, JobProgress, Message, PageHeader, Panel } from '../components'
import { download, pct, points, rowClick } from '../format'
import type { ScreenHit, ScreenOut } from '../types'

const MAX_RESULTS = 50 // the list goes to Analysis, which takes at most 50 tickers

function rank(r: number | null, n: number) {
  return r === null ? 'N/D' : `#${r} of ${n}`
}

function Note({ hit, n }: { hit: ScreenHit; n: number }) {
  const q = hit.quality
  return (
    <div className="space-y-1 border-t border-line bg-canvas/40 px-6 py-4 text-sm text-muted">
      <p>
        ROIC {pct(q.roic_pct)} → {rank(hit.roic_rank, n)}
      </p>
      <p>
        Operating margin {pct(q.margin_year_ago_pct)} → {pct(q.margin_pct)} vs the same quarter last year (
        {points(q.margin_change_pt)}) → {rank(hit.margin_rank, n)}
      </p>
      <p>Score = average of the two ranks as percentiles, 0–100 (100 = best, 0 = worst of the {n})</p>
    </div>
  )
}

/** Same content as the terminal's watchlist file: one ticker per line. */
function downloadWatchlist(out: ScreenOut) {
  const header = `# ilovestock screen ${out.screened_on}: top ${out.hits.length} of ${out.passed} by quality score. ${out.disclaimer}`
  const text = [header, ...out.hits.map((h) => h.ticker)].join('\n') + '\n'
  download(new Blob([text], { type: 'text/plain' }), `screen-${out.screened_on}.txt`)
}

export default function Screener({
  result,
  busy,
  error,
  onSearch,
}: {
  result: ScreenOut | null
  busy: boolean // busy and error are owned by App: both survive leaving this page mid-search
  error: string
  onSearch: (max: number, includeLarge: boolean) => Promise<void>
}) {
  const [max, setMax] = useState(20)
  const [includeLarge, setIncludeLarge] = useState(false)
  const [open, setOpen] = useState<string | null>(null)
  const valid = Number.isInteger(max) && max >= 1 && max <= MAX_RESULTS

  async function submit(e: FormEvent) {
    e.preventDefault()
    setOpen(null)
    await onSearch(max, includeLarge)
  }

  function analyzeAll(out: ScreenOut) {
    window.location.hash = '#analysis/' + encodeURIComponent(out.hits.map((h) => h.ticker).join(','))
  }

  const cols = ['#', 'Ticker', 'Market cap', 'ROIC', 'Op. margin Δ (1y)', 'Quality score']
  return (
    <>
      <PageHeader title="Screener" aside={result && `Screened on ${result.screened_on}`}>
        Finds US-listed stocks that pass every fundamental rule, ranked by quality.
      </PageHeader>

      <Panel>
        <form onSubmit={submit} className="flex flex-col gap-6">
          <div className="flex flex-wrap items-end gap-4">
            <div className="w-40">
              <Field label="Max results" hint={`1 to ${MAX_RESULTS}`}>
                <input
                  type="number"
                  min={1}
                  max={MAX_RESULTS}
                  className={inputClass}
                  value={Number.isNaN(max) ? '' : max}
                  onChange={(e) => setMax(e.target.valueAsNumber)}
                />
              </Field>
            </div>
            <Button type="submit" className="mb-7" disabled={busy || !valid}>
              {busy ? 'Searching…' : 'Search'}
            </Button>
          </div>
          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" className="size-4 accent-teal" checked={includeLarge}
              onChange={(e) => setIncludeLarge(e.target.checked)} />
            Include large and giant caps: the Market cap rule is skipped, Analysis still fails them on it
          </label>
        </form>
        {busy && <Message kind="info">Checking each candidate takes a few seconds. The maximum number of candidates is in Settings.</Message>}
        <JobProgress job="screen" busy={busy} />
        {error && <Message kind="error">{error}</Message>}
      </Panel>

      {result && (
        <Panel
          title={`${result.passed} stocks pass every fundamental rule${result.include_large ? ' except Market cap' : ''} · showing the top ${result.hits.length} by quality score`}
          aside={`${result.candidates} candidates from Finviz`}
        >
          {result.hits.length === 0 ? (
            <Message kind="info">No stock passes every fundamental rule.</Message>
          ) : (
            <div className="-m-6 overflow-x-auto">
              <table className="w-full min-w-[640px] text-left">
                <thead className="text-sm text-muted">
                  <tr className="border-b border-line">
                    {cols.map((h, i) => (
                      <th key={h} className={`px-6 py-3 font-normal ${i >= 3 ? 'text-right' : ''}`}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                {result.hits.map((h, i) => {
                  const isOpen = open === h.ticker
                  return (
                    <tbody key={h.ticker} className="border-b border-line last:border-0">
                      <tr onClick={rowClick(() => setOpen(isOpen ? null : h.ticker))}
                        className={`cursor-pointer ${isOpen ? 'bg-well' : 'hover:bg-well/60'}`}>
                        <td className="px-6 py-3 text-muted">{i + 1}</td>
                        <td className="px-6 py-3">
                          <button
                            type="button"
                            className="flex items-center gap-2 font-semibold text-teal-tint hover:text-text"
                            onClick={() => setOpen(isOpen ? null : h.ticker)}
                            aria-expanded={isOpen}
                          >
                            <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden="true"
                              className={`transition-transform ${isOpen ? 'rotate-90' : ''}`}>
                              <path d="M4 2l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.5" />
                            </svg>
                            {h.ticker}
                          </button>
                        </td>
                        <td className="px-6 py-3">{h.market_cap ?? 'N/D'}</td>
                        <td className="px-6 py-3 text-right">{pct(h.quality.roic_pct)}</td>
                        <td className="px-6 py-3 text-right">{points(h.quality.margin_change_pt)}</td>
                        <td className="px-6 py-3 text-right font-semibold">{Math.round(h.score)}</td>
                      </tr>
                      {isOpen && (
                        <tr>
                          <td colSpan={cols.length} className="p-0">
                            <Note hit={h} n={result.passed} />
                          </td>
                        </tr>
                      )}
                    </tbody>
                  )
                })}
              </table>
            </div>
          )}
        </Panel>
      )}

      {/* outside the panel: the table's negative margin would slide under it */}
      {result && result.errors.length > 0 && (
        <div className="mb-6 -mt-4">
          <Message kind="info">
            Skipped for data errors: {result.errors.join(', ')}.{' '}
            <a href="#log" className="underline hover:text-text">Details in Log</a>
          </Message>
        </div>
      )}

      {result && result.hits.length > 0 && (
        <div className="mb-6 flex flex-wrap gap-3">
          <Button type="button" onClick={() => analyzeAll(result)}>
            Analyze these {result.hits.length}
          </Button>
          <Button type="button" variant="quiet" onClick={() => downloadWatchlist(result)}>
            Save as watchlist
          </Button>
        </div>
      )}

      {result && (
        <footer className="space-y-1 text-sm text-muted">
          <p>{result.disclaimer}</p>
          <p>{result.finviz_warning}</p>
          <p>Only stocks with complete Finviz data are searched.</p>
        </footer>
      )}
    </>
  )
}
