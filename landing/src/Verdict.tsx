import { motion, useReducedMotion } from 'motion/react'
import { useState } from 'react'

import { PLAN, SAMPLES, type Status } from './data'

const STEP = 0.26 // seconds between two criteria resolving
const TONE: Record<Status, string> = {
  PASS: 'bg-pass/15 text-pass',
  FAIL: 'bg-fail/15 text-fail',
  'N/D': 'bg-nd/15 text-nd',
}

export default function Verdict() {
  const [i, setI] = useState(0)
  const reduce = useReducedMotion()
  const s = SAMPLES[i]
  const t = (delay: number) => (reduce ? { duration: 0 } : { delay, duration: 0.3, ease: 'easeOut' as const })
  const end = s.rows.length * STEP + 0.25
  const reasons = s.rows.filter((r) => r.status !== 'PASS')

  return (
    <section aria-label="Example verdict" className="rounded-md border border-edge bg-ink text-mist">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-edge p-4">
        <div>
          <p className="font-heading text-lg font-bold">{s.ticker}</p>
          <p className="text-sm text-soft">Sample values, not a real quote</p>
        </div>
        <div role="group" aria-label="Choose a sample" className="flex rounded-md bg-well p-1">
          {SAMPLES.map((x, n) => (
            <button
              key={x.ticker}
              type="button"
              aria-pressed={n === i}
              onClick={() => setI(n)}
              className="relative cursor-pointer rounded-sm px-3 py-1 text-sm font-semibold text-mist transition-colors hover:text-white"
            >
              {n === i && (
                <motion.span
                  layoutId="sample-pill"
                  className="absolute inset-0 rounded-sm bg-teal"
                  transition={{ type: 'spring', bounce: 0.15, duration: 0.4 }}
                />
              )}
              <span className="relative">{x.label}</span>
            </button>
          ))}
        </div>
      </header>

      {/* key remounts the list, so the sequence plays again for each sample */}
      <ul key={s.ticker} className="divide-y divide-edge px-4">
        {s.rows.map((r, n) => (
          <motion.li
            key={r.name}
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            transition={t(n * STEP)}
            className="grid grid-cols-[1fr_auto_3.5rem] items-center gap-x-3 py-2 sm:grid-cols-[1fr_5rem_3.5rem] sm:gap-x-4"
          >
            <span>
              {r.name}
              <span className="block text-sm text-soft sm:ml-2 sm:inline">{r.rule}</span>
            </span>
            <span className="text-right sm:order-none">{r.value}</span>
            <span className="relative h-6">
              <motion.span
                aria-hidden
                initial={{ opacity: 1 }}
                animate={{ opacity: 0 }}
                transition={t(n * STEP + 0.15)}
                className="absolute inset-y-0 right-0 grid w-12 place-items-center"
              >
                <span className="size-1.5 rounded-full bg-soft" />
              </motion.span>
              <motion.span
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                transition={reduce ? { duration: 0 } : { delay: n * STEP + 0.18, type: 'spring', stiffness: 500, damping: 24 }}
                className={`absolute inset-y-0 right-0 grid place-items-center rounded-sm px-2 text-sm font-semibold ${TONE[r.status]}`}
              >
                {r.status}
              </motion.span>
            </span>
          </motion.li>
        ))}
      </ul>

      <motion.footer
        key={`${s.ticker}-verdict`}
        initial={{ opacity: 0, y: 8 }}
        animate={{ opacity: 1, y: 0 }}
        transition={t(end)}
        className="min-h-36 border-t border-edge bg-panel p-4"
      >
        <p className="flex items-baseline gap-3">
          <motion.span
            initial={{ scale: 0.8 }}
            animate={{ scale: 1 }}
            transition={reduce ? { duration: 0 } : { delay: end, type: 'spring', stiffness: 400, damping: 18 }}
            className={`font-heading text-3xl font-bold ${s.buy ? 'text-pass' : 'text-fail'}`}
          >
            {s.buy ? 'BUY' : 'NO-BUY'}
          </motion.span>
          <span className="text-soft">
            {s.buy ? 'Every criterion passed.' : `${reasons.length} criteria did not pass:`}
          </span>
        </p>
        {s.buy ? (
          <dl className="mt-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
            {[
              ['Entry', PLAN.entry.toFixed(2)],
              ['Stop', PLAN.stop.toFixed(2)],
              ['Target (3R)', PLAN.target.toFixed(2)],
              ['Shares', String(PLAN.shares)],
            ].map(([k, v]) => (
              <div key={k}>
                <dt className="text-sm text-soft">{k}</dt>
                <dd className="font-semibold">{v}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <ul className="mt-3 space-y-1 text-sm">
            {reasons.map((r) => (
              <li key={r.name}>
                {r.name}: <span className={r.status === 'FAIL' ? 'text-fail' : 'text-nd'}>{r.status}</span>
              </li>
            ))}
          </ul>
        )}
        {s.buy && (
          <p className="mt-4 text-sm text-soft">
            161 shares: capped at 10% of a $20,000 portfolio, below the 235 the 1% risk limit would allow.
          </p>
        )}
      </motion.footer>
    </section>
  )
}
