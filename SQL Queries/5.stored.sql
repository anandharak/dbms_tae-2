USE fno_tae2_db;

-- Recreate the procedure so the script can be rerun during the live demo.
DROP PROCEDURE IF EXISTS sp_symbol_report;
DELIMITER //
-- The input parameter restricts the report to one derivative symbol.
CREATE PROCEDURE sp_symbol_report(IN p_symbol VARCHAR(30))
BEGIN
    -- Join contract statistics and prices, then return one aggregate report row.
    SELECT d3.symbol,
           COUNT(*) AS contract_count,
           MIN(d3.expiry_date) AS first_expiry,
           MAX(d3.expiry_date) AS last_expiry,
           SUM(d3.trade_value) AS total_trade_value,
           AVG(d4.close_price) AS average_close_price
    FROM data3 AS d3
    INNER JOIN data4 AS d4 ON d4.data3_id = d3.data3_id
    WHERE d3.symbol = p_symbol
    GROUP BY d3.symbol;
END//
DELIMITER ;

-- Example executions for two symbols in the supplied dataset.
CALL sp_symbol_report('BANKNIFTY');
CALL sp_symbol_report('RELIANCE');