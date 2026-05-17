-- xtquant 量化交易系统 初始数据库结构

CREATE TABLE IF NOT EXISTS strategies (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(200) NOT NULL,
    description TEXT,
    enabled BOOLEAN DEFAULT false,
    config JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS strategy_signals (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    signal_type VARCHAR(20) NOT NULL,       -- buy / sell / skip
    price NUMERIC(12, 4),
    volume INTEGER,
    reason TEXT,
    indicators JSONB DEFAULT '{}',          -- RSI, MA, bias 等指标值
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS trade_records (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100),
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    side VARCHAR(10) NOT NULL,              -- buy / sell
    volume INTEGER NOT NULL,
    order_price NUMERIC(12, 4),
    filled_price NUMERIC(12, 4),
    order_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'pending',   -- pending/filled/partial/cancelled/rejected
    commission NUMERIC(12, 4) DEFAULT 0,    -- 佣金
    stamp_tax NUMERIC(12, 4) DEFAULT 0,     -- 印花税
    transfer_fee NUMERIC(12, 4) DEFAULT 0,  -- 过户费
    slippage NUMERIC(12, 4) DEFAULT 0,      -- 滑点成本
    amount NUMERIC(16, 4),
    trade_mode VARCHAR(10) DEFAULT 'real',  -- real / sim
    error_msg TEXT,
    order_remark TEXT,
    extra JSONB DEFAULT '{}',
    trade_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS positions (
    id SERIAL PRIMARY KEY,
    stock_code VARCHAR(20) NOT NULL,
    stock_name VARCHAR(100),
    volume INTEGER NOT NULL,
    avg_cost NUMERIC(12, 4),
    current_price NUMERIC(12, 4),
    market_value NUMERIC(16, 4),
    profit_loss NUMERIC(16, 4),
    profit_loss_ratio NUMERIC(10, 6),
    trade_mode VARCHAR(10) DEFAULT 'real',
    snapshot_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS account_snapshots (
    id SERIAL PRIMARY KEY,
    total_asset NUMERIC(16, 4),
    available_cash NUMERIC(16, 4),
    frozen_cash NUMERIC(16, 4),
    market_value NUMERIC(16, 4),
    total_profit_loss NUMERIC(16, 4),
    trade_mode VARCHAR(10) DEFAULT 'real',
    snapshot_time TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS backtest_runs (
    id SERIAL PRIMARY KEY,
    strategy_name VARCHAR(100) NOT NULL,
    stock_code VARCHAR(20) NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    params JSONB DEFAULT '{}',
    status VARCHAR(20) DEFAULT 'running',   -- running / completed / failed
    error_msg TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    completed_at TIMESTAMP
);

CREATE TABLE IF NOT EXISTS backtest_results (
    id SERIAL PRIMARY KEY,
    run_id INTEGER REFERENCES backtest_runs(id) ON DELETE CASCADE,
    total_trades INTEGER DEFAULT 0,
    profitable_trades INTEGER DEFAULT 0,
    win_rate NUMERIC(10, 4),
    total_investment NUMERIC(16, 4),
    final_value NUMERIC(16, 4),
    total_return NUMERIC(16, 4),
    return_rate NUMERIC(10, 6),
    annualized_return NUMERIC(10, 6),
    max_drawdown NUMERIC(10, 6),
    volatility NUMERIC(10, 6),
    sharpe_ratio NUMERIC(10, 4),
    calmar_ratio NUMERIC(10, 4),
    equity_curve JSONB DEFAULT '[]',
    buy_signals JSONB DEFAULT '[]',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_configs (
    id SERIAL PRIMARY KEY,
    config_key VARCHAR(200) NOT NULL UNIQUE,
    config_value JSONB NOT NULL,
    description VARCHAR(500),
    updated_at TIMESTAMP DEFAULT NOW(),
    created_at TIMESTAMP DEFAULT NOW()
);

-- 索引
CREATE INDEX IF NOT EXISTS idx_trade_records_strategy ON trade_records(strategy_name, trade_time);
CREATE INDEX IF NOT EXISTS idx_trade_records_stock ON trade_records(stock_code, trade_time);
CREATE INDEX IF NOT EXISTS idx_trade_records_time ON trade_records(trade_time);
CREATE INDEX IF NOT EXISTS idx_trade_records_mode ON trade_records(trade_mode);
CREATE INDEX IF NOT EXISTS idx_positions_snapshot ON positions(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_account_snapshots_time ON account_snapshots(snapshot_time);
CREATE INDEX IF NOT EXISTS idx_strategy_signals_time ON strategy_signals(created_at);
CREATE INDEX IF NOT EXISTS idx_backtest_runs_strategy ON backtest_runs(strategy_name);
