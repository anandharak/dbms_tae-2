"""
Futures & Options Trading, Volatility and Settlement Management Database System.
Comprehensive Relational DBMS application with Dataset Ingestion Mode,
Black-Scholes & Greeks Engine, MTM Settlement Ledger, and SQL Query Workbench.
"""

import os
import sys
import time
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import streamlit as st

# Configure page layout and title
st.set_page_config(
    page_title="F&O Trading, Volatility & Settlement DBMS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Ensure workspace root is in sys.path
WORKSPACE_DIR = os.path.dirname(os.path.abspath(__file__))
if WORKSPACE_DIR not in sys.path:
    sys.path.insert(0, WORKSPACE_DIR)

from database.db_manager import get_db
from database.queries import QUERIES
from analytics.black_scholes import calculate_option_price, calculate_greeks, calculate_implied_volatility
from analytics.volatility_models import generate_volatility_surface_mesh, fit_volatility_smile
from analytics.settlement_engine import SettlementEngine
from ingestion.dataset_parser import DatasetParser
from ingestion.sample_data_generator import generate_option_chain_csv, generate_sample_trade_book_csv

db = get_db()
settlement_engine = SettlementEngine(db)
parser = DatasetParser(db)

# ==============================================================================
# CUSTOM STYLING (BLOOMBERG TERMINAL / DARK NEON AESTHETICS)
# ==============================================================================
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600;700&family=Plus+Jakarta+Sans:wght@300;400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    code, pre, .stCodeBlock {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Top Header Bar */
    .terminal-header {
        background: linear-gradient(135deg, #0d1117 0%, #161b22 100%);
        border: 1px solid #30363d;
        border-radius: 12px;
        padding: 1.2rem 1.8rem;
        margin-bottom: 1.5rem;
        display: flex;
        justify-content: space-between;
        align-items: center;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
    }
    .terminal-title {
        color: #f0f6fc;
        font-size: 1.6rem;
        font-weight: 700;
        letter-spacing: -0.5px;
        margin: 0;
        display: flex;
        align-items: center;
        gap: 12px;
    }
    .terminal-badge {
        background: rgba(0, 242, 254, 0.12);
        color: #00f2fe;
        border: 1px solid rgba(0, 242, 254, 0.3);
        border-radius: 20px;
        padding: 4px 12px;
        font-size: 0.8rem;
        font-weight: 600;
        letter-spacing: 0.5px;
    }
    
    /* Metric Cards */
    .metric-card {
        background: #161b22;
        border: 1px solid #30363d;
        border-radius: 10px;
        padding: 1rem 1.2rem;
        box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
        transition: transform 0.2s ease, border-color 0.2s ease;
    }
    .metric-card:hover {
        border-color: #58a6ff;
        transform: translateY(-2px);
    }
    .metric-title {
        color: #8b949e;
        font-size: 0.8rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
        margin-bottom: 0.3rem;
    }
    .metric-val {
        color: #f0f6fc;
        font-size: 1.5rem;
        font-weight: 700;
        font-family: 'JetBrains Mono', monospace;
    }
    .metric-sub {
        font-size: 0.75rem;
        color: #58a6ff;
        margin-top: 0.2rem;
    }
    
    /* Status Badges */
    .badge-long {
        background: rgba(0, 245, 160, 0.15);
        color: #00f5a0;
        padding: 2px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .badge-short {
        background: rgba(255, 75, 75, 0.15);
        color: #ff4b4b;
        padding: 2px 8px;
        border-radius: 6px;
        font-weight: 600;
        font-size: 0.75rem;
    }
    .badge-margin-call {
        background: rgba(255, 75, 75, 0.25);
        color: #ff4b4b;
        border: 1px solid #ff4b4b;
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 700;
    }
    .badge-safe {
        background: rgba(0, 245, 160, 0.2);
        color: #00f5a0;
        border: 1px solid #00f5a0;
        padding: 3px 10px;
        border-radius: 6px;
        font-weight: 600;
    }
    
    /* Table Styling */
    .dataframe {
        font-family: 'JetBrains Mono', monospace !important;
        font-size: 0.85rem !important;
    }
</style>
""", unsafe_allow_html=True)

# ==============================================================================
# SIDEBAR NAVIGATION & SYSTEM STATUS
# ==============================================================================
with st.sidebar:
    st.markdown("### ⚡ **F&O DBMS Engine**")
    st.markdown("`Database: SQLite 3NF Normalized`")
    st.markdown("`ACID Transactions: Active`")
    st.markdown("`PRAGMA foreign_keys: ON`")
    st.markdown("---")
    
    # Active underlying selector for context
    try:
        underlyings_df = db.execute_query("SELECT symbol, spot_price FROM underlying_assets;")
        underlying_options = underlyings_df["symbol"].tolist() if not underlyings_df.empty else ["NIFTY"]
    except Exception:
        underlying_options = ["NIFTY"]
        
    selected_underlying = st.selectbox("🌐 Focus Underlying Asset", underlying_options, index=0)
    
    st.markdown("---")
    st.markdown("#### ⚡ Quick Actions")
    if st.button("🔄 Refresh Database Status", use_container_width=True):
        st.rerun()

    if st.button("🧹 Clear & Re-seed Sample Data", use_container_width=True):
        from database.seed_full_database import seed_all
        with st.spinner("Re-seeding database schema and initial data..."):
            db.init_database(force_recreate=True)
            seed_all()
        st.success("Database reset and seeded!")
        st.rerun()

    st.markdown("---")
    st.caption("Institutional Derivatives Clearing & Risk System v2.4")

# ==============================================================================
# HEADER BANNER
# ==============================================================================
st.markdown("""
<div class="terminal-header">
    <div>
        <h1 class="terminal-title">
            <span>⚡ Futures & Options Trading, Volatility & Settlement DBMS</span>
        </h1>
        <div style="color: #8b949e; font-size: 0.85rem; margin-top: 4px;">
            High-Performance Relational Clearing House Engine • Black-Scholes Greeks • Daily Mark-to-Market Settlement
        </div>
    </div>
    <div>
        <span class="terminal-badge">DBMS MODE: ONLINE</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Main Application Tabs
tab_overview, tab_upload, tab_trading, tab_volatility, tab_settlement, tab_workbench = st.tabs([
    "📊 Executive Overview",
    "📂 Dataset Upload & DBMS Mode",
    "⚡ F&O Trading & Trade Book",
    "📈 Volatility & Greeks Lab",
    "⚖️ Settlement & Margin Clearing",
    "🗄️ DBMS Workbench & SQL Console"
])

# ==============================================================================
# TAB 1: EXECUTIVE OVERVIEW & DBMS METRICS
# ==============================================================================
with tab_overview:
    # Query summary metrics
    try:
        traders_count = db.execute_query("SELECT COUNT(*) AS c FROM traders;").iloc[0]["c"]
        contracts_count = db.execute_query("SELECT COUNT(*) AS c FROM contracts WHERE is_active = 1;").iloc[0]["c"]
        trades_count = db.execute_query("SELECT COUNT(*) AS c FROM trades;").iloc[0]["c"]
        open_pos_count = db.execute_query("SELECT COUNT(*) AS c FROM positions WHERE net_quantity != 0;").iloc[0]["c"]
        total_oi = db.execute_query("SELECT COALESCE(SUM(open_interest), 0) AS oi FROM market_snapshots WHERE snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id);").iloc[0]["oi"]
        
        # Spot price of selected underlying
        spot_res = db.execute_query("SELECT spot_price FROM underlying_assets WHERE symbol = ?;", (selected_underlying,))
        spot_val = spot_res.iloc[0]["spot_price"] if not spot_res.empty else 24250.0
    except Exception as e:
        traders_count, contracts_count, trades_count, open_pos_count, total_oi, spot_val = 5, 102, 4, 4, 1250000, 24250.0

    # Top Metric KPI Cards
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">{selected_underlying} SPOT PRICE</div>
            <div class="metric-val">₹{spot_val:,.2f}</div>
            <div class="metric-sub">Underlying Reference</div>
        </div>
        """, unsafe_allow_html=True)
    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">ACTIVE CONTRACTS</div>
            <div class="metric-val">{contracts_count:,}</div>
            <div class="metric-sub">Futures & Options Catalog</div>
        </div>
        """, unsafe_allow_html=True)
    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">OPEN POSITIONS</div>
            <div class="metric-val">{open_pos_count:,}</div>
            <div class="metric-sub">Aggregated Portfolio Book</div>
        </div>
        """, unsafe_allow_html=True)
    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">MARKET OPEN INTEREST</div>
            <div class="metric-val">{total_oi:,.0f}</div>
            <div class="metric-sub">Total Contracts Outstanding</div>
        </div>
        """, unsafe_allow_html=True)
    with col5:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">EXECUTED TRADES</div>
            <div class="metric-val">{trades_count:,}</div>
            <div class="metric-sub">Audit Matched Records</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # Split View: Portfolio Greeks vs Top Traded Contracts
    col_left, col_right = st.columns([1.1, 1])
    
    with col_left:
        st.subheader("🌐 Portfolio Greeks & Exposure (DBMS View)")
        st.caption("Aggregated institutional exposure queried from view `vw_portfolio_greeks`")
        try:
            greeks_df = db.execute_query("SELECT * FROM vw_portfolio_greeks;")
            if not greeks_df.empty:
                st.dataframe(
                    greeks_df.style.format({
                        "portfolio_delta": "{:+.4f}",
                        "portfolio_gamma": "{:.6f}",
                        "portfolio_theta": "₹{:,.2f}",
                        "portfolio_vega": "₹{:,.2f}"
                    }),
                    use_container_width=True,
                    height=260
                )
            else:
                st.info("No open positions found. Place trades in the Trading tab or run sample seeding.")
        except Exception as e:
            st.error(f"Error querying view: {e}")

    with col_right:
        st.subheader("🔥 Top Contracts by Volume & Liquidity")
        st.caption("Queried from real-time snapshot tables joined with contracts")
        try:
            top_contracts = db.execute_query("""
                SELECT 
                    c.contract_symbol,
                    c.contract_type,
                    c.strike_price,
                    ms.last_traded_price AS ltp,
                    ms.volume,
                    ms.open_interest,
                    ROUND(ms.implied_volatility * 100, 1) AS iv_pct
                FROM contracts c
                JOIN market_snapshots ms ON c.contract_id = ms.contract_id
                WHERE ms.snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
                ORDER BY ms.volume DESC
                LIMIT 6;
            """)
            st.dataframe(top_contracts, use_container_width=True, height=260)
        except Exception as e:
            st.error(f"Error loading top contracts: {e}")

    # Relational Database Architecture Overview
    st.markdown("---")
    st.subheader("🗄️ Relational DBMS Architecture & Schema Integrity")
    st.markdown("""
    The system operates on an ACID-compliant relational schema structured in **Third Normal Form (3NF)**:
    - **Master Entities**: `underlying_assets` ➔ `contracts` ➔ `traders`
    - **Transactional Tables**: `orders` ➔ `trades` ➔ `positions` (Updated automatically via Database Triggers)
    - **Time-Series Feeds**: `market_snapshots` (Tick, LTP, IV, Delta, Gamma, Theta, Vega)
    - **Clearing Ledgers**: `daily_settlement_ledger` (Daily MTM Variation Margin) & `margin_ledger` (Initial & Maintenance Margins)
    """)

# ==============================================================================
# TAB 2: DATASET UPLOAD & DBMS MODE (CORE USER REQUIREMENT)
# ==============================================================================
with tab_upload:
    st.subheader("📂 Upload External Dataset & Ingest into Relational DBMS")
    st.markdown("""
    This mode allows you to upload **external Option Chain datasets, Trade execution books, or Settlement feeds** (CSV or Excel).
    The engine automatically inspects the column headers, performs type normalization, calculates missing BSM Greeks and IV, 
    and transactionally commits the data into the normalized relational DBMS tables.
    """)

    col_upload_left, col_upload_right = st.columns([1.2, 1])

    with col_upload_left:
        st.markdown("#### 1. Choose Data Source")
        source_mode = st.radio(
            "Select upload mechanism:",
            ["Upload Custom File (CSV / XLSX)", "Load Built-in Sample Datasets (Ready-to-Test)"],
            horizontal=True
        )

        uploaded_file = None
        df_to_ingest = None
        filename_label = ""

        if source_mode == "Upload Custom File (CSV / XLSX)":
            uploaded_file = st.file_uploader(
                "Drop your Option Chain or Derivatives CSV/Excel file here",
                type=["csv", "xlsx", "xls"],
                help="Columns can have any standard names (Strike, Expiry, Option Type, LTP, IV, OI, etc.). The system auto-detects synonyms."
            )
            if uploaded_file is not None:
                try:
                    if uploaded_file.name.endswith(".csv"):
                        df_to_ingest = pd.read_csv(uploaded_file)
                    else:
                        df_to_ingest = pd.read_excel(uploaded_file)
                    filename_label = uploaded_file.name
                except Exception as e:
                    st.error(f"Error reading file: {e}")

        else:
            sample_choice = st.selectbox(
                "Choose pre-built market dataset:",
                [
                    "NIFTY 50 Weekly Option Chain (51 Strikes, CE & PE)",
                    "BANKNIFTY Weekly Option Chain (31 Strikes, CE & PE)",
                    "Institutional Trade Book Feed (Simulated Executions)"
                ]
            )
            
            data_dir = os.path.join(WORKSPACE_DIR, "data")
            if "NIFTY" in sample_choice:
                sample_file = os.path.join(data_dir, "option_chain_nifty.csv")
                if not os.path.exists(sample_file):
                    sample_file = generate_option_chain_csv("NIFTY", 24250.0, 7, 50)
            elif "BANKNIFTY" in sample_choice:
                sample_file = os.path.join(data_dir, "option_chain_banknifty.csv")
                if not os.path.exists(sample_file):
                    sample_file = generate_option_chain_csv("BANKNIFTY", 52100.0, 7, 15)
            else:
                sample_file = os.path.join(data_dir, "sample_trade_book.csv")
                if not os.path.exists(sample_file):
                    sample_file = generate_sample_trade_book_csv()

            df_to_ingest = pd.read_csv(sample_file)
            filename_label = os.path.basename(sample_file)
            st.info(f"Loaded preset file: `{filename_label}` ({len(df_to_ingest)} rows)")

    with col_upload_right:
        st.markdown("#### 2. Schema Auto-Detection & Mapping Inspector")
        if df_to_ingest is not None:
            col_map = parser.map_columns(df_to_ingest.columns.tolist())
            detected_type = parser.detect_dataset_type(col_map)
            
            st.success(f"Detected Type: **{detected_type}** | Columns Found: **{len(col_map)} mapped**")
            
            mapping_display = []
            for k, v in col_map.items():
                mapping_display.append({"Canonical Attribute": k.upper(), "Dataset Column": v})
            
            st.dataframe(pd.DataFrame(mapping_display), use_container_width=True, height=200)

            # Ingestion Action Button
            if st.button("⚡ Ingest into Relational DBMS (ACID Transaction)", type="primary", use_container_width=True):
                with st.spinner("Validating schema, calculating Greeks, and executing SQL transactional ingestion..."):
                    start_t = time.time()
                    try:
                        res = parser.ingest_option_chain_dataframe(df_to_ingest, filename_label)
                        elapsed = time.time() - start_t
                        st.success(f"""
                        ✅ **Database Ingestion Complete!**
                        - **Status**: {res['status']}
                        - **Records Ingested**: {res['records_ingested']}
                        - **Records Failed**: {res['records_failed']}
                        - **Asset**: {res['underlying']} (Spot: ₹{res['spot_price']:,.2f})
                        - **Execution Time**: {elapsed:.2f}s
                        """)
                        time.sleep(1)
                        st.rerun()
                    except Exception as ex:
                        st.error(f"Ingestion failed: {ex}")
        else:
            st.markdown("""
            <div style="background: #161b22; border: 1px dashed #30363d; border-radius: 8px; padding: 2.5rem; text-align: center; color: #8b949e;">
                Select or upload a dataset on the left to inspect its schema and launch relational DBMS ingestion.
            </div>
            """, unsafe_allow_html=True)

    # Data Preview
    if df_to_ingest is not None:
        st.markdown("---")
        st.markdown(f"#### 3. Uploaded Dataset Raw Preview (`{filename_label}` - First 15 Rows)")
        st.dataframe(df_to_ingest.head(15), use_container_width=True)

    # Ingestion Audit Log Table from DB
    st.markdown("---")
    st.markdown("#### 4. DBMS Dataset Ingestion Audit History (`dataset_ingestion_log`)")
    try:
        audit_df = db.execute_query("SELECT * FROM dataset_ingestion_log ORDER BY ingest_id DESC LIMIT 10;")
        if not audit_df.empty:
            st.dataframe(audit_df, use_container_width=True)
        else:
            st.info("No ingestion logs yet.")
    except Exception as e:
        st.error(f"Error loading audit log: {e}")

# ==============================================================================
# TAB 3: F&O TRADING & TRADE BOOK
# ==============================================================================
with tab_trading:
    st.subheader("⚡ F&O Trading Engine & Live Position Book")
    st.markdown("Place trades to trigger real-time database triggers (`trg_trade_buyer_position`, `trg_trade_seller_position`).")

    col_trade_left, col_trade_right = st.columns([1, 1.4])

    with col_trade_left:
        st.markdown("#### 📝 Trade Order Ticket")
        with st.form("trade_order_form"):
            traders_df = db.execute_query("SELECT trader_id, name, account_number, cash_balance FROM traders;")
            trader_map = {f"{r['name']} ({r['account_number']}) - Cash: ₹{r['cash_balance']:,.0f}": r['trader_id'] for _, r in traders_df.iterrows()}
            
            col_b, col_s = st.columns(2)
            with col_b:
                buyer_str = st.selectbox("Buyer Account", list(trader_map.keys()), index=0)
            with col_s:
                seller_index = 1 if len(trader_map) > 1 else 0
                seller_str = st.selectbox("Seller / Counterparty", list(trader_map.keys()), index=seller_index)

            # Contract Selection
            contracts_df = db.execute_query("""
                SELECT c.contract_id, c.contract_symbol, c.strike_price, c.contract_type, c.contract_size, ms.last_traded_price
                FROM contracts c
                LEFT JOIN market_snapshots ms ON c.contract_id = ms.contract_id
                WHERE ms.snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
                ORDER BY c.strike_price ASC
                LIMIT 50;
            """)
            
            if not contracts_df.empty:
                contract_options = {
                    f"{r['contract_symbol']} (LTP: ₹{r['last_traded_price']})": (r['contract_id'], float(r['last_traded_price'] or 100.0), int(r['contract_size']))
                    for _, r in contracts_df.iterrows()
                }
                selected_contract_str = st.selectbox("Select Derivative Contract", list(contract_options.keys()))
                sel_contract_id, default_price, lot_size = contract_options[selected_contract_str]
            else:
                sel_contract_id, default_price, lot_size = 1, 150.0, 50
                st.warning("No contracts available. Upload an option chain dataset first.")

            col_q, col_p = st.columns(2)
            with col_q:
                lots = st.number_input("Number of Lots", min_value=1, max_value=500, value=2, step=1)
                quantity = lots * lot_size
                st.caption(f"Total Quantity: **{quantity} units** (Lot Size: {lot_size})")
            with col_p:
                trade_price = st.number_input("Execution Price (₹)", min_value=0.05, value=float(default_price), step=0.5)

            order_notional = trade_price * quantity
            st.info(f"💵 Total Trade Turnover: **₹{order_notional:,.2f}**")

            submit_trade = st.form_submit_button("⚡ Execute Trade (Commit to DBMS)", type="primary", use_container_width=True)

            if submit_trade:
                b_id = trader_map[buyer_str]
                s_id = trader_map[seller_str]
                if b_id == s_id:
                    st.error("Buyer and Seller cannot be the same account.")
                else:
                    try:
                        conn = db.get_connection()
                        cur = conn.cursor()
                        cur.execute("""
                            INSERT INTO trades (contract_id, buyer_id, seller_id, trade_price, trade_qty)
                            VALUES (?, ?, ?, ?, ?);
                        """, (sel_contract_id, b_id, s_id, trade_price, quantity))
                        conn.commit()
                        conn.close()
                        st.success(f"✅ Trade executed & positions auto-updated by DBMS trigger!")
                        time.sleep(1)
                        st.rerun()
                    except Exception as err:
                        st.error(f"Trade execution failed: {err}")

    with col_trade_right:
        st.markdown("#### 📋 Real-Time Position Book (`vw_open_positions`)")
        try:
            positions_df = db.execute_query("SELECT * FROM vw_open_positions;")
            if not positions_df.empty:
                display_pos = positions_df[[
                    "trader_name", "contract_symbol", "position_side", "net_quantity",
                    "avg_buy_price", "avg_sell_price", "current_ltp", "unrealized_pnl", "delta"
                ]]
                st.dataframe(
                    display_pos.style.format({
                        "avg_buy_price": "₹{:,.2f}",
                        "avg_sell_price": "₹{:,.2f}",
                        "current_ltp": "₹{:,.2f}",
                        "unrealized_pnl": "₹{:,.2f}",
                        "delta": "{:+.3f}"
                    }),
                    use_container_width=True,
                    height=280
                )
            else:
                st.info("No open positions. Use the form to execute trades.")
        except Exception as e:
            st.error(f"Error querying positions: {e}")

        st.markdown("#### 📜 Executed Trades Log (`trades`)")
        try:
            trades_log = db.execute_query("""
                SELECT 
                    t.trade_id,
                    c.contract_symbol,
                    b.name AS buyer,
                    s.name AS seller,
                    t.trade_price,
                    t.trade_qty,
                    (t.trade_price * t.trade_qty) AS turnover,
                    t.executed_at
                FROM trades t
                JOIN contracts c ON t.contract_id = c.contract_id
                JOIN traders b ON t.buyer_id = b.trader_id
                JOIN traders s ON t.seller_id = s.trader_id
                ORDER BY t.trade_id DESC
                LIMIT 6;
            """)
            st.dataframe(trades_log, use_container_width=True, height=220)
        except Exception as e:
            st.error(f"Error loading trades log: {e}")

# ==============================================================================
# TAB 4: VOLATILITY & GREEKS LAB
# ==============================================================================
with tab_volatility:
    st.subheader("📈 Quantitative Volatility & Greeks Analytics Engine")
    st.markdown("Explore 3D Volatility Surfaces, Implied Volatility Smirks/Skews, and Greek Sensitivities.")

    vol_subtab1, vol_subtab2, vol_subtab3 = st.tabs([
        "🌐 3D Volatility Surface", 
        "😊 IV Smile & Skew Curve", 
        "📐 Greeks Risk Ladder & Sensitivity"
    ])

    with vol_subtab1:
        st.markdown("#### Interactive 3D Implied Volatility Surface $(Strike \\times Expiry \\times IV)$")
        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            surface_base_iv = st.slider("Base ATM Volatility (%)", 10.0, 50.0, 18.5, 0.5) / 100.0
        with col_v2:
            surface_skew = st.slider("Put Skew Slope", 0.00001, 0.00020, 0.00008, 0.00001, format="%.5f")
        with col_v3:
            surface_spot = st.number_input("Underlying Spot Reference", value=float(spot_val), step=100.0)

        # Generate meshgrid
        strikes = np.linspace(surface_spot * 0.90, surface_spot * 1.10, 30)
        dtes = np.linspace(2, 60, 20)
        K_mesh, DTE_mesh, iv_surface = generate_volatility_surface_mesh(
            strikes, dtes, surface_base_iv, surface_spot, surface_skew
        )

        fig_3d = go.Figure(data=[go.Surface(
            x=K_mesh,
            y=DTE_mesh,
            z=iv_surface,
            colorscale="Viridis",
            colorbar=dict(title="IV (%)")
        )])
        fig_3d.update_layout(
            title=f"3D Volatility Surface: {selected_underlying}",
            scene=dict(
                xaxis_title="Strike Price (K)",
                yaxis_title="Days to Expiry (DTE)",
                zaxis_title="Implied Volatility (%)",
                camera=dict(eye=dict(x=-1.5, y=-1.5, z=1.2))
            ),
            template="plotly_dark",
            height=580,
            margin=dict(l=10, r=10, b=10, t=40)
        )
        st.plotly_chart(fig_3d, use_container_width=True)

    with vol_subtab2:
        st.markdown("#### Real Market Option Chain IV Smile & Skew")
        try:
            chain_df = db.execute_query("""
                SELECT 
                    c.strike_price,
                    c.contract_type,
                    ms.implied_volatility * 100 AS iv_pct,
                    ms.last_traded_price,
                    ms.open_interest,
                    ms.delta
                FROM contracts c
                JOIN market_snapshots ms ON c.contract_id = ms.contract_id
                WHERE ms.snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
                ORDER BY c.strike_price ASC;
            """)
            if not chain_df.empty:
                fig_smile = px.line(
                    chain_df, 
                    x="strike_price", 
                    y="iv_pct", 
                    color="contract_type",
                    markers=True,
                    title=f"Implied Volatility Smile ({selected_underlying})",
                    labels={"strike_price": "Strike Price", "iv_pct": "Implied Volatility (%)", "contract_type": "Type"},
                    template="plotly_dark",
                    color_discrete_map={"CE": "#00f5a0", "PE": "#ff4b4b"}
                )
                fig_smile.add_vline(x=spot_val, line_dash="dash", line_color="#58a6ff", annotation_text="Spot Price")
                fig_smile.update_layout(height=480)
                st.plotly_chart(fig_smile, use_container_width=True)
            else:
                st.info("No market snapshot data available.")
        except Exception as e:
            st.error(f"Error plotting IV smile: {e}")

    with vol_subtab3:
        st.markdown("#### Black-Scholes Greeks Ladder Simulator")
        col_g1, col_g2, col_g3, col_g4 = st.columns(4)
        with col_g1:
            sim_spot = st.number_input("Spot Price", value=24250.0, step=50.0)
        with col_g2:
            sim_strike = st.number_input("Strike Price", value=24250.0, step=50.0)
        with col_g3:
            sim_dte = st.slider("Days to Expiration", 1, 90, 14)
        with col_g4:
            sim_iv = st.slider("Volatility (IV %)", 5.0, 80.0, 18.0) / 100.0

        # Calculate Greeks across range of spot prices
        spot_range = np.linspace(sim_strike * 0.85, sim_strike * 1.15, 60)
        greeks_data = []
        for s in spot_range:
            c_grk = calculate_greeks(s, sim_strike, sim_dte / 365.0, 0.065, sim_iv, "CE")
            p_grk = calculate_greeks(s, sim_strike, sim_dte / 365.0, 0.065, sim_iv, "PE")
            greeks_data.append({
                "spot": s,
                "Call_Delta": c_grk["delta"],
                "Put_Delta": p_grk["delta"],
                "Gamma": c_grk["gamma"],
                "Vega": c_grk["vega"],
                "Call_Theta": c_grk["theta"],
                "Put_Theta": p_grk["theta"]
            })
        df_greeks_sim = pd.DataFrame(greeks_data)

        greek_choice = st.radio("Select Greek to Plot:", ["Delta", "Gamma", "Vega", "Theta"], horizontal=True)
        if greek_choice == "Delta":
            fig_g = px.line(df_greeks_sim, x="spot", y=["Call_Delta", "Put_Delta"], title="Delta Sensitivity Profile", template="plotly_dark")
        elif greek_choice == "Gamma":
            fig_g = px.line(df_greeks_sim, x="spot", y="Gamma", title="Gamma Sensitivity (Risk of Delta Change)", template="plotly_dark")
        elif greek_choice == "Vega":
            fig_g = px.line(df_greeks_sim, x="spot", y="Vega", title="Vega Sensitivity (Per 1% Volatility Shift)", template="plotly_dark")
        else:
            fig_g = px.line(df_greeks_sim, x="spot", y=["Call_Theta", "Put_Theta"], title="Daily Theta Decay", template="plotly_dark")

        fig_g.add_vline(x=sim_strike, line_dash="dash", line_color="#ffb703", annotation_text="Strike Price")
        fig_g.update_layout(height=420)
        st.plotly_chart(fig_g, use_container_width=True)

# ==============================================================================
# TAB 5: SETTLEMENT & MARGIN CLEARING
# ==============================================================================
with tab_settlement:
    st.subheader("⚖️ Clearing House Settlement & Margin Risk Management")
    st.markdown("Execute End-of-Day Mark-to-Market (MTM) settlement cycles, Variation Margin, and Expiry Cash Settlements.")

    col_settle_ctl, col_settle_stat = st.columns([1, 1.4])

    with col_settle_ctl:
        st.markdown("#### 1. End-of-Day (EOD) MTM Settlement Batch")
        settle_date = st.date_input("Settlement Cycle Date", value=datetime.now().date())
        settle_date_str = settle_date.strftime("%Y-%m-%d")

        if st.button("⚡ Run Daily MTM Settlement Batch", type="primary", use_container_width=True):
            with st.spinner(f"Processing MTM clearing cycle for {settle_date_str}..."):
                res = settlement_engine.run_daily_mtm_settlement(settle_date_str)
                st.success(f"Cleared {res['cleared']} positions for settlement date {settle_date_str}!")
                time.sleep(1)
                st.rerun()

        st.markdown("---")
        st.markdown("#### 2. Final Expiry Cash Settlement")
        st.caption("Cash-settles expiring contracts, exercises ITM options, and books realized P&L.")
        
        # Check active expiry dates in DB
        expiries = db.execute_query("SELECT DISTINCT expiry_date FROM contracts WHERE is_active = 1 ORDER BY expiry_date ASC;")
        if not expiries.empty:
            sel_exp = st.selectbox("Expiring Date to Settle", expiries["expiry_date"].tolist())
            if st.button("🏁 Execute Expiry Cash Settlement", use_container_width=True):
                with st.spinner(f"Settling contracts expiring on {sel_exp}..."):
                    exp_res = settlement_engine.execute_expiry_settlement(sel_exp)
                    st.success(f"Settled {exp_res['contracts_settled']} expiring contracts. Net cash payout: ₹{exp_res['net_payout_amount']:,.2f}")
                    time.sleep(1)
                    st.rerun()
        else:
            st.info("No active expiries.")

    with col_settle_stat:
        st.markdown("#### 3. Clearing House Margin Health & Breach Monitor (`margin_ledger`)")
        try:
            margin_df = db.execute_query("""
                SELECT 
                    t.account_number,
                    t.name,
                    t.account_type,
                    ml.equity_balance,
                    ml.initial_margin_req,
                    ml.maintenance_margin_req,
                    ml.margin_utilization_pct,
                    ml.is_margin_call,
                    ml.margin_shortfall
                FROM margin_ledger ml
                JOIN traders t ON ml.trader_id = t.trader_id
                WHERE ml.calc_date = (SELECT MAX(calc_date) FROM margin_ledger);
            """)
            if not margin_df.empty:
                st.dataframe(
                    margin_df.style.format({
                        "equity_balance": "₹{:,.2f}",
                        "initial_margin_req": "₹{:,.2f}",
                        "maintenance_margin_req": "₹{:,.2f}",
                        "margin_utilization_pct": "{:.1f}%",
                        "margin_shortfall": "₹{:,.2f}"
                    }),
                    use_container_width=True,
                    height=260
                )
            else:
                st.info("Run daily MTM settlement on the left to generate the margin ledger.")
        except Exception as e:
            st.error(f"Error loading margin ledger: {e}")

    # Daily MTM Settlement Ledger History Table
    st.markdown("---")
    st.markdown("#### 4. Historical MTM Variation Margin Ledger (`daily_settlement_ledger`)")
    try:
        ledger_df = db.execute_query("""
            SELECT 
                s.settlement_id,
                s.settlement_date,
                t.name AS trader_name,
                c.contract_symbol,
                s.open_net_qty,
                s.prior_settlement_price,
                s.current_settlement_price,
                s.mtm_pnl,
                s.variation_margin,
                s.settlement_status
            FROM daily_settlement_ledger s
            JOIN traders t ON s.trader_id = t.trader_id
            JOIN contracts c ON s.contract_id = c.contract_id
            ORDER BY s.settlement_date DESC, s.settlement_id DESC
            LIMIT 15;
        """)
        if not ledger_df.empty:
            st.dataframe(
                ledger_df.style.format({
                    "prior_settlement_price": "₹{:,.2f}",
                    "current_settlement_price": "₹{:,.2f}",
                    "mtm_pnl": "₹{:,.2f}",
                    "variation_margin": "₹{:,.2f}"
                }),
                use_container_width=True
            )
        else:
            st.info("No settlement records yet. Execute daily MTM settlement above.")
    except Exception as e:
        st.error(f"Error loading settlement ledger: {e}")

# ==============================================================================
# TAB 6: DBMS WORKBENCH & SQL CONSOLE
# ==============================================================================
with tab_workbench:
    st.subheader("🗄️ Relational DBMS Workbench & SQL Query Console")
    st.markdown("Execute custom SQL queries, inspect table structures, analyze query plans, and explore the schema.")

    workbench_sub1, workbench_sub2, workbench_sub3 = st.tabs([
        "💻 Interactive SQL Console",
        "📚 Curated Institutional SQL Queries",
        "🔍 Schema Browser & Table Introspection"
    ])

    with workbench_sub1:
        st.markdown("#### Run Arbitrary SQL Query against DBMS")
        default_sql = "SELECT * FROM vw_open_positions LIMIT 10;"
        user_sql = st.text_area("SQL Statement (Supports SELECT, INSERT, UPDATE, EXPLAIN)", value=default_sql, height=120)

        col_run, col_explain = st.columns([1, 1])
        with col_run:
            if st.button("▶️ Execute Query", type="primary", use_container_width=True):
                try:
                    start_t = time.time()
                    if user_sql.strip().upper().startswith("SELECT") or user_sql.strip().upper().startswith("WITH") or user_sql.strip().upper().startswith("EXPLAIN"):
                        result_df = db.execute_query(user_sql)
                        elapsed = (time.time() - start_t) * 1000.0
                        st.success(f"Query returned {len(result_df)} rows in {elapsed:.2f} ms")
                        st.dataframe(result_df, use_container_width=True)
                    else:
                        affected = db.execute_non_query(user_sql)
                        elapsed = (time.time() - start_t) * 1000.0
                        st.success(f"Statement executed successfully. Affected/Last ID: {affected} in {elapsed:.2f} ms")
                except Exception as err:
                    st.error(f"SQL Execution Error: {err}")

        with col_explain:
            if st.button("🔎 EXPLAIN Query Plan", use_container_width=True):
                try:
                    plan_df = db.explain_query_plan(user_sql)
                    st.write("**SQLite Query Execution Plan:**")
                    st.dataframe(plan_df, use_container_width=True)
                except Exception as err:
                    st.error(f"Explain Error: {err}")

    with workbench_sub2:
        st.markdown("#### Curated Institutional SQL Query Library")
        st.caption("Pre-tested queries demonstrating Common Table Expressions (CTEs), Window Functions, and Risk Rollups.")
        
        query_names = list(QUERIES.keys())
        selected_query_name = st.selectbox("Select Pre-built Institutional Query", query_names)
        
        query_info = QUERIES[selected_query_name]
        st.markdown(f"**Description**: {query_info['description']}")
        st.code(query_info["sql"].strip(), language="sql")

        if st.button(f"▶️ Run '{selected_query_name}'", use_container_width=True):
            try:
                start_t = time.time()
                lib_df = db.execute_query(query_info["sql"])
                elapsed = (time.time() - start_t) * 1000.0
                st.success(f"Returned {len(lib_df)} rows in {elapsed:.2f} ms")
                st.dataframe(lib_df, use_container_width=True)
            except Exception as e:
                st.error(f"Query error: {e}")

    with workbench_sub3:
        st.markdown("#### Schema Browser & Table Metadata")
        tables_meta = db.get_tables_info()
        st.dataframe(pd.DataFrame(tables_meta), use_container_width=True)

        selected_table = st.selectbox("Inspect Columns for Table/View:", [t["name"] for t in tables_meta])
        if selected_table:
            col_meta = db.get_table_schema(selected_table)
            fk_meta = db.get_foreign_keys(selected_table)
            
            c_meta1, c_meta2 = st.columns(2)
            with c_meta1:
                st.write(f"**Columns for `{selected_table}`:**")
                st.dataframe(col_meta, use_container_width=True)
            with c_meta2:
                st.write(f"**Foreign Keys for `{selected_table}`:**")
                if not fk_meta.empty:
                    st.dataframe(fk_meta, use_container_width=True)
                else:
                    st.info("No foreign keys defined directly on this entity.")
