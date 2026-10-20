import { PageHeader, Panel } from '../components'

export default function Portfolio() {
  return (
    <>
      <PageHeader title="Portfolio">Positions you hold and when to sell them.</PageHeader>
      <Panel title="Not available yet">
        <p className="max-w-[65ch] text-muted">
          Portfolio tracking is planned for phase 2: open positions, hold or sell signals, trailing
          stops, exposure per sector and pauses after losses. This version analyzes stocks you do
          not own yet: use Analysis.
        </p>
      </Panel>
    </>
  )
}
