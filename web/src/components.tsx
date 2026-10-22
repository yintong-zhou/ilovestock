import type { ButtonHTMLAttributes, ReactNode } from 'react'

import { fmt, qualityText } from './format'
import type { CriterionResult, Quality, Status, TradePlan, Verdict } from './types'

export function PageHeader({ title, aside, children }: { title: string; aside?: ReactNode; children?: ReactNode }) {
  return (
    <header className="mb-8 flex flex-wrap items-end justify-between gap-4 border-b border-line pb-6">
      <div>
        <h1 className="font-heading text-3xl leading-tight font-bold">{title}</h1>
        {children && <p className="mt-2 max-w-[65ch] text-muted">{children}</p>}
      </div>
      {aside && <div className="text-sm text-muted">{aside}</div>}
    </header>
  )
}

export function Panel({ title, aside, children }: { title?: string; aside?: ReactNode; children: ReactNode }) {
  return (
    <section className="mb-6 rounded-md border border-line bg-panel">
      {title && (
        <div className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line px-6 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          {aside && <div className="text-sm text-muted">{aside}</div>}
        </div>
      )}
      <div className="p-6">{children}</div>
    </section>
  )
}

export function Button({
  children,
  variant = 'primary',
  className = '',
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'quiet' }) {
  const style =
    variant === 'primary'
      ? 'bg-teal text-white hover:bg-[#25809f]'
      : 'border border-line text-text hover:border-muted'
  return (
    <button
      className={`h-10 rounded-sm px-4 font-semibold whitespace-nowrap transition-colors disabled:cursor-not-allowed disabled:opacity-40 ${style} ${className}`}
      {...props}
    >
      {children}
    </button>
  )
}

export function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="flex flex-col gap-2">
      <span className="text-sm font-semibold">{label}</span>
      {children}
      {hint && <span className="text-sm text-muted">{hint}</span>}
    </label>
  )
}

export const inputClass =
  'h-10 w-full rounded-sm border border-line bg-well px-3 text-text placeholder:text-muted/60 focus:border-teal-tint focus:outline-none'

export function Message({ kind, children }: { kind: 'error' | 'info'; children: ReactNode }) {
  const style = kind === 'error' ? 'border-fail/50 text-fail' : 'border-teal-tint/50 text-teal-tint'
  return (
    <p role={kind === 'error' ? 'alert' : 'status'} className={`mt-4 rounded-sm border-l-2 bg-well px-4 py-2 ${style}`}>
      {children}
    </p>
  )
}

const STATUS_TEXT: Record<Status, string> = { PASS: 'text-pass', FAIL: 'text-fail', 'N/D': 'text-nd' }
const STATUS_FILL: Record<Status, string> = { PASS: 'bg-pass', FAIL: 'bg-fail', 'N/D': 'bg-nd' }

export function StatusText({ status }: { status: Status }) {
  return <span className={`font-semibold ${STATUS_TEXT[status]}`}>{status}</span>
}

export function VerdictBadge({ verdict }: { verdict: Verdict }) {
  const style = { BUY: 'bg-green text-canvas', 'BUY*': 'bg-nd text-canvas', 'NO-BUY': 'bg-line text-muted' }[verdict]
  return (
    <span className={`inline-block rounded-sm px-2 py-0.5 text-sm font-semibold whitespace-nowrap ${style}`}>
      {verdict}
    </span>
  )
}

/** One cell per rule, fundamental then technical: the method at a glance. */
export function RuleMatrix({ fundamental, technical }: { fundamental: CriterionResult[]; technical: CriterionResult[] }) {
  const passed = (items: CriterionResult[]) => items.filter((c) => c.status === 'PASS').length
  const label = `Fundamental ${passed(fundamental)} of ${fundamental.length} pass, technical ${passed(technical)} of ${technical.length} pass`
  const cells = (items: CriterionResult[]) =>
    items.map((c) => (
      <span
        key={c.name}
        title={`${c.name}: ${c.status}${c.value === null ? '' : ` (${c.value})`}`}
        className={`size-3 rounded-[2px] ${STATUS_FILL[c.status]}`}
      />
    ))
  return (
    <span role="img" aria-label={label} className="inline-flex items-center gap-2">
      <span className="flex gap-1">{cells(fundamental)}</span>
      <span className="flex gap-1">{cells(technical)}</span>
    </span>
  )
}

export function RuleLegend() {
  return (
    <span className="inline-flex flex-wrap items-center gap-4">
      {(['PASS', 'FAIL', 'N/D'] as Status[]).map((s) => (
        <span key={s} className="inline-flex items-center gap-2">
          <span className={`size-3 rounded-[2px] ${STATUS_FILL[s]}`} />
          {s}
        </span>
      ))}
    </span>
  )
}

export function CriteriaTable({
  title,
  items,
  quality,
}: {
  title: string
  items: CriterionResult[]
  quality?: Quality | null // shown last, outside the criteria: never part of the verdict
}) {
  return (
    <div>
      <h3 className="mb-2 font-semibold text-muted">{title}</h3>
      {/* fixed layout + shared column widths: the two criteria tables line up */}
      <table className="w-full table-fixed text-left text-sm">
        <colgroup>
          <col className="w-[26%]" />
          <col className="w-[22%]" />
          <col className="w-[18%]" />
          <col className="w-[10%]" />
          <col />
        </colgroup>
        <thead className="text-muted">
          <tr className="border-b border-line">
            <th className="py-2 pr-4 font-normal">Criterion</th>
            <th className="py-2 pr-4 text-right font-normal">Value</th>
            <th className="py-2 pr-4 font-normal">Threshold</th>
            <th className="py-2 pr-4 font-normal">Status</th>
            <th className="py-2 font-normal">Note</th>
          </tr>
        </thead>
        <tbody>
          {items.map((c) => (
            <tr key={c.name} className="border-b border-line/60 align-top last:border-0">
              <td className="py-2 pr-4">{c.name}</td>
              <td className="py-2 pr-4 text-right break-words">{c.value ?? 'N/D'}</td>
              <td className="py-2 pr-4 text-muted">{c.threshold}</td>
              <td className="py-2 pr-4">
                <StatusText status={c.status} />
              </td>
              <td className="py-2 text-muted">{c.note}</td>
            </tr>
          ))}
          {quality && (
            <tr className="align-top">
              <td className="py-2 pr-4">Quality</td>
              <td className="py-2 pr-4 text-right break-words">{qualityText(quality)}</td>
              <td className="py-2 pr-4 text-muted">—</td>
              <td className="py-2 pr-4 font-semibold text-teal-tint">INFO</td>
              <td className="py-2 text-muted">Informative, does not change the verdict</td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  )
}

export function PlanDetails({ plan }: { plan: TradePlan }) {
  const rows: [string, string][] = [
    ['Shares', `${plan.shares}, limited by ${plan.binding || 'N/D'}`],
    ['Position value', fmt(plan.position_value)],
    ['Max loss', fmt(plan.max_loss)],
    ['Effective risk', `${fmt(plan.effective_risk)} (${plan.risk_band})`],
    ['Trailing stop 10w', fmt(plan.trailing_stop_10w)],
    ['Trailing stop 8w', fmt(plan.trailing_stop_8w)],
  ]
  return (
    <div className="rounded-md border border-line bg-well p-6">
      <h3 className="mb-4 font-semibold text-muted">Trade plan</h3>
      <div className="mb-6 grid grid-cols-3 gap-4">
        {(
          [
            ['Entry', plan.entry, 'text-text'],
            ['Stop', plan.stop, 'text-fail'],
            ['Target', plan.target, 'text-pass'],
          ] as const
        ).map(([k, v, color]) => (
          <div key={k}>
            <p className="text-sm text-muted">{k}</p>
            <p className={`text-2xl font-semibold ${color}`}>{fmt(v)}</p>
          </div>
        ))}
      </div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
        {rows.map(([k, v]) => (
          <div key={k} className="contents">
            <dt className="text-muted">{k}</dt>
            <dd className="text-right">{v}</dd>
          </div>
        ))}
      </dl>
      <ul className="mt-6 space-y-1 border-t border-line pt-4 text-sm text-muted">
        {plan.info.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
      {plan.discarded && <Message kind="error">Trade discarded: {plan.discarded}</Message>}
    </div>
  )
}
