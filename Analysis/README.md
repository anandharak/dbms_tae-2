# Futures & Options Trading, Volatility and Settlement Management Database System

A comprehensive, institutional-grade Relational Database Management System (DBMS) platform for **Futures & Options (F&O) Derivatives Trading**, **Black-Scholes Volatility & Greeks Modeling**, and **Clearing House Settlement Management (Daily Mark-to-Market & Margining)**.

Featuring a dedicated **Dataset Ingestion Mode** that ingests custom CSV/Excel option chains and trade books directly into normalized relational DBMS tables with ACID transaction guarantees.

---

## 🚀 Key Features

### 1. 📂 Dedicated Dataset Ingestion & DBMS Mode
- **Custom CSV/Excel Upload**: Upload external option chains, market ticks, or trade logs.
- **Smart Column Synonym Mapper**: Automatically identifies `Strike`, `Underlying`, `Expiry`, `Option Type`, `LTP`, `IV`, `OI`, `Volume`, and `Lot Size`.
- **Quantitative Enrichment**: Automatically computes theoretical BSM option prices, Implied Volatility (IV), and Greeks ($\Delta, \Gamma, \Theta, \mathcal{V}, \rho$) for missing records during ingestion.
- **ACID Transaction Execution**: Validates data types and inserts records into normalized relational tables with full rollback on error.
- **Preset Market Datasets**: Pre-built NIFTY 50 and BANKNIFTY option chains ready for 1-click testing.

### 2. 🗄️ Relational DBMS Architecture (3NF SQLite Engine)
- **Master Entities**:
  - `underlying_assets`: Spot prices, lot sizes, tick sizes, asset classes.
  - `contracts`: Derivative contract specifications (Futures, CE Call Options, PE Put Options, strikes, expiries).
  - `traders`: Clearing accounts, account types (Retail, Prop, Institutional, Market Maker), cash and collateral.
- **Transactional Tables**:
  - `orders`: Order book records (Limit, Market, Stop Loss).
  - `trades`: Matched trade execution records.
  - `positions`: Real-time aggregated portfolio book.
- **Automated Database Triggers**:
  - `trg_trade_buyer_position`: Auto-calculates buyer average price, net quantity, and cash deduction upon trade insert.
  - `trg_trade_seller_position`: Auto-calculates seller average price, net short exposure, and cash credit.
- **SQL Views**:
  - `vw_open_positions`: Real-time portfolio book with current LTP, Greeks, and unrealized P&L.
  - `vw_portfolio_greeks`: Net Delta, Gamma, Theta, Vega aggregated per trader.
  - `vw_settlement_summary`: Daily MTM variation margin rollups.

### 3. 📈 Volatility & Greeks Lab
- **Black-Scholes-Merton Engine**: Vectorized theoretical pricing for European/American options.
- **Analytical Greeks**: Delta, Gamma, Vega (per 1% vol), Theta (daily decay), Rho.
- **Newton-Raphson IV Solver**: Inverts market option prices to determine exact Implied Volatility with bisection fallback.
- **Interactive 3D Volatility Surface**: Real-time Plotly 3D meshgrid across $(Strike \times DTE \times IV)$.
- **Volatility Smile & Skew Analysis**: Strike-wise IV smile curves comparing Call and Put skew.
- **Greek Sensitivity Profiles**: Visual risk ladders against underlying spot price shifts.

### 4. ⚖️ Settlement & Margin Clearing Engine
- **Daily Mark-to-Market (MTM) Settlement**:
  - Computes daily price delta: $(P_t - P_{t-1}) \times Net\_Quantity \times Contract\_Size$.
  - Generates Variation Margin cash flows and updates `daily_settlement_ledger`.
- **Clearing House Margin Risk Ledger**:
  - SPAN-style Initial Margin calculation (12.5% notional for Futures, premium + exposure for short options).
  - Maintenance Margin threshold monitoring (75% of Initial Margin).
  - Automated **Margin Call** breach detection and shortfall alerts.
- **Final Expiry Cash Settlement**:
  - Exercises In-the-Money (ITM) options vs Out-of-the-Money expiration.
  - Credits/debits final cash payoffs and closes out positions to realized P&L.

### 5. 💻 DBMS Workbench & SQL Console
- **Interactive SQL Console**: Run arbitrary SQL (`SELECT`, `INSERT`, `UPDATE`, `EXPLAIN`).
- **Institutional Query Library**: Pre-built queries using CTEs, Window functions (`LAG`, `LEAD`, `DENSE_RANK`), and risk aggregations.
- **Schema & Query Plan Explorer**: Detailed table schemas, column metadata, and SQLite execution plans.

---

## 🛠️ Directory Structure

```
├── app.py                         # Institutional Streamlit terminal application
├── run.bat                        # 1-Click launcher script
├── database/
│   ├── schema.sql                 # Complete 3NF DDL (Tables, Foreign Keys, Triggers, Views, Indexes)
│   ├── db_manager.py              # SQLite connection manager, query executor, schema introspection
│   ├── queries.py                 # Institutional SQL query library
│   └── seed_full_database.py      # Database populator script
├── analytics/
│   ├── black_scholes.py           # BSM pricing, analytical Greeks, Newton-Raphson IV solver
│   ├── volatility_models.py       # HV estimators, 3D Volatility Surface generator, smile fitting
│   └── settlement_engine.py       # Daily MTM settlement, margin calculator, expiry cash settlement
├── ingestion/
│   ├── dataset_parser.py          # Smart column mapper, validator, relational bulk loader
│   └── sample_data_generator.py   # Generates realistic synthetic option chains and trade books
└── data/
    ├── fno_settlement.db          # Active SQLite relational database
    ├── option_chain_nifty.csv     # NIFTY 50 option chain sample dataset
    ├── option_chain_banknifty.csv # BANKNIFTY option chain sample dataset
    └── sample_trade_book.csv      # Sample trade execution book
```

---

## 🚀 How to Run

### Method 1: Using the Launcher Script
Double-click or run:
```bash
run.bat
```

### Method 2: Direct Command Line
```bash
streamlit run app.py
```
Open your browser at `http://localhost:8501`.
