"""
Institutional SQL Query Library for F&O Analytics and Settlement.
Contains queries demonstrating Common Table Expressions (CTEs), Window Functions,
Recursive Aggregations, and Analytical Rollups.
"""

QUERIES = {
    "Portfolio Summary & Net Greeks": {
        "description": "Calculates real-time net Delta, Gamma, Theta, Vega exposure aggregated per trader across all open positions.",
        "sql": """
SELECT 
    t.account_number,
    t.name AS trader_name,
    t.account_type,
    t.cash_balance,
    COUNT(p.contract_id) AS open_positions_count,
    ROUND(SUM(p.net_quantity * c.contract_size), 2) AS total_contract_units,
    ROUND(SUM(p.net_quantity * c.contract_size * COALESCE(ms.delta, 0)), 4) AS portfolio_delta,
    ROUND(SUM(p.net_quantity * c.contract_size * COALESCE(ms.gamma, 0)), 6) AS portfolio_gamma,
    ROUND(SUM(p.net_quantity * c.contract_size * COALESCE(ms.theta, 0)), 2) AS portfolio_theta_daily_decay,
    ROUND(SUM(p.net_quantity * c.contract_size * COALESCE(ms.vega, 0)), 2) AS portfolio_vega_per_1pct_vol,
    ROUND(SUM(
        CASE 
            WHEN p.net_quantity > 0 THEN (COALESCE(ms.last_traded_price, p.avg_buy_price) - p.avg_buy_price) * p.net_quantity * c.contract_size
            WHEN p.net_quantity < 0 THEN (p.avg_sell_price - COALESCE(ms.last_traded_price, p.avg_sell_price)) * ABS(p.net_quantity) * c.contract_size
            ELSE 0 
        END
    ), 2) AS total_unrealized_pnl
FROM traders t
JOIN positions p ON t.trader_id = p.trader_id
JOIN contracts c ON p.contract_id = c.contract_id
LEFT JOIN (
    SELECT contract_id, last_traded_price, delta, gamma, theta, vega
    FROM market_snapshots
    WHERE snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
) ms ON c.contract_id = ms.contract_id
WHERE p.net_quantity != 0
GROUP BY t.trader_id, t.account_number, t.name, t.account_type, t.cash_balance
ORDER BY total_unrealized_pnl DESC;
        """
    },

    "Option Chain Strike Skew & Open Interest (Window Function)": {
        "description": "Uses Window Functions (LAG, LEAD, DENSE_RANK) to analyze IV skew across strikes and identify max pain / high OI concentration zones.",
        "sql": """
WITH OptionChainData AS (
    SELECT 
        u.symbol AS underlying,
        c.contract_symbol,
        c.contract_type,
        c.strike_price,
        c.expiry_date,
        ms.last_traded_price,
        ms.implied_volatility * 100 AS iv_pct,
        ms.delta,
        ms.volume,
        ms.open_interest,
        -- Window function: rank strikes in ascending order
        DENSE_RANK() OVER (PARTITION BY u.symbol, c.contract_type ORDER BY c.strike_price ASC) as strike_rank,
        -- Window function: calculate IV skew vs adjacent lower strike
        ROUND((ms.implied_volatility - LAG(ms.implied_volatility, 1) OVER (
            PARTITION BY u.symbol, c.contract_type ORDER BY c.strike_price ASC
        )) * 100, 3) AS iv_skew_vs_prior_strike,
        -- Window function: market share of Open Interest
        ROUND(ms.open_interest * 100.0 / NULLIF(SUM(ms.open_interest) OVER (PARTITION BY u.symbol, c.contract_type), 0), 2) AS oi_share_pct
    FROM contracts c
    JOIN underlying_assets u ON c.underlying_id = u.underlying_id
    JOIN market_snapshots ms ON c.contract_id = ms.contract_id
    WHERE ms.snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
      AND c.contract_type IN ('CE', 'PE')
)
SELECT * 
FROM OptionChainData
ORDER BY strike_price ASC, contract_type ASC;
        """
    },

    "Daily Mark-to-Market (MTM) Variation Margin Ledger": {
        "description": "Multi-day settlement audit tracking MTM gains, losses, cumulative cash flows, and margin settlement status.",
        "sql": """
SELECT 
    s.settlement_date,
    t.account_number,
    t.name AS trader_name,
    c.contract_symbol,
    s.open_net_qty,
    s.prior_settlement_price,
    s.current_settlement_price,
    ROUND((s.current_settlement_price - s.prior_settlement_price), 4) AS price_delta,
    s.mtm_pnl,
    s.variation_margin,
    s.settlement_status,
    -- Window function: Running cumulative MTM for this trader
    ROUND(SUM(s.mtm_pnl) OVER (
        PARTITION BY s.trader_id 
        ORDER BY s.settlement_date ASC, s.settlement_id ASC
    ), 2) AS cumulative_trader_mtm
FROM daily_settlement_ledger s
JOIN traders t ON s.trader_id = t.trader_id
JOIN contracts c ON s.contract_id = c.contract_id
ORDER BY s.settlement_date DESC, s.mtm_pnl ASC;
        """
    },

    "Clearing House Margin Risk & Breach Detection": {
        "description": "Identifies traders approaching or breaching maintenance margin limits (Margin Call triggering).",
        "sql": """
WITH TraderMarginHealth AS (
    SELECT 
        t.trader_id,
        t.account_number,
        t.name,
        t.account_type,
        t.cash_balance,
        t.collateral_value,
        COALESCE(SUM(
            CASE 
                WHEN p.net_quantity > 0 THEN (COALESCE(ms.last_traded_price, p.avg_buy_price) - p.avg_buy_price) * p.net_quantity * c.contract_size
                WHEN p.net_quantity < 0 THEN (p.avg_sell_price - COALESCE(ms.last_traded_price, p.avg_sell_price)) * ABS(p.net_quantity) * c.contract_size
                ELSE 0 
            END
        ), 0) AS unrealized_pnl,
        -- Initial margin: 15% notional for Futures, premium for Options
        COALESCE(SUM(
            CASE 
                WHEN c.contract_type = 'FUT' THEN ABS(p.net_quantity) * c.contract_size * ms.last_traded_price * 0.15
                WHEN c.contract_type IN ('CE', 'PE') AND p.net_quantity < 0 THEN ABS(p.net_quantity) * c.contract_size * (ms.last_traded_price + (u.spot_price * 0.10))
                ELSE ABS(p.net_quantity) * c.contract_size * ms.last_traded_price
            END
        ), 0) AS initial_margin_req
    FROM traders t
    LEFT JOIN positions p ON t.trader_id = p.trader_id AND p.net_quantity != 0
    LEFT JOIN contracts c ON p.contract_id = c.contract_id
    LEFT JOIN underlying_assets u ON c.underlying_id = u.underlying_id
    LEFT JOIN (
        SELECT contract_id, last_traded_price FROM market_snapshots
        WHERE snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
    ) ms ON c.contract_id = ms.contract_id
    GROUP BY t.trader_id
)
SELECT 
    account_number,
    name,
    account_type,
    cash_balance,
    unrealized_pnl,
    (cash_balance + collateral_value + unrealized_pnl) AS total_equity,
    initial_margin_req,
    ROUND(initial_margin_req * 0.75, 2) AS maintenance_margin_req,
    CASE 
        WHEN (cash_balance + collateral_value + unrealized_pnl) <= 0 THEN 'INSOLVENT'
        WHEN (cash_balance + collateral_value + unrealized_pnl) < (initial_margin_req * 0.75) THEN 'MARGIN_CALL'
        WHEN (cash_balance + collateral_value + unrealized_pnl) < initial_margin_req THEN 'WARNING'
        ELSE 'SAFE'
    END AS risk_status,
    ROUND(
        CASE 
            WHEN initial_margin_req > 0 
            THEN (initial_margin_req * 100.0) / NULLIF(cash_balance + collateral_value + unrealized_pnl, 0)
            ELSE 0 
        END, 2
    ) AS margin_utilization_pct
FROM TraderMarginHealth
ORDER BY margin_utilization_pct DESC;
        """
    },

    "Top Traded Contracts by Volume & Liquidity": {
        "description": "Ranks contracts by trading activity, turnover, and open interest growth.",
        "sql": """
SELECT 
    c.contract_symbol,
    u.symbol AS underlying,
    c.contract_type,
    c.strike_price,
    c.expiry_date,
    ms.last_traded_price,
    ms.volume,
    ms.open_interest,
    ROUND(ms.last_traded_price * ms.volume * c.contract_size, 2) AS turnover_nominal,
    ROUND(ms.implied_volatility * 100, 2) AS iv_pct,
    COUNT(t.trade_id) AS total_trades_executed
FROM contracts c
JOIN underlying_assets u ON c.underlying_id = u.underlying_id
LEFT JOIN market_snapshots ms ON c.contract_id = ms.contract_id
    AND ms.snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
LEFT JOIN trades t ON c.contract_id = t.contract_id
GROUP BY c.contract_id
ORDER BY ms.volume DESC, turnover_nominal DESC;
        """
    }
}
