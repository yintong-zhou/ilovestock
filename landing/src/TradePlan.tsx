import { motion, useInView, useReducedMotion } from 'motion/react'
import { useRef } from 'react'

import { CLOSES, PLAN } from './data'

const X0 = 16
const X1 = 456
const y = (p: number) => 340 - (p - 8.4) * 46 // 8.60 -> 331, 14.95 -> 39
const x = (n: number) => X0 + (n * (X1 - X0)) / (CLOSES.length - 1)
const LINE = CLOSES.map((c, n) => `${n ? 'L' : 'M'}${x(n).toFixed(1)} ${y(c).toFixed(1)}`).join(' ')
const BASE_FROM = CLOSES.length - 11 // the 10 weeks before the breakout week

const LEVELS = [
  { label: `Target ${PLAN.target.toFixed(2)} (3R)`, p: PLAN.target, color: 'var(--color-green)', text: 'var(--color-green-ink)' },
  { label: `Entry ${PLAN.entry.toFixed(2)}`, p: PLAN.entry, color: 'var(--color-navy)', text: 'var(--color-navy)' },
  { label: `Stop ${PLAN.stop.toFixed(2)}`, p: PLAN.stop, color: '#b3392d', text: '#b3392d' },
]

export default function TradePlan() {
  const ref = useRef<SVGSVGElement>(null)
  const seen = useInView(ref, { once: true, margin: '0px 0px -20% 0px' })
  const reduce = useReducedMotion()
  const go = seen || !!reduce
  const tr = (delay: number, duration: number) => (reduce ? { duration: 0 } : { delay, duration, ease: 'easeOut' as const })

  return (
    <figure>
      <svg
        ref={ref}
        viewBox="0 0 640 350"
        role="img"
        aria-label="Illustrative weekly price chart: a run-up, a ten week base and a breakout, with entry at 12.40, stop at 11.55 and a 3R target at 14.95."
        className="h-auto w-full"
      >
        <motion.rect
          x={x(BASE_FROM)}
          y={y(12.31)}
          width={x(CLOSES.length - 2) - x(BASE_FROM)}
          height={y(11.55) - y(12.31)}
          fill="var(--color-teal)"
          initial={{ opacity: 0 }}
          animate={{ opacity: go ? 0.12 : 0 }}
          transition={tr(1.2, 0.6)}
        />
        <motion.rect
          x={X0}
          y={y(PLAN.entry)}
          width={X1 - X0}
          height={y(PLAN.stop) - y(PLAN.entry)}
          fill="#b3392d"
          initial={{ opacity: 0 }}
          animate={{ opacity: go ? 0.1 : 0 }}
          transition={tr(2.6, 0.5)}
        />
        <motion.rect
          x={X0}
          y={y(PLAN.target)}
          width={X1 - X0}
          height={y(PLAN.entry) - y(PLAN.target)}
          fill="var(--color-green)"
          initial={{ opacity: 0 }}
          animate={{ opacity: go ? 0.1 : 0 }}
          transition={tr(2.7, 0.5)}
        />
        {LEVELS.map((l, n) => (
          <g key={l.label}>
            <motion.line
              x1={X0}
              x2={X1}
              y1={y(l.p)}
              y2={y(l.p)}
              stroke={l.color}
              strokeWidth={1.5}
              strokeDasharray="5 4"
              initial={{ pathLength: 0 }}
              animate={{ pathLength: go ? 1 : 0 }}
              transition={tr(2.1 + n * 0.15, 0.6)}
            />
            <motion.text
              x={X1 + 12}
              y={y(l.p) + 5}
              fill={l.text}
              fontSize={18}
              fontWeight={600}
              initial={{ opacity: 0 }}
              animate={{ opacity: go ? 1 : 0 }}
              transition={tr(2.7 + n * 0.15, 0.4)}
            >
              {l.label}
            </motion.text>
          </g>
        ))}
        <motion.path
          d={LINE}
          fill="none"
          stroke="var(--color-ink)"
          strokeWidth={2.25}
          strokeLinejoin="round"
          strokeLinecap="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: go ? 1 : 0 }}
          transition={tr(0, 2)}
        />
        <motion.circle
          cx={x(CLOSES.length - 1)}
          cy={y(PLAN.entry)}
          r={5}
          fill="var(--color-navy)"
          initial={{ scale: 0 }}
          animate={{ scale: go ? 1 : 0 }}
          style={{ transformOrigin: `${x(CLOSES.length - 1)}px ${y(PLAN.entry)}px` }}
          transition={reduce ? { duration: 0 } : { delay: 2, type: 'spring', stiffness: 500, damping: 18 }}
        />
        <motion.text
          x={x(BASE_FROM)}
          y={y(11.55) + 22}
          fill="var(--color-muted)"
          fontSize={17}
          initial={{ opacity: 0 }}
          animate={{ opacity: go ? 1 : 0 }}
          transition={tr(1.4, 0.4)}
        >
          10-week base
        </motion.text>
      </svg>
      <figcaption className="mt-2 text-sm text-muted">
        Illustrative weekly closes, not a real stock. Stop = lowest low of the base; target = entry + 3 x (entry - stop).
      </figcaption>
    </figure>
  )
}
