export interface Strategy {
  id: string
  name: string
  description: string
}

export interface Duration {
  id: string
  name: string
}

export interface BacktestRequest {
  strategy: string
  stock_code: string
  duration: string
}

export interface BacktestResponse {
  success: boolean
  data?: BacktestResult
  error?: string
}

export interface BuyRecord {
  time: string
  price: number
  volume: number
  cost: number
  rsi?: number
  bias?: number
}

export interface BacktestResult {
  strategy: string
  stock_code: string
  start_time: string
  end_time: string
  total_trades: number
  profitable_trades: number
  total_investment: number
  final_value: number
  total_return: number
  return_rate: number
  volatility: number
  sharpe_ratio: number
  annualized_return?: number
  max_drawdown?: number
  calmar_ratio?: number
  win_rate?: number
  buy_records: BuyRecord[]
  prices: number[]
  times: string[]
}

export interface HistoryRecord {
  id: string
  filename: string
  strategy: string
  stock_code: string
  created_at: string
  total_trades: number
  return_rate: number
}