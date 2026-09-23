USE fno_tae2_db;

-- View 1: reusable reporting layer for daily volatility analysis.
CREATE OR REPLACE VIEW vw_volatility_report AS
SELECT d1.trade_date, d1.symbol,
       d1.underlying_close, d1.futures_close,
       d2.current_underlying_daily_volatility,
       d2.current_futures_daily_volatility,
       d2.applicable_daily_volatility,
       d2.applicable_annualised_volatility
FROM data1 AS d1
INNER JOIN data2 AS d2 ON d2.data1_id = d1.data1_id;

-- View 2: reusable reporting layer for derivative activity and prices.
CREATE OR REPLACE VIEW vw_derivative_summary AS
SELECT d3.symbol, d3.instrument,
       COUNT(*) AS contract_count,
       SUM(d3.trade_value) AS total_trade_value,
       SUM(d3.trade_quantity) AS total_trade_quantity,
       AVG(d4.close_price) AS average_close_price,
       MAX(d4.high_price) AS highest_price
FROM data3 AS d3
INNER JOIN data4 AS d4 ON d4.data3_id = d3.data3_id
GROUP BY d3.symbol, d3.instrument;

-- Query both views to demonstrate their reporting output.
SELECT * FROM vw_volatility_report
ORDER BY applicable_annualised_volatility DESC;

SELECT * FROM vw_derivative_summary
ORDER BY total_trade_value DESC;