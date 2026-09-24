-- ==============================================================================
-- FUTURES & OPTIONS TRADING, VOLATILITY AND SETTLEMENT MANAGEMENT DBMS SCHEMA
-- Relational DBMS with 3NF Normalization, Foreign Keys, Triggers, Views & Indexes
-- ==============================================================================

PRAGMA foreign_keys = ON;

-- 1. UNDERLYING ASSETS TABLE
CREATE TABLE IF NOT EXISTS underlying_assets (
    underlying_id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol VARCHAR(20) NOT NULL UNIQUE,
    asset_name VARCHAR(100) NOT NULL,
    asset_class VARCHAR(20) NOT NULL CHECK (asset_class IN ('EQUITY_INDEX', 'EQUITY_STOCK', 'COMMODITY', 'CURRENCY')),
    spot_price DECIMAL(15, 4) NOT NULL CHECK (spot_price > 0),
    lot_size INTEGER NOT NULL DEFAULT 1 CHECK (lot_size > 0),
    tick_size DECIMAL(10, 4) NOT NULL DEFAULT 0.05,
    currency VARCHAR(10) NOT NULL DEFAULT 'INR',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. DERIVATIVE CONTRACTS TABLE (FUTURES & OPTIONS SPECIFICATION)
CREATE TABLE IF NOT EXISTS contracts (
    contract_id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_symbol VARCHAR(50) NOT NULL UNIQUE,
    underlying_id INTEGER NOT NULL,
    contract_type VARCHAR(5) NOT NULL CHECK (contract_type IN ('FUT', 'CE', 'PE')),
    strike_price DECIMAL(15, 4) DEFAULT NULL, -- NULL for Futures
    expiry_date DATE NOT NULL,
    contract_size INTEGER NOT NULL CHECK (contract_size > 0),
    settlement_type VARCHAR(10) NOT NULL DEFAULT 'CASH' CHECK (settlement_type IN ('CASH', 'PHYSICAL')),
    is_active BOOLEAN NOT NULL DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (underlying_id) REFERENCES underlying_assets(underlying_id) ON DELETE RESTRICT,
    CHECK (
        (contract_type = 'FUT' AND strike_price IS NULL) OR
        (contract_type IN ('CE', 'PE') AND strike_price IS NOT NULL AND strike_price > 0)
    )
);

-- 3. TRADERS & CLEARING ACCOUNTS TABLE
CREATE TABLE IF NOT EXISTS traders (
    trader_id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_number VARCHAR(30) NOT NULL UNIQUE,
    name VARCHAR(100) NOT NULL,
    account_type VARCHAR(20) NOT NULL CHECK (account_type IN ('RETAIL', 'PROPRIETARY', 'INSTITUTIONAL', 'MARKET_MAKER')),
    cash_balance DECIMAL(18, 4) NOT NULL DEFAULT 1000000.0000,
    collateral_value DECIMAL(18, 4) NOT NULL DEFAULT 0.0000,
    margin_multiplier DECIMAL(5, 2) NOT NULL DEFAULT 1.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. ORDERS TABLE (ORDER BOOK)
CREATE TABLE IF NOT EXISTS orders (
    order_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trader_id INTEGER NOT NULL,
    contract_id INTEGER NOT NULL,
    order_type VARCHAR(10) NOT NULL CHECK (order_type IN ('MARKET', 'LIMIT', 'STOP_LOSS')),
    side VARCHAR(5) NOT NULL CHECK (side IN ('BUY', 'SELL')),
    price DECIMAL(15, 4) NOT NULL CHECK (price >= 0),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    filled_quantity INTEGER NOT NULL DEFAULT 0,
    order_status VARCHAR(15) NOT NULL DEFAULT 'PENDING' CHECK (order_status IN ('PENDING', 'PARTIAL', 'FILLED', 'CANCELLED', 'REJECTED')),
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trader_id) REFERENCES traders(trader_id) ON DELETE CASCADE,
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE RESTRICT
);

-- 5. TRADES TABLE (TRADE EXECUTION BOOK)
CREATE TABLE IF NOT EXISTS trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    buy_order_id INTEGER,
    sell_order_id INTEGER,
    contract_id INTEGER NOT NULL,
    buyer_id INTEGER NOT NULL,
    seller_id INTEGER NOT NULL,
    trade_price DECIMAL(15, 4) NOT NULL CHECK (trade_price > 0),
    trade_qty INTEGER NOT NULL CHECK (trade_qty > 0),
    executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE RESTRICT,
    FOREIGN KEY (buyer_id) REFERENCES traders(trader_id) ON DELETE RESTRICT,
    FOREIGN KEY (seller_id) REFERENCES traders(trader_id) ON DELETE RESTRICT
);

-- 6. POSITIONS TABLE (REAL-TIME AGGREGATED PORTFOLIO BOOK)
CREATE TABLE IF NOT EXISTS positions (
    position_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trader_id INTEGER NOT NULL,
    contract_id INTEGER NOT NULL,
    net_quantity INTEGER NOT NULL DEFAULT 0, -- Positive = Long, Negative = Short
    total_buy_qty INTEGER NOT NULL DEFAULT 0,
    total_sell_qty INTEGER NOT NULL DEFAULT 0,
    avg_buy_price DECIMAL(15, 4) NOT NULL DEFAULT 0.0000,
    avg_sell_price DECIMAL(15, 4) NOT NULL DEFAULT 0.0000,
    realized_pnl DECIMAL(18, 4) NOT NULL DEFAULT 0.0000,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trader_id) REFERENCES traders(trader_id) ON DELETE CASCADE,
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE RESTRICT,
    UNIQUE(trader_id, contract_id)
);

-- 7. MARKET SNAPSHOTS & TICKS (PRICE, VOLUME, OI & VOLATILITY)
CREATE TABLE IF NOT EXISTS market_snapshots (
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_id INTEGER NOT NULL,
    snapshot_time TIMESTAMP NOT NULL,
    underlying_spot DECIMAL(15, 4) NOT NULL,
    last_traded_price DECIMAL(15, 4) NOT NULL,
    bid_price DECIMAL(15, 4),
    ask_price DECIMAL(15, 4),
    volume INTEGER NOT NULL DEFAULT 0,
    open_interest INTEGER NOT NULL DEFAULT 0,
    implied_volatility DECIMAL(8, 4), -- e.g., 0.1850 for 18.5%
    delta DECIMAL(8, 4),
    gamma DECIMAL(10, 6),
    theta DECIMAL(10, 4),
    vega DECIMAL(10, 4),
    rho DECIMAL(10, 4),
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE CASCADE
);

-- 8. DAILY SETTLEMENT LEDGER (MARK-TO-MARKET MTM & CASH FLOWS)
CREATE TABLE IF NOT EXISTS daily_settlement_ledger (
    settlement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    settlement_date DATE NOT NULL,
    trader_id INTEGER NOT NULL,
    contract_id INTEGER NOT NULL,
    open_net_qty INTEGER NOT NULL,
    prior_settlement_price DECIMAL(15, 4) NOT NULL,
    current_settlement_price DECIMAL(15, 4) NOT NULL,
    mtm_pnl DECIMAL(18, 4) NOT NULL,
    variation_margin DECIMAL(18, 4) NOT NULL, -- Cash to deposit (+) or receive (-)
    settlement_status VARCHAR(20) NOT NULL DEFAULT 'CLEARED' CHECK (settlement_status IN ('CLEARED', 'MARGIN_CALL', 'DEFAULTED', 'FINAL_EXPIRY')),
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trader_id) REFERENCES traders(trader_id) ON DELETE CASCADE,
    FOREIGN KEY (contract_id) REFERENCES contracts(contract_id) ON DELETE RESTRICT,
    UNIQUE(settlement_date, trader_id, contract_id)
);

-- 9. MARGIN ACCOUNTS & RISK LEDGER
CREATE TABLE IF NOT EXISTS margin_ledger (
    margin_record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    trader_id INTEGER NOT NULL,
    calc_date DATE NOT NULL,
    initial_margin_req DECIMAL(18, 4) NOT NULL,
    maintenance_margin_req DECIMAL(18, 4) NOT NULL,
    equity_balance DECIMAL(18, 4) NOT NULL, -- Cash + Collateral + Unrealized MTM
    margin_utilization_pct DECIMAL(7, 2) NOT NULL,
    is_margin_call BOOLEAN NOT NULL DEFAULT 0,
    margin_shortfall DECIMAL(18, 4) NOT NULL DEFAULT 0.0000,
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (trader_id) REFERENCES traders(trader_id) ON DELETE CASCADE,
    UNIQUE(trader_id, calc_date)
);

-- 10. DATASET INGESTION AUDIT LOG TABLE
CREATE TABLE IF NOT EXISTS dataset_ingestion_log (
    ingest_id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename VARCHAR(255) NOT NULL,
    dataset_type VARCHAR(50) NOT NULL,
    records_ingested INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(20) NOT NULL,
    notes TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ==============================================================================
-- INDEXES FOR HIGH-PERFORMANCE QUERY EXECUTION
-- ==============================================================================
CREATE INDEX IF NOT EXISTS idx_contracts_underlying ON contracts(underlying_id, contract_type, expiry_date);
CREATE INDEX IF NOT EXISTS idx_contracts_symbol ON contracts(contract_symbol);
CREATE INDEX IF NOT EXISTS idx_trades_contract ON trades(contract_id, executed_at);
CREATE INDEX IF NOT EXISTS idx_trades_buyer ON trades(buyer_id);
CREATE INDEX IF NOT EXISTS idx_trades_seller ON trades(seller_id);
CREATE INDEX IF NOT EXISTS idx_orders_trader ON orders(trader_id, order_status);
CREATE INDEX IF NOT EXISTS idx_positions_trader ON positions(trader_id);
CREATE INDEX IF NOT EXISTS idx_market_snapshots_contract ON market_snapshots(contract_id, snapshot_time);
CREATE INDEX IF NOT EXISTS idx_settlement_date ON daily_settlement_ledger(settlement_date, trader_id);

-- ==============================================================================
-- SQL VIEWS FOR REPORTING & ANALYTICS
-- ==============================================================================

-- VIEW 1: OPEN POSITIONS WITH CONTRACT DETAILS & UNDERLYING
CREATE VIEW IF NOT EXISTS vw_open_positions AS
SELECT 
    p.position_id,
    p.trader_id,
    t.name AS trader_name,
    t.account_number,
    c.contract_id,
    c.contract_symbol,
    u.symbol AS underlying_symbol,
    u.spot_price AS underlying_spot,
    c.contract_type,
    c.strike_price,
    c.expiry_date,
    c.contract_size,
    p.net_quantity,
    CASE 
        WHEN p.net_quantity > 0 THEN 'LONG'
        WHEN p.net_quantity < 0 THEN 'SHORT'
        ELSE 'CLOSED'
    END AS position_side,
    p.avg_buy_price,
    p.avg_sell_price,
    p.realized_pnl,
    COALESCE(ms.last_traded_price, 0) AS current_ltp,
    COALESCE(ms.implied_volatility, 0) AS current_iv,
    COALESCE(ms.delta, 0) AS delta,
    COALESCE(ms.gamma, 0) AS gamma,
    COALESCE(ms.theta, 0) AS theta,
    COALESCE(ms.vega, 0) AS vega,
    -- Unrealized P&L Calculation
    CASE
        WHEN p.net_quantity > 0 THEN (COALESCE(ms.last_traded_price, p.avg_buy_price) - p.avg_buy_price) * p.net_quantity * c.contract_size
        WHEN p.net_quantity < 0 THEN (p.avg_sell_price - COALESCE(ms.last_traded_price, p.avg_sell_price)) * ABS(p.net_quantity) * c.contract_size
        ELSE 0
    END AS unrealized_pnl
FROM positions p
JOIN traders t ON p.trader_id = t.trader_id
JOIN contracts c ON p.contract_id = c.contract_id
JOIN underlying_assets u ON c.underlying_id = u.underlying_id
LEFT JOIN (
    -- Latest market snapshot for each contract
    SELECT contract_id, last_traded_price, implied_volatility, delta, gamma, theta, vega
    FROM market_snapshots
    WHERE snapshot_id IN (
        SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id
    )
) ms ON c.contract_id = ms.contract_id
WHERE p.net_quantity != 0;

-- VIEW 2: PORTFOLIO GREEKS SUMMARY PER TRADER
CREATE VIEW IF NOT EXISTS vw_portfolio_greeks AS
SELECT 
    t.trader_id,
    t.name AS trader_name,
    u.symbol AS underlying_symbol,
    COUNT(p.contract_id) AS total_open_contracts,
    SUM(p.net_quantity * c.contract_size) AS net_shares_exposure,
    ROUND(SUM(p.net_quantity * c.contract_size * COALESCE(ms.delta, 0)), 4) AS portfolio_delta,
    ROUND(SUM(p.net_quantity * c.contract_size * COALESCE(ms.gamma, 0)), 6) AS portfolio_gamma,
    ROUND(SUM(p.net_quantity * c.contract_size * COALESCE(ms.theta, 0)), 2) AS portfolio_theta,
    ROUND(SUM(p.net_quantity * c.contract_size * COALESCE(ms.vega, 0)), 2) AS portfolio_vega
FROM positions p
JOIN traders t ON p.trader_id = t.trader_id
JOIN contracts c ON p.contract_id = c.contract_id
JOIN underlying_assets u ON c.underlying_id = u.underlying_id
LEFT JOIN (
    SELECT contract_id, delta, gamma, theta, vega
    FROM market_snapshots
    WHERE snapshot_id IN (
        SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id
    )
) ms ON c.contract_id = ms.contract_id
WHERE p.net_quantity != 0
GROUP BY t.trader_id, t.name, u.symbol;

-- VIEW 3: SETTLEMENT & CLEARING SUMMARY
CREATE VIEW IF NOT EXISTS vw_settlement_summary AS
SELECT 
    s.settlement_date,
    t.trader_id,
    t.name AS trader_name,
    COUNT(s.contract_id) AS contracts_settled,
    ROUND(SUM(s.mtm_pnl), 2) AS total_mtm_pnl,
    ROUND(SUM(s.variation_margin), 2) AS net_variation_margin,
    MAX(s.settlement_status) AS overall_status
FROM daily_settlement_ledger s
JOIN traders t ON s.trader_id = t.trader_id
GROUP BY s.settlement_date, t.trader_id, t.name;

-- ==============================================================================
-- DATABASE TRIGGERS
-- ==============================================================================

-- TRIGGER 1: UPDATE BUYER POSITION ON TRADE EXECUTION
CREATE TRIGGER IF NOT EXISTS trg_trade_buyer_position
AFTER INSERT ON trades
BEGIN
    INSERT INTO positions (trader_id, contract_id, net_quantity, total_buy_qty, avg_buy_price, last_updated)
    VALUES (
        NEW.buyer_id, 
        NEW.contract_id, 
        NEW.trade_qty, 
        NEW.trade_qty, 
        NEW.trade_price, 
        CURRENT_TIMESTAMP
    )
    ON CONFLICT(trader_id, contract_id) DO UPDATE SET
        avg_buy_price = (
            (positions.avg_buy_price * positions.total_buy_qty) + (NEW.trade_price * NEW.trade_qty)
        ) / (positions.total_buy_qty + NEW.trade_qty),
        total_buy_qty = positions.total_buy_qty + NEW.trade_qty,
        net_quantity = positions.net_quantity + NEW.trade_qty,
        last_updated = CURRENT_TIMESTAMP;
        
    -- Deduct buyer cash balance
    UPDATE traders 
    SET cash_balance = cash_balance - (NEW.trade_price * NEW.trade_qty)
    WHERE trader_id = NEW.buyer_id;
END;

-- TRIGGER 2: UPDATE SELLER POSITION ON TRADE EXECUTION
CREATE TRIGGER IF NOT EXISTS trg_trade_seller_position
AFTER INSERT ON trades
BEGIN
    INSERT INTO positions (trader_id, contract_id, net_quantity, total_sell_qty, avg_sell_price, last_updated)
    VALUES (
        NEW.seller_id, 
        NEW.contract_id, 
        -NEW.trade_qty, 
        NEW.trade_qty, 
        NEW.trade_price, 
        CURRENT_TIMESTAMP
    )
    ON CONFLICT(trader_id, contract_id) DO UPDATE SET
        avg_sell_price = (
            (positions.avg_sell_price * positions.total_sell_qty) + (NEW.trade_price * NEW.trade_qty)
        ) / (positions.total_sell_qty + NEW.trade_qty),
        total_sell_qty = positions.total_sell_qty + NEW.trade_qty,
        net_quantity = positions.net_quantity - NEW.trade_qty,
        last_updated = CURRENT_TIMESTAMP;
        
    -- Credit seller cash balance
    UPDATE traders 
    SET cash_balance = cash_balance + (NEW.trade_price * NEW.trade_qty)
    WHERE trader_id = NEW.seller_id;
END;
