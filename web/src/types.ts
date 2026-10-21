// Mirrors the API's Pydantic/dataclass models (src/ilovestock/api/app.py, models.py).

export type Status = 'PASS' | 'FAIL' | 'N/D'
export type Verdict = 'BUY' | 'BUY*' | 'NO-BUY'

export interface CriterionResult {
  name: string
  status: Status
  value: number | string | null
  threshold: string
  note: string
}

export interface TradePlan {
  entry: number
  stop: number
  target: number | null
  shares: number
  max_loss: number
  effective_risk: number
  position_value: number
  binding: string
  risk_band: string
  trailing_stop_10w: number | null
  trailing_stop_8w: number | null
  discarded: string | null
  info: string[]
}

export interface TickerAnalysis {
  ticker: string
  verdict: Verdict
  reasons: string[]
  fundamental: CriterionResult[]
  technical: CriterionResult[]
  earnings: CriterionResult | null
  plan: TradePlan | null
  data_date: string | null
  error: string | null
}

export interface AnalyzeOut {
  disclaimer: string
  sources: string[]
  data_date: string
  finviz_warning: string
  results: TickerAnalysis[]
}

export interface PinStatus {
  configured: boolean
  unlocked: boolean
}

export interface AppConfig {
  capital: number
  risk_pct: number
  max_position_pct: number
  r_multiple: number
  entry_mode: 'breakout' | 'pullback' | 'restart'
  growth_basis: 'yoy' | 'qoq'
  sales_growth_min: number
  eps_growth_min: number
  roe_min: number
  institutional_own_max: number
  nano_max: number
  micro_max: number
  small_max: number
  mid_max: number
  large_max: number
}
