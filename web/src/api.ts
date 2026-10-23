import type { AnalyzeOut, AppConfig, HistoryEdit, HistoryRow, PinStatus, ScreenOut } from './types'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const res = await fetch(path, {
    method,
    headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
  if (!res.ok) {
    let message = res.statusText
    try {
      const { detail } = await res.json()
      message = typeof detail === 'string' ? detail : JSON.stringify(detail)
    } catch {
      // non-JSON error body: keep the status text
    }
    throw new ApiError(res.status, message)
  }
  return res
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await send(method, path, body)
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const api = {
  pinStatus: () => request<PinStatus>('GET', '/api/pin/status'),
  unlock: (pin: string) => request<void>('POST', '/api/pin/unlock', { pin }),
  lock: () => request<void>('POST', '/api/pin/lock'),
  changePin: (current_pin: string, new_pin: string) =>
    request<void>('POST', '/api/pin/change', { current_pin, new_pin }),
  getConfig: () => request<AppConfig>('GET', '/api/config'),
  putConfig: (cfg: AppConfig) => request<AppConfig>('PUT', '/api/config', cfg),
  analyze: (tickers: string[], finviz_url: string | null, allow_missing: boolean) =>
    request<AnalyzeOut>('POST', '/api/analyze', { tickers, finviz_url, allow_missing }),
  screen: (max: number, include_large: boolean) =>
    request<ScreenOut>('POST', '/api/screen', { max, include_large }),
  history: () => request<HistoryRow[]>('GET', '/api/history'),
  editHistory: (id: string, changes: HistoryEdit) => request<HistoryRow>('PATCH', `/api/history/${encodeURIComponent(id)}`, changes),
  deleteHistory: (id: string) => request<void>('DELETE', `/api/history/${encodeURIComponent(id)}`),
  deleteTickerHistory: (ticker: string) =>
    request<void>('DELETE', `/api/history?ticker=${encodeURIComponent(ticker)}`),
  historyPdf: (title: 'History' | 'Watchlist', ids: string[]) =>
    send('POST', '/api/history/pdf', { title, ids }).then((r) => r.blob()),
  watchlist: () => request<string[]>('GET', '/api/watchlist'),
  watch: (ticker: string) => request<string[]>('PUT', `/api/watchlist/${encodeURIComponent(ticker)}`),
  unwatch: (ticker: string) => request<string[]>('DELETE', `/api/watchlist/${encodeURIComponent(ticker)}`),
}
