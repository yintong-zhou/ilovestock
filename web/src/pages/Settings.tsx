import { type FormEvent, useEffect, useState } from 'react'

import { api } from '../api'
import { Button, Field, inputClass, Message, PageHeader, Panel } from '../components'
import type { AppConfig } from '../types'

type NumKey = { [K in keyof AppConfig]: AppConfig[K] extends number ? K : never }[keyof AppConfig]

const GROUPS: { title: string; fields: [NumKey, string, string?][] }[] = [
  {
    title: 'Portfolio and risk',
    fields: [
      ['capital', 'Capital'],
      ['risk_pct', 'Max loss per trade (%)', 'Below 0.5 very conservative, 0.5–1 moderate, 1–2 aggressive. Above 2 is rejected.'],
      ['max_position_pct', 'Max weight per stock (%)', 'Course limit: above 10 is rejected.'],
      ['r_multiple', 'Take profit (multiple of R)', 'Below 2 every trade is discarded.'],
    ],
  },
  {
    title: 'Fundamental thresholds',
    fields: [
      ['sales_growth_min', 'Min sales growth (%)'],
      ['eps_growth_min', 'Min EPS growth (%)'],
      ['roe_min', 'Min ROE (%)'],
      ['institutional_own_max', 'Max institutional ownership (%)'],
    ],
  },
  {
    title: 'Market cap bands (upper bound, millions USD)',
    fields: [
      ['nano_max', 'Nano'],
      ['micro_max', 'Micro'],
      ['small_max', 'Small'],
      ['mid_max', 'Mid'],
      ['large_max', 'Large'],
    ],
  },
]

// One grid for every settings panel, so fields line up from panel to panel.
const GRID = 'grid gap-6 sm:grid-cols-2 sm:items-start lg:grid-cols-3'

function PinForm({ onApiError }: { onApiError: (e: unknown) => void }) {
  const [current, setCurrent] = useState('')
  const [next, setNext] = useState('')
  const [msg, setMsg] = useState<{ kind: 'error' | 'info'; text: string } | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    try {
      await api.changePin(current, next)
      setMsg({ kind: 'info', text: 'PIN changed. Other open tabs need the new PIN.' })
      setCurrent('')
      setNext('')
    } catch (err) {
      setMsg({ kind: 'error', text: (err as Error).message })
      onApiError(err)
    }
  }

  const pinInput = (value: string, set: (v: string) => void) => (
    <input className={inputClass} type="password" inputMode="numeric" autoComplete="off" maxLength={8}
      value={value} onChange={(e) => set(e.target.value.replace(/\D/g, ''))} />
  )
  return (
    <Panel title="PIN">
      <form onSubmit={submit} className={GRID}>
        <Field label="Current PIN">{pinInput(current, setCurrent)}</Field>
        <Field label="New PIN" hint="4 to 8 digits">{pinInput(next, setNext)}</Field>
        <div className="sm:pt-7">
          <Button type="submit" disabled={!current || !next}>
            Change PIN
          </Button>
        </div>
      </form>
      {msg && <Message kind={msg.kind}>{msg.text}</Message>}
    </Panel>
  )
}

export default function Settings({ onApiError }: { onApiError: (e: unknown) => void }) {
  const [cfg, setCfg] = useState<AppConfig | null>(null)
  const [msg, setMsg] = useState<{ kind: 'error' | 'info'; text: string } | null>(null)

  useEffect(() => {
    api.getConfig().then(setCfg, (err) => {
      setMsg({ kind: 'error', text: err.message })
      onApiError(err)
    })
  }, [onApiError])

  async function save(e: FormEvent) {
    e.preventDefault()
    if (!cfg) return
    try {
      setCfg(await api.putConfig(cfg))
      setMsg({ kind: 'info', text: 'Settings saved. The next analysis uses them, in the web app and in the CLI.' })
    } catch (err) {
      setMsg({ kind: 'error', text: (err as Error).message })
      onApiError(err)
    }
  }

  return (
    <>
      <PageHeader title="Settings">
        The same config file as the CLI. Technical indicator parameters are fixed by the method and
        cannot be changed.
      </PageHeader>
      <PinForm onApiError={onApiError} />
      {cfg && (
        <form onSubmit={save}>
          <Panel title="Method">
            <div className={GRID}>
              <Field label="Entry point">
                <select className={inputClass} value={cfg.entry_mode}
                  onChange={(e) => setCfg({ ...cfg, entry_mode: e.target.value as AppConfig['entry_mode'] })}>
                  <option value="breakout">Breakout (last close)</option>
                  <option value="pullback">Pullback (upper Donchian band)</option>
                  <option value="restart">Restart (previous week high)</option>
                </select>
              </Field>
              <Field label="Growth basis">
                <select className={inputClass} value={cfg.growth_basis}
                  onChange={(e) => setCfg({ ...cfg, growth_basis: e.target.value as AppConfig['growth_basis'] })}>
                  <option value="yoy">Year over year (Finviz)</option>
                  <option value="qoq">Quarter over quarter (Yahoo)</option>
                </select>
              </Field>
            </div>
          </Panel>
          {GROUPS.map((g) => (
            <Panel key={g.title} title={g.title}>
              <div className={GRID}>
                {g.fields.map(([key, label, hint]) => (
                  <Field key={key} label={label} hint={hint}>
                    <input className={inputClass} type="number" step="any" required value={cfg[key]}
                      onChange={(e) => setCfg({ ...cfg, [key]: e.target.valueAsNumber })} />
                  </Field>
                ))}
              </div>
            </Panel>
          ))}
          <div className="flex flex-wrap items-center gap-4">
            <Button type="submit">Save settings</Button>
          </div>
          {msg && <Message kind={msg.kind}>{msg.text}</Message>}
        </form>
      )}
      {!cfg && msg && <Message kind={msg.kind}>{msg.text}</Message>}
    </>
  )
}
