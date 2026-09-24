USE fno_tae2_db;

-- Inner join: return only volatility rows that have matching calculated metrics.
SELECT d1.trade_date, d1.symbol, d1.underlying_close,
       d2.applicable_daily_volatility, d2.applicable_annualised_volatility
FROM data1 AS d1
INNER JOIN data2 AS d2 ON d2.data1_id = d1.data1_id
ORDER BY d1.trade_date, d1.symbol;

-- Inner join: combine contract statistics with OHLC prices and keep high-value trades.
SELECT d3.instrument, d3.symbol, d3.expiry_date,
       d4.open_price, d4.high_price, d4.low_price, d4.close_price,
       d3.trade_value
FROM data3 AS d3
INNER JOIN data4 AS d4 ON d4.data3_id = d3.data3_id
WHERE d3.trade_value > 1000000000
ORDER BY d3.trade_value DESC;

-- Left outer join: retain every data1 price row, even if data2 has no matching row.
SELECT d1.symbol, d1.trade_date,
       COALESCE(d2.applicable_annualised_volatility, 0) AS annualised_volatility
FROM data1 AS d1
LEFT JOIN data2 AS d2 ON d2.data1_id = d1.data1_id
ORDER BY annualised_volatility DESC;

-- Right outer join: retain every data4 price row while looking up its data3 contract.
SELECT d3.symbol, d3.expiry_date, d4.close_price, d3.number_of_trades
FROM data3 AS d3
RIGHT JOIN data4 AS d4 ON d4.data3_id = d3.data3_id;

-- Self join: compare an earlier and later expiry for the same derivative symbol.
SELECT first_contract.symbol,
       first_contract.expiry_date AS first_expiry,
       second_contract.expiry_date AS second_expiry,
       first_price.close_price AS first_close,
       second_price.close_price AS second_close,
       second_price.close_price - first_price.close_price AS price_difference
FROM data3 AS first_contract
JOIN data4 AS first_price ON first_price.data3_id = first_contract.data3_id
JOIN data3 AS second_contract
  ON second_contract.symbol = first_contract.symbol
 AND second_contract.expiry_date > first_contract.expiry_date
JOIN data4 AS second_price ON second_price.data3_id = second_contract.data3_id
ORDER BY first_contract.symbol, first_contract.expiry_date, second_contract.expiry_date;

-- MySQL has no FULL OUTER JOIN; combine LEFT and RIGHT JOIN results with UNION.
SELECT d1.symbol AS volatility_symbol, d3.symbol AS derivative_symbol,
       d1.trade_date, d3.expiry_date
FROM data1 AS d1
LEFT JOIN data3 AS d3 ON d3.symbol = d1.symbol
UNION
SELECT d1.symbol AS volatility_symbol, d3.symbol AS derivative_symbol,
       d1.trade_date, d3.expiry_date
FROM data1 AS d1
RIGHT JOIN data3 AS d3 ON d3.symbol = d1.symbol;

-- Aggregate join: calculate per-symbol totals and filter them with HAVING.
SELECT d3.symbol, COUNT(*) AS contracts,
       SUM(d3.trade_value) AS total_trade_value,
       AVG(d4.close_price) AS average_close_price
FROM data3 AS d3
JOIN data4 AS d4 ON d4.data3_id = d3.data3_id
GROUP BY d3.symbol
HAVING SUM(d3.trade_value) > 1000000000
ORDER BY total_trade_value DESC;