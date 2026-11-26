import { MotionConfig, motion, useReducedMotion } from 'motion/react'
import { useState, type ReactNode } from 'react'

import { RANKING, REPO } from './data'
import TradePlan from './TradePlan'
import Verdict from './Verdict'

const wrap = 'mx-auto w-full max-w-6xl px-4 sm:px-6'
const h2 = 'text-2xl leading-snug sm:text-3xl'
const btn = 'inline-flex cursor-pointer items-center justify-center rounded-md px-6 py-2 font-semibold transition-colors'

function Header() {
  return (
    <header className={`${wrap} flex items-center justify-between gap-4 py-4`}>
      <a href="#top" className="flex items-center gap-2 font-heading text-lg font-bold text-navy">
        <img src="/logo.png" alt="" width={40} height={40} />
        iLoveStock
      </a>
      <nav aria-label="Sections" className="hidden gap-6 text-sm font-semibold text-muted md:flex">
        {[
          ['#method', 'How it decides'],
          ['#plan', 'Trade plan'],
          ['#screener', 'Screener'],
          ['#limits', 'Limits'],
        ].map(([href, label]) => (
          <a key={href} href={href} className="transition-colors hover:text-navy">
            {label}
          </a>
        ))}
      </nav>
      <a href={REPO} className={`${btn} bg-navy text-mist hover:bg-teal`}>
        View on GitHub
      </a>
    </header>
  )
}

function Hero() {
  const reduce = useReducedMotion()
  return (
    <section id="top" className={`${wrap} grid items-center gap-10 pt-10 pb-16 lg:grid-cols-[1fr_1.1fr]`}>
      <motion.div
        initial={reduce ? false : { opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.5, ease: 'easeOut' }}
      >
        <h1 className="text-3xl leading-tight text-navy sm:text-4xl lg:text-[2.75rem]">
          Every rule passes, or it is a NO-BUY.
        </h1>
        <p className="mt-6 max-w-[62ch] text-lg">
          iLoveStock checks a US stock against fixed fundamental and technical rules, then returns a BUY or NO-BUY
          verdict with a trade plan. It lists every criterion that failed and every one it had no data for.
        </p>
        <p className="mt-4 max-w-[62ch] text-muted">
          An educational screening tool, not financial advice. A BUY means the rules passed on the data available, not
          that you should buy.
        </p>
        <div className="mt-10 flex flex-wrap gap-4">
          <a href="#install" className={`${btn} bg-navy text-mist hover:bg-teal`}>
            Install it
          </a>
          <a href="#method" className={`${btn} border border-navy text-navy hover:bg-navy hover:text-mist`}>
            See how the verdict works
          </a>
        </div>
      </motion.div>
      <Verdict />
    </section>
  )
}

const FUNDAMENTALS = [
  ['Sales and earnings growth', 'is the business growing'],
  ['Return on equity', 'how well it turns capital into profit'],
  ['Institutional ownership', 'who holds it, and whether they are buying'],
  ['Dividend', 'whether profit is paid out or reinvested'],
  ['Market capitalization', 'the size of the company'],
  ['Earnings calendar', 'how close the next report is, and how the market took the last one'],
]
const TECHNICALS = [
  ['Relative strength', 'how the stock moves against the S&P 500'],
  ['Breakout', 'price leaving a period of consolidation'],
  ['Consolidation', 'how orderly the pause before the move was'],
  ['Volume', 'whether trading confirms the move'],
  ['Directional movement', 'the strength and direction of the trend'],
  ['Long-term trend', 'where the price sits against its long moving average'],
]

function Column({ title, question, rows }: { title: string; question: string; rows: string[][] }) {
  return (
    <div>
      <h3 className="text-xl text-navy">{title}</h3>
      <p className="mt-1 text-muted">{question}</p>
      <dl className="mt-6 divide-y divide-rule border-y border-rule">
        {rows.map(([k, v]) => (
          <div key={k} className="py-2">
            <dt className="font-semibold">{k}</dt>
            <dd className="text-muted">{v}</dd>
          </div>
        ))}
      </dl>
    </div>
  )
}

const STATUSES = [
  ['PASS', 'bg-green-ink', 'The value is on the right side of the threshold.'],
  ['FAIL', 'bg-[#b3392d]', 'The value is on the wrong side. It is listed as a reason for NO-BUY.'],
  ['N/D', 'bg-[#8a6a14]', 'No data. It counts as a failure, never as a pass.'],
]

function Method() {
  return (
    <section id="method" className="bg-white py-16">
      <div className={wrap}>
        <h2 className={`${h2} max-w-[24ch] text-navy`}>Two questions, asked in this order</h2>
        <p className="mt-4 max-w-[62ch]">
          Fundamentals say whether the company is worth owning. Technicals say whether now is a moment of possible
          growth. These are the areas it looks at. The exact rules and values are in the code, not on this page.
        </p>
        <div className="mt-10 grid gap-10 md:grid-cols-2 md:gap-16">
          <Column title="Fundamentals" question="Is the company worth owning?" rows={FUNDAMENTALS} />
          <Column title="Technicals" question="Is now a moment of possible growth?" rows={TECHNICALS} />
        </div>
        <div className="mt-16 grid gap-6 border-t border-rule pt-10 md:grid-cols-3">
          {STATUSES.map(([s, tone, text]) => (
            <p key={s} className="flex items-start gap-4">
              <span className={`mt-0.5 rounded-sm px-2 text-sm font-semibold text-white ${tone}`}>{s}</span>
              <span className="max-w-[40ch]">{text}</span>
            </p>
          ))}
        </div>
      </div>
    </section>
  )
}

function Plan() {
  return (
    <section id="plan" className={`${wrap} grid items-center gap-10 py-16 lg:grid-cols-[1fr_1.2fr]`}>
      <div>
        <h2 className={`${h2} max-w-[24ch] text-navy`}>A BUY comes with the numbers to act on it</h2>
        <p className="mt-4 max-w-[62ch]">
          The trade plan gives an entry, a stop, a take profit and how many shares fit your capital.
        </p>
        <ul className="mt-6 max-w-[62ch] space-y-2">
          {[
            'Risk per trade is capped, and a riskier setting is rejected.',
            'A trade whose reward does not clearly beat its risk is discarded.',
            'No single stock can take over the portfolio.',
          ].map((t) => (
            <li key={t} className="flex gap-2">
              <svg aria-hidden viewBox="0 0 20 20" className="mt-1.5 size-4 shrink-0 text-teal">
                <path d="M4 10.5l4 4 8-9" fill="none" stroke="currentColor" strokeWidth={2} />
              </svg>
              {t}
            </li>
          ))}
        </ul>
      </div>
      <TradePlan />
    </section>
  )
}

function Screener() {
  const reduce = useReducedMotion()
  return (
    <section id="screener" className="bg-white py-16">
      <div className={`${wrap} grid items-start gap-10 lg:grid-cols-2`}>
        <div>
          <h2 className={`${h2} max-w-[24ch] text-navy`}>Start from the companies, then check the chart</h2>
          <p className="mt-4 max-w-[62ch]">
            The screener starts from the fundamentals and checks every candidate with the same rules as the full analysis.
            Only stocks where every criterion passes are listed, ready for the technical check.
          </p>
          <p className="mt-4 max-w-[62ch]">
            They are ranked by a quality score built from profitability and the trend of operating margin. Growth
            alone says nothing about profit. The score is informational and never changes a verdict.
          </p>
        </div>
        <figure>
          <table className="w-full text-left">
            <caption className="sr-only">Illustrative quality ranking of five stocks that passed</caption>
            <thead className="border-b border-rule text-sm text-muted">
              <tr>
                <th className="py-2 font-semibold">Stock</th>
                <th className="py-2 font-semibold">ROIC</th>
                <th className="py-2 font-semibold">Margin change</th>
                <th className="py-2 font-semibold">Quality</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-rule">
              {RANKING.map((r, n) => (
                <tr key={r.name}>
                  <th className="py-2 font-semibold">{r.name}</th>
                  <td className="py-2">{r.roic}</td>
                  <td className="py-2">{r.margin}</td>
                  <td className="w-32 py-2 sm:w-40">
                    <span className="flex items-center gap-2">
                      <span className="h-2 flex-1 rounded-sm bg-mist">
                        <motion.span
                          className="block h-full origin-left rounded-sm bg-teal"
                          style={{ width: `${r.score}%` }}
                          initial={{ scaleX: reduce ? 1 : 0 }}
                          whileInView={{ scaleX: 1 }}
                          viewport={{ once: true }}
                          transition={{ delay: n * 0.1, duration: 0.6, ease: 'easeOut' }}
                        />
                      </span>
                      <span className="w-7 text-right">{r.score}</span>
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <figcaption className="mt-2 text-sm text-muted">
            Illustrative values.
          </figcaption>
        </figure>
      </div>
    </section>
  )
}

const icon = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.5,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
} as const
const WAYS: { title: string; text: string; svg: ReactNode }[] = [
  {
    title: 'Command line',
    text: 'Analyze tickers, a watchlist or a Finviz screener URL. Export Markdown, CSV and JSON reports.',
    svg: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M7 9l3 3-3 3M13 15h4" />
      </>
    ),
  },
  {
    title: 'Web app',
    text: 'Screener, analysis, history and watchlist with PDF export. It listens on 127.0.0.1 only and has a local PIN lock.',
    svg: (
      <>
        <rect x="3" y="4" width="18" height="16" rx="2" />
        <path d="M3 9h18M7 6.5h.01M10 6.5h.01" />
      </>
    ),
  },
  {
    title: 'Desktop app',
    text: 'The same web app in its own window, with a Windows installer that bundles Python.',
    svg: (
      <>
        <rect x="3" y="4" width="18" height="12" rx="2" />
        <path d="M9 20h6M12 16v4" />
      </>
    ),
  },
]
const INSTALL = `git clone ${REPO}.git
cd ilovestock
cd web && npm ci && npm run build && cd ..
pip install .
ilovestock analyze HZO --detail`

function CopyBlock() {
  const [done, setDone] = useState(false)
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(INSTALL)
      setDone(true)
      setTimeout(() => setDone(false), 2000)
    } catch {
      /* clipboard blocked: the text is still selectable */
    }
  }
  return (
    <div className="relative rounded-md bg-ink text-mist">
      <pre className="overflow-x-auto p-4 pr-24 text-sm leading-relaxed">
        <code>{INSTALL}</code>
      </pre>
      <button
        type="button"
        onClick={copy}
        className="absolute top-2 right-2 cursor-pointer rounded-sm bg-panel px-3 py-1 text-sm font-semibold transition-colors hover:bg-teal"
      >
        <motion.span key={String(done)} initial={{ opacity: 0, y: 4 }} animate={{ opacity: 1, y: 0 }} className="block">
          {done ? 'Copied' : 'Copy'}
        </motion.span>
      </button>
    </div>
  )
}

function Ways() {
  return (
    <section id="install" className={`${wrap} py-16`}>
      <h2 className={`${h2} max-w-[24ch] text-navy`}>It runs on your computer</h2>
      <div className="mt-10 grid gap-10 md:grid-cols-3">
        {WAYS.map((w) => (
          <div key={w.title}>
            <svg aria-hidden viewBox="0 0 24 24" className="size-8 text-teal" {...icon}>
              {w.svg}
            </svg>
            <h3 className="mt-4 text-lg text-navy">{w.title}</h3>
            <p className="mt-2 max-w-[40ch] text-muted">{w.text}</p>
          </div>
        ))}
      </div>
      <div className="mt-10 grid items-start gap-6 lg:grid-cols-[1fr_1.2fr]">
        <p className="max-w-[62ch]">
          iLoveStock is open source and is not published on PyPI: install it from the repository. You need Python 3.11
          or later and Node.js to build the web interface.
        </p>
        <CopyBlock />
      </div>
    </section>
  )
}

const LIMITS = [
  [
    'Not financial advice',
    'A BUY means every rule of the method passed on the data available. Always recheck entry and stop on the live price before trading.',
  ],
  [
    'Data can be wrong, late or missing',
    'Fundamentals come from Finviz by scraping and prices from Yahoo. Finviz quotes are delayed 15 to 20 minutes, and missing values show as N/D.',
  ],
  [
    'Scraping may break a site’s terms',
    'Scraping Finviz may violate its terms of service. Use iLoveStock only if you accept that.',
  ],
  ['US stocks, USD only', 'NASDAQ, NYSE and AMEX. Prices quoted in another currency are rejected.'],
  [
    'Built for smaller companies',
    'The method targets smaller companies, so the biggest stocks will not get a BUY.',
  ],
  ['Open source, GPL-3.0', 'You can read every rule in the code.'],
]

function Limits() {
  return (
    <section id="limits" className="bg-ink py-16 text-mist">
      <div className={wrap}>
        <h2 className={`${h2} max-w-[24ch] text-white`}>What it does not do</h2>
        <p className="mt-4 max-w-[62ch] text-soft">Limits and risks get the same weight as the features above.</p>
        <dl className="mt-10 grid gap-x-16 gap-y-6 md:grid-cols-2">
          {LIMITS.map(([k, v]) => (
            <div key={k} className="border-t border-edge pt-4">
              <dt className="font-heading font-bold text-white">{k}</dt>
              <dd className="mt-2 max-w-[48ch] text-soft">{v}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  )
}

function Footer() {
  return (
    <footer className={`${wrap} flex flex-wrap items-center justify-between gap-4 py-10 text-sm text-muted`}>
      <p className="flex items-center gap-2">
        <img src="/logo.png" alt="" width={24} height={24} />
        iLoveStock. Educational tool, not financial advice.
      </p>
      <p>
        <a href={REPO} className="font-semibold text-navy hover:underline">
          Source on GitHub
        </a>
        {' · GPL-3.0'}
      </p>
    </footer>
  )
}

export default function App() {
  return (
    <MotionConfig reducedMotion="user">
      <a
        href="#method"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:rounded-md focus:bg-white focus:px-4 focus:py-2"
      >
        Skip to content
      </a>
      <Header />
      <main>
        <Hero />
        <Method />
        <Plan />
        <Screener />
        <Ways />
        <Limits />
      </main>
      <Footer />
    </MotionConfig>
  )
}
