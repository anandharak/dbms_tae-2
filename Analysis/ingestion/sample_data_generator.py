"""
Sample Dataset Generator for Futures & Options System.
Generates realistic Option Chains, Trades, and Settlement Feeds,
and saves them as CSV files in the data/ directory for instant testing and dataset upload testing.
"""

import os
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from analytics.black_scholes import calculate_option_price, calculate_greeks

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data")

def generate_option_chain_csv(
    underlying_symbol: str = "NIFTY", 
    spot_price: float = 24250.0, 
    expiry_days: int = 7,
    lot_size: int = 50
) -> str:
    """Generate realistic Option Chain CSV with Strikes, CE/PE, LTP, IV, Greeks, OI, Volume."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, f"option_chain_{underlying_symbol.lower()}.csv")

    expiry_date = (datetime.now() + timedelta(days=expiry_days)).strftime("%Y-%m-%d")
    T = expiry_days / 365.0
    r = 0.065

    # Strikes centered around spot price with step 50
    center_strike = int(round(spot_price / 50.0) * 50)
    strikes = [center_strike + i * 50 for i in range(-25, 26)] # 51 strikes

    records = []
    for K in strikes:
        # Base volatility smile
        moneyness = K / spot_price
        base_iv = 0.16 + 0.35 * ((moneyness - 1.0) ** 2) - 0.04 * (moneyness - 1.0)
        base_iv = max(0.09, min(base_iv, 0.45))

        # Call Option
        call_iv = base_iv
        call_price = calculate_option_price(spot_price, K, T, r, call_iv, "CE")
        call_greeks = calculate_greeks(spot_price, K, T, r, call_iv, "CE")
        call_oi = int(np.random.randint(5000, 350000) * np.exp(-abs(moneyness - 1.0) * 8))
        call_vol = int(call_oi * np.random.uniform(0.1, 0.6))

        records.append({
            "underlying_symbol": underlying_symbol,
            "contract_symbol": f"{underlying_symbol}_{expiry_date.replace('-', '')}_{K}_CE",
            "contract_type": "CE",
            "strike_price": K,
            "expiry_date": expiry_date,
            "lot_size": lot_size,
            "spot_price": spot_price,
            "ltp": round(call_price, 2),
            "bid": round(max(0.05, call_price - 0.5), 2),
            "ask": round(call_price + 0.5, 2),
            "iv_pct": round(call_iv * 100, 2),
            "delta": call_greeks["delta"],
            "gamma": call_greeks["gamma"],
            "theta": call_greeks["theta"],
            "vega": call_greeks["vega"],
            "rho": call_greeks["rho"],
            "volume": call_vol,
            "open_interest": call_oi,
            "trade_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

        # Put Option
        put_iv = base_iv * 1.05  # Put skew
        put_price = calculate_option_price(spot_price, K, T, r, put_iv, "PE")
        put_greeks = calculate_greeks(spot_price, K, T, r, put_iv, "PE")
        put_oi = int(np.random.randint(5000, 350000) * np.exp(-abs(moneyness - 1.0) * 8))
        put_vol = int(put_oi * np.random.uniform(0.1, 0.6))

        records.append({
            "underlying_symbol": underlying_symbol,
            "contract_symbol": f"{underlying_symbol}_{expiry_date.replace('-', '')}_{K}_PE",
            "contract_type": "PE",
            "strike_price": K,
            "expiry_date": expiry_date,
            "lot_size": lot_size,
            "spot_price": spot_price,
            "ltp": round(put_price, 2),
            "bid": round(max(0.05, put_price - 0.5), 2),
            "ask": round(put_price + 0.5, 2),
            "iv_pct": round(put_iv * 100, 2),
            "delta": put_greeks["delta"],
            "gamma": put_greeks["gamma"],
            "theta": put_greeks["theta"],
            "vega": put_greeks["vega"],
            "rho": put_greeks["rho"],
            "volume": put_vol,
            "open_interest": put_oi,
            "trade_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })

    df = pd.DataFrame(records)
    df.to_csv(filepath, index=False)
    return filepath

def generate_sample_trade_book_csv() -> str:
    """Generate realistic Trade Book CSV."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, "sample_trade_book.csv")

    trades_data = [
        {"trade_id": "TRD1001", "contract_symbol": "NIFTY_FUT_CURR", "buyer_account": "ACC_ALPHA_CORP", "seller_account": "ACC_RETAIL_01", "price": 24280.0, "quantity": 100, "trade_time": "2026-09-22 09:30:15"},
        {"trade_id": "TRD1002", "contract_symbol": "NIFTY_24200_CE", "buyer_account": "ACC_BETA_PROP", "seller_account": "ACC_ALPHA_CORP", "price": 185.50, "quantity": 250, "trade_time": "2026-09-22 10:15:30"},
        {"trade_id": "TRD1003", "contract_symbol": "NIFTY_24300_PE", "buyer_account": "ACC_RETAIL_01", "seller_account": "ACC_BETA_PROP", "price": 142.20, "quantity": 150, "trade_time": "2026-09-22 11:05:42"},
        {"trade_id": "TRD1004", "contract_symbol": "NIFTY_24400_CE", "buyer_account": "ACC_GAMMA_MM", "seller_account": "ACC_RETAIL_02", "price": 78.40, "quantity": 500, "trade_time": "2026-09-22 12:20:10"},
        {"trade_id": "TRD1005", "contract_symbol": "NIFTY_24100_PE", "buyer_account": "ACC_RETAIL_02", "seller_account": "ACC_GAMMA_MM", "price": 62.10, "quantity": 300, "trade_time": "2026-09-22 14:10:05"},
    ]
    df = pd.DataFrame(trades_data)
    df.to_csv(filepath, index=False)
    return filepath

def seed_initial_database(db):
    """Seed initial sample records into SQLite database if empty."""
    conn = db.get_connection()
    try:
        cursor = conn.cursor()
        
        # Check if underlying assets exist
        cursor.execute("SELECT COUNT(*) FROM underlying_assets;")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO underlying_assets (symbol, asset_name, asset_class, spot_price, lot_size, tick_size, currency)
                VALUES 
                    ('NIFTY', 'NIFTY 50 Index', 'EQUITY_INDEX', 24250.00, 50, 0.05, 'INR'),
                    ('BANKNIFTY', 'NIFTY Bank Index', 'EQUITY_INDEX', 52100.00, 15, 0.05, 'INR'),
                    ('RELIANCE', 'Reliance Industries Ltd', 'EQUITY_STOCK', 2950.00, 250, 0.05, 'INR'),
                    ('AAPL', 'Apple Inc', 'EQUITY_STOCK', 225.50, 100, 0.01, 'USD');
            """)

        # Check if default traders exist
        cursor.execute("SELECT COUNT(*) FROM traders;")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO traders (account_number, name, account_type, cash_balance, collateral_value, margin_multiplier)
                VALUES 
                    ('ACC_ALPHA_CORP', 'Alpha Institutional Fund', 'INSTITUTIONAL', 25000000.00, 10000000.00, 2.50),
                    ('ACC_BETA_PROP', 'Beta Quantitative Prop Desk', 'PROPRIETARY', 15000000.00, 5000000.00, 2.00),
                    ('ACC_GAMMA_MM', 'Gamma Market Maker LLP', 'MARKET_MAKER', 50000000.00, 20000000.00, 3.00),
                    ('ACC_RETAIL_01', 'Rahul Sharma (Retail HNI)', 'RETAIL', 2500000.00, 500000.00, 1.00),
                    ('ACC_RETAIL_02', 'Priya Patel (Retail Active)', 'RETAIL', 1200000.00, 0.00, 1.00);
            """)

        conn.commit()
    finally:
        conn.close()
