USE fno_tae2_db;

-- Store the old and new close price whenever a data4 row changes.
CREATE TABLE IF NOT EXISTS data4_audit (
    audit_id INT AUTO_INCREMENT PRIMARY KEY,
    data4_id INT NOT NULL,
    old_close_price DECIMAL(18, 4) NOT NULL,
    new_close_price DECIMAL(18, 4) NOT NULL,
    changed_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
);

DROP TRIGGER IF EXISTS trg_data4_price_audit;
DELIMITER //
-- MySQL triggers execute automatically after an UPDATE on data4.
CREATE TRIGGER trg_data4_price_audit
AFTER UPDATE ON data4
FOR EACH ROW
BEGIN
    IF OLD.close_price <> NEW.close_price THEN
        INSERT INTO data4_audit (data4_id, old_close_price, new_close_price)
        VALUES (NEW.data4_id, OLD.close_price, NEW.close_price);
    END IF;
END//
DELIMITER ;

-- Test: update the first available row, then display the generated audit record.
UPDATE data4
SET close_price = close_price + 0.01
ORDER BY data4_id
LIMIT 1;

SELECT * FROM data4_audit ORDER BY audit_id DESC;