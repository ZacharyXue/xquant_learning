import type { Strategy, Duration, BacktestRequest, BacktestResponse, BacktestResult, HistoryRecord } from '../types'

const API_BASE = '/api'

export async function getStrategies(): Promise<Strategy[]> {
  const res = await fetch(`${API_BASE}/strategies`)
  const data = await res.json()
  return data.strategies
}

export async function getDurations(): Promise<Duration[]> {
  const res = await fetch(`${API_BASE}/durations`)
  const data = await res.json()
  return data.durations
}

export async function runBacktest(request: BacktestRequest): Promise<BacktestResponse> {
  const res = await fetch(`${API_BASE}/backtest`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  return res.json()
}

export async function getBacktestData(strategy: string, stock: string): Promise<BacktestResult> {
  const res = await fetch(`${API_BASE}/data/${strategy}/${stock}`)
  if (!res.ok) {
    const err = await res.json()
    throw new Error(err.detail || '获取数据失败')
  }
  return res.json()
}

export async function getHistory(): Promise<HistoryRecord[]> {
  const res = await fetch(`${API_BASE}/history`)
  if (!res.ok) {
    return []
  }
  const data = await res.json()
  return data.history || []
}

export async function getConfig(): Promise<any> {
  const res = await fetch(`${API_BASE}/config`)
  return res.json()
}