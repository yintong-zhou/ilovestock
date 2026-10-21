import { PageHeader, Panel, RuleLegend, RuleMatrix, VerdictBadge } from '../components'
import type { AnalyzeOut } from '../types'

export default function Dashboard({ run }: { run: AnalyzeOut | null }) {
  if (!run) {
    return (
      <>
        <PageHeader title="Dashboard">Statistics of the latest analysis in this session.</PageHeader>
        <Panel>
          <p>
            No analysis yet. Run one from{' '}
            <a className="font-semibold text-teal-tint underline underline-offset-4" href="#analysis">
              Analysis
            </a>{' '}
            and the statistics appear here.
          </p>
        </Panel>
      </>
    )
  }

  const results = run.results
  const count = (v: string) => results.filter((r) => r.verdict === v).length
  const errors = results.filter((r) => r.error).length
  // How often each criterion blocked a BUY: the method's bottlenecks in this list.
  const blocking = new Map<string, number>()
  for (const r of results) {
    if (r.verdict !== 'NO-BUY') continue // BUY* reasons are allowed N/D, not blockers
    for (const reason of r.reasons) {
      const name = reason.split(':')[0]
      blocking.set(name, (blocking.get(name) ?? 0) + 1)
    }
  }
  const ranked = [...blocking.entries()].sort((a, b) => b[1] - a[1])
  const stats: [string, number, string][] = [
    ['Tickers analyzed', results.length, 'text-text'],
    ['BUY', count('BUY'), 'text-pass'],
    ['BUY* (incomplete)', count('BUY*'), 'text-nd'],
    ['NO-BUY', count('NO-BUY'), 'text-text'],
    ['Data errors', errors, errors ? 'text-fail' : 'text-text'],
  ]

  return (
    <>
      <PageHeader title="Dashboard" aside={`Data as of ${run.data_date}`}>
        Statistics of the latest analysis in this session. They are not saved: a new analysis
        replaces them.
      </PageHeader>

      <dl className="mb-6 grid grid-cols-2 overflow-hidden rounded-md border border-line bg-panel lg:grid-cols-5">
        {stats.map(([label, value, color]) => (
          <div key={label} className="border-line p-6 not-last:border-r max-lg:even:border-r-0 max-lg:nth-[-n+4]:border-b">
            <dt className="text-sm text-muted">{label}</dt>
            <dd className={`mt-2 text-4xl font-semibold ${color}`}>{value}</dd>
          </div>
        ))}
      </dl>

      <div className="grid gap-6 lg:grid-cols-2">
        <Panel title="Criteria that blocked a BUY" aside={`out of ${results.length} tickers`}>
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
                    <div className="h-2 rounded-full bg-teal" style={{ width: `${(count / results.length) * 100}%` }} />
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Panel>

        <Panel title="Tickers" aside={<RuleLegend />}>
          <ul className="flex flex-col">
            {results.map((r) => (
              <li key={r.ticker} className="flex items-center gap-4 border-b border-line py-3 first:pt-0 last:border-0 last:pb-0">
                <span className="w-16 font-semibold">{r.ticker}</span>
                <span className="w-20">
                  <VerdictBadge verdict={r.verdict} />
                </span>
                {r.error ? (
                  <span className="text-sm text-fail">Data error</span>
                ) : (
                  <RuleMatrix
                    fundamental={[...r.fundamental, ...(r.earnings ? [r.earnings] : [])]}
                    technical={r.technical}
                  />
                )}
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      <p className="text-sm text-muted">{run.disclaimer}</p>
    </>
  )
}
