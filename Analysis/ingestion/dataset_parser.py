"""
Dataset Ingestion & Schema Mapper Engine.
Handles uploaded CSV/Excel files, normalizes columns, validates integrity,
and inserts records into the Relational DBMS with transactions and audit logs.
"""

import os
import re
import pandas as pd
import numpy as np
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from database.db_manager import DatabaseManager, get_db
from analytics.black_scholes import calculate_greeks, calculate_implied_volatility

# Column synonym dictionary for flexible dataset schema mapping
SYNONYM_MAP = {
    "underlying": ["underlying", "symbol", "underlying_symbol", "stock", "index", "ticker"],
    "contract_symbol": ["contract_symbol", "contract", "instrument", "option_symbol", "tradingsymbol"],
    "contract_type": ["contract_type", "type", "option_type", "opt_type", "ce_pe"],
    "strike_price": ["strike_price", "strike", "strikeprice", "k"],
    "expiry_date": ["expiry_date", "expiry", "expiration", "exp_date", "expiration_date"],
    "ltp": ["ltp", "last_price", "close", "last_traded_price", "price", "settle_price"],
    "bid": ["bid", "bid_price", "best_bid"],
    "ask": ["ask", "ask_price", "offer", "best_ask"],
    "iv": ["iv", "iv_pct", "implied_volatility", "volatility", "implied_vol"],
    "volume": ["volume", "vol", "traded_qty", "traded_volume"],
    "open_interest": ["open_interest", "oi", "openinterest"],
    "spot_price": ["spot_price", "underlying_spot", "spot", "index_price", "underlying_price"],
    "lot_size": ["lot_size", "lotsize", "contract_size", "market_lot"]
}

class DatasetParser:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or get_db()

    def map_columns(self, df_cols: List[str]) -> Dict[str, str]:
        """Map user uploaded column names to standardized canonical column names."""
        mapping = {}
        cleaned_cols = {re.sub(r'[^a-zA-Z0-9]', '', c).lower(): c for c in df_cols}

        for canonical, synonyms in SYNONYM_MAP.items():
            for syn in synonyms:
                cleaned_syn = re.sub(r'[^a-zA-Z0-9]', '', syn).lower()
                if cleaned_syn in cleaned_cols:
                    mapping[canonical] = cleaned_cols[cleaned_syn]
                    break
        return mapping

    def detect_dataset_type(self, mapped_cols: Dict[str, str]) -> str:
        """Infer whether uploaded dataset is an Option Chain, Trade Book, or Settlement Feed."""
        if "strike_price" in mapped_cols and "contract_type" in mapped_cols:
            return "OPTION_CHAIN"
        elif "buyer_account" in mapped_cols or "trade_id" in mapped_cols:
            return "TRADE_BOOK"
        elif "settlement_price" in mapped_cols or "mtm_pnl" in mapped_cols:
            return "SETTLEMENT_FEED"
        return "GENERIC_FUTURES_OPTIONS"

    def ingest_option_chain_dataframe(
        self, 
        df: pd.DataFrame, 
        filename: str = "uploaded_file.csv"
    ) -> Dict[str, Any]:
        """
        Validate, normalize, and ingest an Option Chain dataset into relational database.
        Populates underlying_assets, contracts, and market_snapshots tables.
        """
        col_map = self.map_columns(df.columns.tolist())
        records_ingested = 0
        records_failed = 0
        conn = self.db.get_connection()

        try:
            cursor = conn.cursor()
            
            # Extract or default key values
            underlying_col = col_map.get("underlying")
            strike_col = col_map.get("strike_price")
            type_col = col_map.get("contract_type")
            expiry_col = col_map.get("expiry_date")
            ltp_col = col_map.get("ltp")
            spot_col = col_map.get("spot_price")
            iv_col = col_map.get("iv")
            vol_col = col_map.get("volume")
            oi_col = col_map.get("open_interest")
            lot_col = col_map.get("lot_size")

            if not strike_col or not type_col:
                raise ValueError("Dataset missing required 'Strike' or 'Option Type' columns.")

            default_underlying = "DERIVATIVE_INDEX"
            if underlying_col and not df[underlying_col].isna().all():
                default_underlying = str(df[underlying_col].dropna().iloc[0]).upper()

            default_spot = 24000.0
            if spot_col and not df[spot_col].isna().all():
                default_spot = float(df[spot_col].dropna().iloc[0])

            default_lot = 50
            if lot_col and not df[lot_col].isna().all():
                default_lot = int(df[lot_col].dropna().iloc[0])

            # 1. Upsert Underlying Asset
            cursor.execute("""
                INSERT INTO underlying_assets (symbol, asset_name, asset_class, spot_price, lot_size, tick_size, currency)
                VALUES (?, ?, 'EQUITY_INDEX', ?, ?, 0.05, 'INR')
                ON CONFLICT(symbol) DO UPDATE SET
                    spot_price = excluded.spot_price,
                    updated_at = CURRENT_TIMESTAMP;
            """, (default_underlying, f"{default_underlying} Asset", default_spot, default_lot))
            
            cursor.execute("SELECT underlying_id FROM underlying_assets WHERE symbol = ?;", (default_underlying,))
            underlying_id = cursor.fetchone()[0]

            now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            for _, row in df.iterrows():
                try:
                    raw_type = str(row[type_col]).upper().strip()
                    c_type = "CE" if "CALL" in raw_type or raw_type == "CE" or raw_type == "C" else "PE"
                    strike = float(row[strike_col])
                    
                    if expiry_col and pd.notna(row[expiry_col]):
                        expiry_date = pd.to_datetime(row[expiry_col]).strftime("%Y-%m-%d")
                    else:
                        expiry_date = (datetime.now() + pd.Timedelta(days=7)).strftime("%Y-%m-%d")

                    ltp = float(row[ltp_col]) if (ltp_col and pd.notna(row[ltp_col])) else 100.0
                    vol = int(row[vol_col]) if (vol_col and pd.notna(row[vol_col])) else 1000
                    oi = int(row[oi_col]) if (oi_col and pd.notna(row[oi_col])) else 50000

                    # Standardized contract symbol
                    c_symbol = f"{default_underlying}_{expiry_date.replace('-', '')}_{int(strike)}_{c_type}"

                    # Upsert contract
                    cursor.execute("""
                        INSERT INTO contracts (contract_symbol, underlying_id, contract_type, strike_price, expiry_date, contract_size, settlement_type, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, 'CASH', 1)
                        ON CONFLICT(contract_symbol) DO UPDATE SET
                            expiry_date = excluded.expiry_date,
                            contract_size = excluded.contract_size;
                    """, (c_symbol, underlying_id, c_type, strike, expiry_date, default_lot))

                    cursor.execute("SELECT contract_id FROM contracts WHERE contract_symbol = ?;", (c_symbol,))
                    contract_id = cursor.fetchone()[0]

                    # Volatility and Greeks calculation
                    if iv_col and pd.notna(row[iv_col]):
                        raw_iv = float(row[iv_col])
                        iv = raw_iv / 100.0 if raw_iv > 2.0 else raw_iv
                    else:
                        # Auto-solve IV
                        days_left = max(1, (pd.to_datetime(expiry_date) - pd.to_datetime(datetime.now().date())).days)
                        iv = calculate_implied_volatility(ltp, default_spot, strike, days_left / 365.0, 0.065, c_type)

                    days_to_exp = max(1, (pd.to_datetime(expiry_date) - pd.to_datetime(datetime.now().date())).days)
                    greeks = calculate_greeks(default_spot, strike, days_to_exp / 365.0, 0.065, iv, c_type)

                    # Insert market snapshot
                    cursor.execute("""
                        INSERT INTO market_snapshots (
                            contract_id, snapshot_time, underlying_spot, last_traded_price,
                            bid_price, ask_price, volume, open_interest,
                            implied_volatility, delta, gamma, theta, vega, rho
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                    """, (
                        contract_id, now_str, default_spot, ltp,
                        round(max(0.05, ltp - 0.5), 2), round(ltp + 0.5, 2), vol, oi,
                        round(iv, 4), greeks["delta"], greeks["gamma"], greeks["theta"], greeks["vega"], greeks["rho"]
                    ))

                    records_ingested += 1
                except Exception as ex:
                    records_failed += 1

            # Log audit
            cursor.execute("""
                INSERT INTO dataset_ingestion_log (filename, dataset_type, records_ingested, records_failed, status, notes)
                VALUES (?, 'OPTION_CHAIN', ?, ?, 'SUCCESS', ?);
            """, (filename, records_ingested, records_failed, f"Ingested for {default_underlying} with spot {default_spot}"))

            conn.commit()

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

        return {
            "status": "SUCCESS",
            "filename": filename,
            "dataset_type": "OPTION_CHAIN",
            "records_ingested": records_ingested,
            "records_failed": records_failed,
            "underlying": default_underlying,
            "spot_price": default_spot
        }
