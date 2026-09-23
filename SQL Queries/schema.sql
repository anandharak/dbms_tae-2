-- TAE 2 MySQL schema for the two supplied NSE datasets.
-- data1/data2 store volatility prices and calculated volatility measures.
-- data3/data4 store derivative contract statistics and OHLC prices.
DROP DATABASE IF EXISTS fno_tae2_db;
CREATE DATABASE fno_tae2_db;
USE fno_tae2_db;

-- Volatility source: one row per symbol and trading date.
CREATE TABLE data1 (
    data1_id INT PRIMARY KEY,
    trade_date DATE NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    underlying_close DECIMAL(18, 6),
    underlying_previous_close DECIMAL(18, 6),
    futures_close DECIMAL(18, 6),
    futures_previous_close DECIMAL(18, 6),
    UNIQUE KEY uq_data1_date_symbol (trade_date, symbol)
);

-- Volatility calculations linked one-to-one with the matching data1 row.
CREATE TABLE data2 (
    data2_id INT PRIMARY KEY,
    data1_id INT NOT NULL,
    underlying_log_return DECIMAL(18, 10),
    previous_underlying_volatility DECIMAL(18, 10),
    current_underlying_daily_volatility DECIMAL(18, 10),
    underlying_annualised_volatility DECIMAL(18, 10),
    futures_log_return DECIMAL(18, 10),
    previous_futures_volatility DECIMAL(18, 10),
    current_futures_daily_volatility DECIMAL(18, 10),
    futures_annualised_volatility DECIMAL(18, 10),
    applicable_daily_volatility DECIMAL(18, 10),
    applicable_annualised_volatility DECIMAL(18, 10),
    CONSTRAINT fk_data2_data1 FOREIGN KEY (data1_id) REFERENCES data1(data1_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY uq_data2_data1 (data1_id),
    CHECK (applicable_daily_volatility IS NULL OR applicable_daily_volatility >= 0),
    CHECK (applicable_annualised_volatility IS NULL OR applicable_annualised_volatility >= 0)
);

-- Derivatives source: instrument, symbol, expiry, volume and trade statistics.
CREATE TABLE data3 (
    data3_id INT PRIMARY KEY,
    instrument VARCHAR(12) NOT NULL,
    symbol VARCHAR(30) NOT NULL,
    expiry_date DATE NOT NULL,
    open_interest DECIMAL(20, 2) NOT NULL DEFAULT 0,
    trade_value DECIMAL(24, 2) NOT NULL DEFAULT 0,
    trade_quantity BIGINT NOT NULL DEFAULT 0,
    number_of_contracts BIGINT NOT NULL DEFAULT 0,
    number_of_trades BIGINT NOT NULL DEFAULT 0,
    CHECK (open_interest >= 0),
    CHECK (trade_value >= 0),
    CHECK (trade_quantity >= 0),
    CHECK (number_of_contracts >= 0),
    CHECK (number_of_trades >= 0),
    INDEX idx_data3_symbol_expiry (symbol, expiry_date),
    INDEX idx_data3_trade_value (trade_value)
);

-- Derivative OHLC prices linked one-to-one with the matching contract row.
CREATE TABLE data4 (
    data4_id INT PRIMARY KEY,
    data3_id INT NOT NULL,
    open_price DECIMAL(18, 4) NOT NULL,
    high_price DECIMAL(18, 4) NOT NULL,
    low_price DECIMAL(18, 4) NOT NULL,
    close_price DECIMAL(18, 4) NOT NULL,
    CONSTRAINT fk_data4_data3 FOREIGN KEY (data3_id) REFERENCES data3(data3_id)
        ON DELETE CASCADE ON UPDATE CASCADE,
    UNIQUE KEY uq_data4_data3 (data3_id),
    CHECK (open_price >= 0),
    CHECK (high_price >= open_price),
    CHECK (low_price <= open_price),
    CHECK (close_price BETWEEN low_price AND high_price)
);

-- Indexes support symbol/date searches and volatility filtering.
CREATE INDEX idx_data1_symbol_date ON data1 (symbol, trade_date);
CREATE INDEX idx_data2_annualised_volatility ON data2 (applicable_annualised_volatility);

-- ================================================================
-- DQL: Data Query Language
-- SELECT reads data without changing any table.
-- ================================================================
SELECT data1_id, trade_date, symbol, underlying_close, futures_close
FROM data1
ORDER BY trade_date, symbol
LIMIT 10;

SELECT symbol, applicable_annualised_volatility
FROM data1
JOIN data2 ON data2.data1_id = data1.data1_id
ORDER BY applicable_annualised_volatility DESC
LIMIT 10;

-- ================================================================
-- DML: Data Manipulation Language
-- A temporary table demonstrates INSERT, UPDATE and DELETE safely.
-- The imported data1-data4 tables are not modified by these examples.
-- ================================================================
DROP TEMPORARY TABLE IF EXISTS dml_demo;
CREATE TEMPORARY TABLE dml_demo (
    demo_id INT PRIMARY KEY,
    demo_text VARCHAR(50) NOT NULL,
    demo_value DECIMAL(10, 2) NOT NULL
);

INSERT INTO dml_demo (demo_id, demo_text, demo_value)
VALUES (1, 'DML demonstration row', 100.00);

UPDATE dml_demo
SET demo_value = 125.00
WHERE demo_id = 1;

DELETE FROM dml_demo
WHERE demo_id = 1;

-- ================================================================
-- DCL: Data Control Language
-- Grant read access to the account executing this Workbench script.
-- REVOKE is shown as a comment because revoking the current user's
-- access could interrupt the active Workbench session.
-- ================================================================
GRANT SELECT ON fno_tae2_db.* TO CURRENT_USER;
-- REVOKE SELECT ON fno_tae2_db.* FROM CURRENT_USER;

-- ================================================================
-- TCL: Transaction Control Language
-- Demonstrate SAVEPOINT, ROLLBACK TO SAVEPOINT and COMMIT safely.
-- ================================================================
START TRANSACTION;
INSERT INTO dml_demo (demo_id, demo_text, demo_value)
VALUES (2, 'TCL demonstration row', 200.00);
SAVEPOINT before_demo_update;
UPDATE dml_demo
SET demo_value = 250.00
WHERE demo_id = 2;
ROLLBACK TO SAVEPOINT before_demo_update;
COMMIT;

DROP TEMPORARY TABLE IF EXISTS dml_demo;