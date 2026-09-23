Title:Futures & Options Trading, Volatility and Settlement 
Management Database System

# NSE F&O Volatility and Derivatives Database

This project implements a MySQL database for NSE futures and options (F&O) market data. It combines two supplied datasets:

1. `F&O Volatility.csv`, containing daily underlying and futures prices plus volatility calculations.
2. `F&O Vola_tility.csv`, containing derivative instrument, expiry, trading, and OHLC price information.

The complete workflow is: clean the source files, design the ER model, convert the model into relational tables, load the data, and demonstrate queries, views, indexes, a stored procedure, and an audit trigger.

## Requirements

- MySQL 8.x and MySQL Workbench or the MySQL command-line client
- Python 3.9 or newer
- The supplied files in `Raw Datasets/` and `Cleaned Datasets/`

## Project Structure

| File or folder | Purpose |
|---|---|
| `schema.sql` | Creates `fno_tae2_db`, the four base tables, keys, constraints, indexes, and DQL/DML/DCL/TCL examples. |
| `python_cleaning_script.py` | Cleans the raw derivatives CSV and produces a cleaning report. |
| `populate.py` | Reads both cleaned CSV files and generates `data.sql`. |
| `data.sql` | Generated data-loading script for `data1`, `data2`, `data3`, and `data4`. |
| `indexing.sql` | Adds optional indexes for derivative searches. |
| `views.sql` | Creates reusable volatility and derivative summary views. |
| `stored.sql` | Creates and demonstrates the `sp_symbol_report` stored procedure. |
| `trigger.sql` | Creates an audit table and trigger for derivative close-price changes. |
| `join.sql` | Demonstrates inner, outer, self, union-based full-outer, and aggregate joins. |
| `correlated.sql` | Demonstrates correlated subqueries for symbol, date, and expiry analysis. |
| `Raw Datasets/` | Original NSE CSV files. |
| `Cleaned Datasets/` | Validated CSV files consumed by `populate.py`. |
| `SQL Queries/` | Folder for additional SQL analysis queries. |

## How the ER Diagram Is Achieved

### 1. Identify the business entities

The ER diagram is first created from the real business objects in the F&O domain:

| ER entity | Meaning in this project | Implemented table/columns |
|---|---|---|
| `Security` | The traded symbol, such as an index or company | `data1.symbol` and `data3.symbol` |
| `Trading_Date` | The date on which market activity is recorded | `data1.trade_date` |
| `Market_Record` | One daily underlying/futures market observation | One row in `data1` |
| `Price_Details` | OHLC prices for a derivative contract | One row in `data4` |
| `Instrument` | The derivative type, such as futures or options | `data3.instrument` |
| `Expiry` | The contract expiry date | `data3.expiry_date` |
| `Volatility` | Returns and daily/annualised volatility measures | One row in `data2` |
| `Risk_Assessment` | A conceptual use of volatility for risk analysis | Derived from `data2` volatility columns and reporting queries |

The diagram is a conceptual model. The implementation uses four practical tables because the two source datasets already have two natural data families: volatility observations and derivative contracts.

### 2. Convert entities into relational tables

Each entity becomes a table or a clearly defined table component. Every table receives a primary key so that each record can be uniquely identified:

- `data1(data1_id, trade_date, symbol, underlying_close, underlying_previous_close, futures_close, futures_previous_close)` stores the daily market record.
- `data2(data2_id, data1_id, ...)` stores volatility calculations for the corresponding `data1` record.
- `data3(data3_id, instrument, symbol, expiry_date, open_interest, trade_value, trade_quantity, number_of_contracts, number_of_trades)` stores derivative contracts and trading statistics.
- `data4(data4_id, data3_id, open_price, high_price, low_price, close_price)` stores derivative OHLC prices.

This is how the ER diagram becomes executable SQL: entity attributes become columns, entity identifiers become primary keys, and relationships become foreign keys.

### 3. Implement the relationships and cardinalities

The important relationships in the submitted ER diagram are implemented as follows:

| Relationship | SQL implementation | Cardinality |
|---|---|---|
| Market record to volatility | `data2.data1_id` references `data1.data1_id` | One market record to zero or one volatility row; each volatility row belongs to exactly one market record |
| Derivative contract to price details | `data4.data3_id` references `data3.data3_id` | One contract to zero or one OHLC row; each OHLC row belongs to exactly one contract |
| Security to market records | `data1.symbol` identifies the security represented by each market record | One security can have many daily records |
| Security to derivative contracts | `data3.symbol` identifies the security represented by each contract | One security can have many contracts |
| Instrument to derivative contracts | `data3.instrument` records the instrument type | One instrument type can have many contracts |
| Expiry to derivative contracts | `data3.expiry_date` records the expiry value | One expiry date can apply to many contracts |

The one-to-one relationships are enforced with unique constraints:

```sql
CONSTRAINT fk_data2_data1 FOREIGN KEY (data1_id) REFERENCES data1(data1_id),
UNIQUE KEY uq_data2_data1 (data1_id)

CONSTRAINT fk_data4_data3 FOREIGN KEY (data3_id) REFERENCES data3(data3_id),
UNIQUE KEY uq_data4_data3 (data3_id)
```

`ON DELETE CASCADE` and `ON UPDATE CASCADE` keep dependent volatility or price rows consistent when their parent row changes. The foreign keys also ensure that a child row cannot refer to a non-existent market record or contract.

### 4. Apply normalization

The uploaded CSV files are flat files, so they contain groups of values that belong to different subjects. The conversion follows the normalisation plan from the report:

- **UNF:** The raw rows contain prices, volatility, contract details, and trading statistics together.
- **1NF:** Values are made atomic; each column contains one value and repeating groups are removed.
- **2NF:** Market observations, volatility calculations, derivative contracts, and OHLC details are separated so non-key attributes depend on the correct key.
- **3NF:** Contract price details do not repeat contract trading attributes, and volatility values do not repeat market price attributes.
- **BCNF intention:** The identifying key for each implemented relation determines the attributes stored in that relation.

The result reduces duplication, improves update consistency, and makes joins possible between related subjects.

### 5. Add integrity constraints

The schema protects the ER model with:

- primary keys on all four base tables;
- foreign keys for dependent data;
- unique `(trade_date, symbol)` values in `data1`;
- `NOT NULL` constraints for required identifiers and dates;
- checks preventing negative quantities, values, interest, and volatility;
- OHLC checks such as `high_price >= open_price` and `close_price` between the low and high prices.

## Data Preparation

Run the following command from the project directory to clean the raw derivative file:

```powershell
python .\python_cleaning_script.py ".\Raw Datasets\F&O Vola_tility Raw.csv" -o ".\Cleaned Datasets\F&O Vola_tility.csv"
```

The cleaning script trims headers and values, normalizes missing-value tokens, converts `EXP_DATE` from `DD/MM/YYYY` to `YYYY-MM-DD`, normalizes numbers, removes rows without `SYMBOL` or `EXP_DATE`, removes invalid OHLC rows and exact duplicates, and preserves genuinely missing market values as SQL `NULL`.

The cleaned volatility file must be available at `Cleaned Datasets/F&O Volatility.csv`, because `populate.py` reads that path directly.

## Generate and Load the Data

Generate the SQL inserts after both cleaned files are ready:

```powershell
python .\populate.py
```

The generator creates inserts in dependency order: `data1`, `data2`, `data3`, then `data4`. This order follows the ER relationships because child rows must be loaded after their parent rows. The generated script clears existing rows first, so run it only when replacing the current dataset is intended.

Run the SQL scripts in this order:

```text
1. schema.sql       -- create database, tables, keys, and constraints
2. data.sql         -- load the cleaned data
3. indexing.sql     -- add optional performance indexes
4. views.sql        -- create reporting views
5. stored.sql       -- create the stored procedure
6. trigger.sql      -- create the audit trigger
7. join.sql         -- run relationship queries
8. correlated.sql   -- run analytical subqueries
```

Example command-line execution:

```powershell
mysql -u your_username -p < schema.sql
mysql -u your_username -p fno_tae2_db < data.sql
mysql -u your_username -p fno_tae2_db < indexing.sql
mysql -u your_username -p fno_tae2_db < views.sql
mysql -u your_username -p fno_tae2_db < stored.sql
mysql -u your_username -p fno_tae2_db < trigger.sql
mysql -u your_username -p fno_tae2_db < join.sql
mysql -u your_username -p fno_tae2_db < correlated.sql
```

## Reports and Database Features

`views.sql` creates two reusable reports:

- `vw_volatility_report` joins `data1` and `data2` to show market prices and volatility.
- `vw_derivative_summary` joins `data3` and `data4` and aggregates contract count, trade value, quantity, average close, and highest price by symbol and instrument.

`stored.sql` creates `sp_symbol_report(symbol)`, which returns contract count, expiry range, total trade value, and average close price:

```sql
CALL sp_symbol_report('BANKNIFTY');
CALL sp_symbol_report('RELIANCE');
```

`trigger.sql` creates `trg_data4_price_audit`. Whenever a derivative `close_price` changes, the trigger stores the old price, new price, record identifier, and change time in `data4_audit`. The demonstration update in that file intentionally changes the first row by `0.01`; remove or comment it out for a non-demonstration run.

`indexing.sql` adds indexes for `(instrument, symbol)` and `expiry_date`. The join and correlated-query scripts demonstrate how the foreign-key and business-key relationships support analysis.

## Verification Checklist

After execution, verify the ER implementation with:

```sql
USE fno_tae2_db;

SHOW TABLES;
SELECT COUNT(*) FROM data1;
SELECT COUNT(*) FROM data2;
SELECT COUNT(*) FROM data3;
SELECT COUNT(*) FROM data4;

SELECT d1.data1_id, d1.symbol, d2.applicable_annualised_volatility
FROM data1 AS d1
JOIN data2 AS d2 ON d2.data1_id = d1.data1_id
LIMIT 10;

SELECT d3.data3_id, d3.symbol, d4.open_price, d4.close_price
FROM data3 AS d3
JOIN data4 AS d4 ON d4.data3_id = d3.data3_id
LIMIT 10;
```

These checks confirm that the tables exist, rows were loaded, and both one-to-one ER relationships work through their foreign keys.

## Important Notes

- The database name is `fno_tae2_db`.
- `schema.sql` drops and recreates that database, deleting any existing database with the same name.
- `data.sql` truncates the four base tables before inserting generated data.
- The SQL uses MySQL features such as `DELIMITER`, `FOREIGN_KEY_CHECKS`, `CREATE OR REPLACE VIEW`, and `GRANT`.
- Use a MySQL connection rather than a SQL Server connection.
- Missing values from the source datasets are preserved as SQL `NULL` where the schema allows them.
