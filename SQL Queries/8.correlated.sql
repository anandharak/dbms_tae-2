USE fno_tae2_db;

-- Correlation rule: the inner query calculates the average for the current symbol.
SELECT d3.symbol, d3.expiry_date, d3.trade_value
FROM data3 AS d3
WHERE d3.trade_value > (
    SELECT AVG(other_contract.trade_value)
    FROM data3 AS other_contract
    WHERE other_contract.symbol = d3.symbol
)
ORDER BY d3.symbol, d3.trade_value DESC;

-- Correlation rule: compare each row with the average annualised volatility for its date.
SELECT d1.trade_date, d1.symbol, d2.applicable_annualised_volatility
FROM data1 AS d1
JOIN data2 AS d2 ON d2.data1_id = d1.data1_id
WHERE d2.applicable_annualised_volatility > (
    SELECT AVG(other_metrics.applicable_annualised_volatility)
    FROM data1 AS other_date
    JOIN data2 AS other_metrics ON other_metrics.data1_id = other_date.data1_id
    WHERE other_date.trade_date = d1.trade_date
)
ORDER BY d1.trade_date, d2.applicable_annualised_volatility DESC;

-- Correlation rule: return the contract whose expiry equals that symbol's maximum expiry.
SELECT d3.symbol, d3.expiry_date, d4.close_price
FROM data3 AS d3
JOIN data4 AS d4 ON d4.data3_id = d3.data3_id
WHERE d3.expiry_date = (
    SELECT MAX(other_contract.expiry_date)
    FROM data3 AS other_contract
    WHERE other_contract.symbol = d3.symbol
)
ORDER BY d3.symbol;