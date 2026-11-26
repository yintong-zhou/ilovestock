export type Status = 'PASS' | 'FAIL' | 'N/D'

export const REPO = 'https://github.com/yintong-zhou/ilovestock'

export interface Row {
  name: string
  rule: string
  value: string
  status: Status
}

export interface Sample {
  ticker: string
  label: string
  rows: Row[]
  buy: boolean
}

// Illustrative values: the rule names and thresholds are the real defaults, the numbers are not a real quote.
export const SAMPLES: Sample[] = [
  {
    ticker: 'SMPL',
    label: 'Passes every rule',
    buy: true,
    rows: [
      { name: 'Sales growth QoQ', rule: '> 20%', value: '24.6%', status: 'PASS' },
      { name: 'EPS growth QoQ', rule: '> 15%', value: '31.2%', status: 'PASS' },
      { name: 'ROE', rule: '> 15%', value: '18.4%', status: 'PASS' },
      { name: 'Dividend yield', rule: '= 0%', value: '0.00%', status: 'PASS' },
      { name: 'Next earnings', rule: '> 10 days', value: '21 days', status: 'PASS' },
      { name: 'Relative strength vs S&P 500', rule: 'RS > SMA 52w', value: '1.042', status: 'PASS' },
      { name: 'Donchian 10w', rule: 'weekly close > 12.31', value: '12.40', status: 'PASS' },
      { name: 'Breakout volume', rule: 'week > 10w average', value: '1.80x', status: 'PASS' },
    ],
  },
  {
    ticker: 'DEMO',
    label: 'Fails some rules',
    buy: false,
    rows: [
      { name: 'Sales growth QoQ', rule: '> 20%', value: '12.1%', status: 'FAIL' },
      { name: 'EPS growth QoQ', rule: '> 15%', value: '28.0%', status: 'PASS' },
      { name: 'ROE', rule: '> 15%', value: 'no data', status: 'N/D' },
      { name: 'Dividend yield', rule: '= 0%', value: '0.00%', status: 'PASS' },
      { name: 'Next earnings', rule: '> 10 days', value: '6 days', status: 'FAIL' },
      { name: 'Relative strength vs S&P 500', rule: 'RS > SMA 52w', value: '1.015', status: 'PASS' },
      { name: 'Donchian 10w', rule: 'weekly close > 9.84', value: '10.02', status: 'PASS' },
      { name: 'Breakout volume', rule: 'week > 10w average', value: '0.84x', status: 'FAIL' },
    ],
  },
]

// Weekly closes: a run-up, a 10-week base, then the breakout (entry 12.40, stop 11.55, 3R target 14.95).
export const CLOSES = [
  8.6, 8.8, 8.7, 8.9, 8.8, 9.1, 9.0, 9.4, 9.8, 10.2, 10.1, 10.6, 11.0, 11.4, 11.8, 12.0, 11.8, 12.1, 11.9, 12.2,
  11.9, 12.1, 11.8, 12.0, 12.2, 12.4,
]
export const PLAN = { entry: 12.4, stop: 11.55, target: 14.95, shares: 161 }

// Quality ranking: each stock gets a percentile for ROIC and for the 1-year operating margin
// change (N/D is worst); the score is their average. 5 stocks -> percentiles 100, 75, 50, 25, 0.
export const RANKING = [
  { name: 'Company A', roic: '21.4%', margin: '+4.1 pts', score: 100 },
  { name: 'Company B', roic: '17.9%', margin: '+3.2 pts', score: 75 },
  { name: 'Company C', roic: '16.2%', margin: '+0.8 pts', score: 38 },
  { name: 'Company E', roic: 'no data', margin: '+2.0 pts', score: 25 },
  { name: 'Company D', roic: '12.7%', margin: '-1.5 pts', score: 13 },
]
