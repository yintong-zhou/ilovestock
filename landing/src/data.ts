export type Status = 'PASS' | 'FAIL' | 'N/D'

export const REPO = 'https://github.com/yintong-zhou/ilovestock'

export interface Row {
  name: string
  value: string
  status: Status
}

export interface Sample {
  ticker: string
  label: string
  rows: Row[]
  buy: boolean
}

// Illustrative values only: no thresholds or parameters of the method are published here.
export const SAMPLES: Sample[] = [
  {
    ticker: 'SMPL',
    label: 'Passes every rule',
    buy: true,
    rows: [
      { name: 'Sales growth', value: '24.6%', status: 'PASS' },
      { name: 'Earnings growth', value: '31.2%', status: 'PASS' },
      { name: 'Return on equity', value: '18.4%', status: 'PASS' },
      { name: 'Dividend', value: 'none', status: 'PASS' },
      { name: 'Next earnings', value: '21 days', status: 'PASS' },
      { name: 'Relative strength', value: 'strong', status: 'PASS' },
      { name: 'Breakout', value: 'confirmed', status: 'PASS' },
      { name: 'Volume', value: '1.8x', status: 'PASS' },
    ],
  },
  {
    ticker: 'DEMO',
    label: 'Fails some rules',
    buy: false,
    rows: [
      { name: 'Sales growth', value: '12.1%', status: 'FAIL' },
      { name: 'Earnings growth', value: '28.0%', status: 'PASS' },
      { name: 'Return on equity', value: 'no data', status: 'N/D' },
      { name: 'Dividend', value: 'none', status: 'PASS' },
      { name: 'Next earnings', value: '6 days', status: 'FAIL' },
      { name: 'Relative strength', value: 'strong', status: 'PASS' },
      { name: 'Breakout', value: 'confirmed', status: 'PASS' },
      { name: 'Volume', value: '0.8x', status: 'FAIL' },
    ],
  },
]

// Illustrative weekly closes: a run-up, a pause, then a breakout.
export const CLOSES = [
  8.6, 8.8, 8.7, 8.9, 8.8, 9.1, 9.0, 9.4, 9.8, 10.2, 10.1, 10.6, 11.0, 11.4, 11.8, 12.0, 11.8, 12.1, 11.9, 12.2,
  11.9, 12.1, 11.8, 12.0, 12.2, 12.4,
]
export const PLAN = { entry: 12.4, stop: 11.55, target: 14.6, shares: 120 }

// Illustrative quality ranking.
export const RANKING = [
  { name: 'Company A', roic: '21.4%', margin: '+4.1 pts', score: 100 },
  { name: 'Company B', roic: '17.9%', margin: '+3.2 pts', score: 75 },
  { name: 'Company C', roic: '16.2%', margin: '+0.8 pts', score: 38 },
  { name: 'Company E', roic: 'no data', margin: '+2.0 pts', score: 25 },
  { name: 'Company D', roic: '12.7%', margin: '-1.5 pts', score: 13 },
]
