import type {
  Strategy, PaginatedTrades, DashboardData,
  BacktestRequest, BacktestResult, BacktestRun,
  FeeConfig, SlippageConfig, TradingHoursConfig,
} from '../types'

const API = '/api'

// ---- Dashboard ----
export async function fetchDashboard(mode = 'real'): Promise<DashboardData> {
  const res = await fetch(`${API}/dashboard?trade_mode=${mode}`)
  return res.json()
}

// ---- Strategy ----
export async function fetchStrategies(): Promise<Strategy[]> {
  const res = await fetch(`${API}/strategy`)
  return res.json()
}

export async function toggleStrategy(name: string, enabled: boolean): Promise<void> {
  await fetch(`${API}/strategy/toggle`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, enabled }),
  })
}

// ---- Trade History ----
export async function fetchTrades(params: {
  strategy_name?: string
  stock_code?: string
  side?: string
  status?: string
  trade_mode?: string
  page?: number
  page_size?: number
} = {}): Promise<PaginatedTrades> {
  const qs = new URLSearchParams()
  Object.entries(params).forEach(([k, v]) => { if (v !== undefined) qs.set(k, String(v)) })
  const res = await fetch(`${API}/trade?${qs}`)
  return res.json()
}

// ---- Backtest ----
export async function runBacktest(req: BacktestRequest): Promise<any> {
  const res = await fetch(`${API}/backtest/run`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(req),
  })
  return res.json()
}

export async function fetchBacktestHistory(limit = 20): Promise<BacktestRun[]> {
  const res = await fetch(`${API}/backtest/history?limit=${limit}`)
  return res.json()
}

export async function fetchBacktestResult(runId: number): Promise<BacktestResult> {
  const res = await fetch(`${API}/backtest/result/${runId}`)
  return res.json()
}

// ---- Settings ----
export async function fetchFeeConfig(): Promise<FeeConfig> {
  const res = await fetch(`${API}/settings/fee`)
  return res.json()
}

export async function updateFeeConfig(data: Partial<FeeConfig>): Promise<void> {
  await fetch(`${API}/settings/fee`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function fetchSlippageConfig(): Promise<SlippageConfig> {
  const res = await fetch(`${API}/settings/slippage`)
  return res.json()
}

export async function updateSlippageConfig(data: Partial<SlippageConfig>): Promise<void> {
  await fetch(`${API}/settings/slippage`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
}

export async function fetchTradingHours(): Promise<TradingHoursConfig> {
  const res = await fetch(`${API}/settings/trading-hours`)
  return res.json()
}

export async function fetchTradeMode(): Promise<string> {
  const res = await fetch(`${API}/settings/trade-mode`)
  const data = await res.json()
  return data.mode
}

export async function updateTradeMode(mode: string): Promise<void> {
  await fetch(`${API}/settings/trade-mode?mode=${mode}`, { method: 'PUT' })
}
