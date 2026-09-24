"""
Database Populator and Sample File Creator.
Ensures default database has complete realistic data for immediate demo and testing.
"""

import os
import sys

workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if workspace_dir not in sys.path:
    sys.path.insert(0, workspace_dir)

import pandas as pd
from datetime import datetime, timedelta
from database.db_manager import get_db
from ingestion.sample_data_generator import generate_option_chain_csv, generate_sample_trade_book_csv, seed_initial_database
from ingestion.dataset_parser import DatasetParser
from analytics.settlement_engine import SettlementEngine

def seed_all():
    db = get_db()
    seed_initial_database(db)
    
    # 1. Generate & Ingest NIFTY option chain
    nifty_csv = generate_option_chain_csv("NIFTY", 24250.0, 7, 50)
    parser = DatasetParser(db)
    df_nifty = pd.read_csv(nifty_csv)
    parser.ingest_option_chain_dataframe(df_nifty, "option_chain_nifty.csv")

    # 2. Generate & Ingest BANKNIFTY option chain
    banknifty_csv = generate_option_chain_csv("BANKNIFTY", 52100.0, 7, 15)
    df_bn = pd.read_csv(banknifty_csv)
    parser.ingest_option_chain_dataframe(df_bn, "option_chain_banknifty.csv")

    # 3. Generate sample trade book CSV
    generate_sample_trade_book_csv()

    # 4. Insert some initial simulated trades
    conn = db.get_connection()
    cur = conn.cursor()
    
    # Check if trades already exist
    cur.execute("SELECT COUNT(*) FROM trades;")
    if cur.fetchone()[0] == 0:
        # Get some contract IDs
        cur.execute("SELECT contract_id, strike_price, contract_type FROM contracts WHERE underlying_id = 1 LIMIT 10;")
        nifty_contracts = cur.fetchall()

        if len(nifty_contracts) >= 4:
            # Trade 1: Alpha buys 200 contracts from Gamma
            cur.execute("""
                INSERT INTO trades (contract_id, buyer_id, seller_id, trade_price, trade_qty)
                VALUES (?, 1, 3, 220.0, 200);
            """, (nifty_contracts[0]["contract_id"],))

            # Trade 2: Beta buys 150 contracts from Retail 1
            cur.execute("""
                INSERT INTO trades (contract_id, buyer_id, seller_id, trade_price, trade_qty)
                VALUES (?, 2, 4, 145.0, 150);
            """, (nifty_contracts[1]["contract_id"],))

            # Trade 3: Retail 2 buys 50 contracts from Gamma
            cur.execute("""
                INSERT INTO trades (contract_id, buyer_id, seller_id, trade_price, trade_qty)
                VALUES (?, 5, 3, 85.0, 50);
            """, (nifty_contracts[2]["contract_id"],))

            # Trade 4: Gamma buys 100 contracts from Alpha
            cur.execute("""
                INSERT INTO trades (contract_id, buyer_id, seller_id, trade_price, trade_qty)
                VALUES (?, 3, 1, 310.0, 100);
            """, (nifty_contracts[3]["contract_id"],))

            conn.commit()

    conn.close()

    # 5. Run initial settlement for yesterday and today
    settlement = SettlementEngine(db)
    yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    today = datetime.now().strftime("%Y-%m-%d")
    try:
        settlement.run_daily_mtm_settlement(yesterday)
        settlement.run_daily_mtm_settlement(today)
    except Exception as e:
        print(f"Settlement notice: {e}")

    print("Initial seeding completed successfully.")

if __name__ == "__main__":
    seed_all()
