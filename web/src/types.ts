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

/** Informative: is the growth profitable? Never changes the verdict (models.Quality). */
export interface Quality {
  roic_pct: number | null
  margin_pct: number | null
  margin_year_ago_pct: number | null
  margin_change_pt: number | null
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
  price: number | null
  fundamentals_date: string | null
  quality: Quality | null
}

export interface AnalyzeOut {
  disclaimer: string
  sources: string[]
  data_date: string
  finviz_warning: string
  results: TickerAnalysis[]
}

/** One stock from the screener (src/ilovestock/screener.py). */
export interface ScreenHit {
  ticker: string
  market_cap: string | null
  quality: Quality
  score: number
  roic_rank: number | null
  margin_rank: number | null
}

export interface ScreenOut {
  disclaimer: string
  finviz_warning: string
  screened_on: string
  include_large: boolean // the Market cap rule was skipped
  candidates: number
  passed: number
  errors: string[]
  hits: ScreenHit[]
}

/** One saved analysis of one ticker (src/ilovestock/history.py). */
export interface HistoryRow {
  id: string
  analyzed_at: string
  data_date: string | null
  ticker: string
  verdict: Verdict
  price: number | null
  entry: number | null
  stop: number | null
  target: number | null
  shares: number | null
  reasons: string[]
  criteria: CriterionResult[]
  note: string
  edited_at: string | null
}

export type HistoryEdit = Partial<Pick<HistoryRow, 'verdict' | 'price' | 'entry' | 'stop' | 'target' | 'shares' | 'note'>>

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
  max_candidates: number
  max_candidates_large: number
}
