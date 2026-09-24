USE fno_tae2_db;

-- Additional indexes for derivative contract filtering and reporting.
-- The primary, unique, and existing indexes are defined in schema.sql.

SET @index_exists = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'data3'
      AND index_name = 'idx_data3_instrument_symbol'
);
SET @sql = IF(
    @index_exists = 0,
    'CREATE INDEX idx_data3_instrument_symbol ON data3 (instrument, symbol)',
    'SELECT 1'
);
PREPARE create_index FROM @sql;
EXECUTE create_index;
DEALLOCATE PREPARE create_index;

SET @index_exists = (
    SELECT COUNT(*)
    FROM information_schema.statistics
    WHERE table_schema = DATABASE()
      AND table_name = 'data3'
      AND index_name = 'idx_data3_expiry_date'
);
SET @sql = IF(
    @index_exists = 0,
    'CREATE INDEX idx_data3_expiry_date ON data3 (expiry_date)',
    'SELECT 1'
);
PREPARE create_index FROM @sql;
EXECUTE create_index;
DEALLOCATE PREPARE create_index;
