export interface Strategy {
  name: string
  display_name: string
  description: string
  enabled: boolean
  config: Record<string, any>
}

export interface TradeRecord {
  id: number
  strategy_name: string | null
  stock_code: string
  side: string
  volume: number
  order_price: number | null
  filled_price: number | null
  status: string
  commission: number
  stamp_tax: number
  transfer_fee: number
  slippage: number
  amount: number | null
  trade_mode: string
  trade_time: string
  created_at: string
}

export interface Position {
  stock_code: string
  stock_name: string
  volume: number
  avg_cost: number
  current_price: number
  market_value: number
  profit_loss: number
}

export interface DashboardData {
  total_asset: number
  available_cash: number
  market_value: number
  total_profit_loss: number
  positions: Position[]
  recent_trades: {
    id: number
    strategy_name: string | null
    stock_code: string
    side: string
    volume: number
    status: string
    amount: number
    trade_time: string
  }[]
  active_strategies: string[]
}

export interface PaginatedTrades {
  items: TradeRecord[]
  total: number
  page: number
  page_size: number
}

export interface BacktestRequest {
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  params?: Record<string, any>
}

export interface BacktestResult {
  run_id: number
  total_trades: number
  profitable_trades: number
  win_rate: number
  total_investment: number
  final_value: number
  return_rate: number
  annualized_return: number
  max_drawdown: number
  sharpe_ratio: number
  calmar_ratio: number
  equity_curve: { date: string; value: number }[]
  buy_signals: { date: string; price: number }[]
  error_msg?: string
  benchmark?: {
    final_value: number
    return_rate: number
    annualized_return: number
    max_drawdown: number
    sharpe_ratio: number
    calmar_ratio: number
    equity_curve: { date: string; value: number }[]
  }
}

export interface OptimizeRequest {
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  param_grid: Record<string, number[]>
}

export interface BacktestRun {
  id: number
  strategy_name: string
  stock_code: string
  start_date: string
  end_date: string
  status: string
  error_msg?: string
  started_at: string
}

export interface FeeConfig {
  commission_rate: number
  stamp_tax_rate: number
  transfer_fee_rate: number
  min_commission: number
}

export interface SlippageConfig {
  rate: number
  mode: string
}

export interface TradingHoursConfig {
  start: string
  end: string
  cancel_unfilled_at: string
}

export interface WSMessage {
  type: string
  data: any
}
