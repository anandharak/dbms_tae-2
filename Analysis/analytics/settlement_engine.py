"""
Settlement & Clearing Management Engine.
Implements:
1. Daily Mark-to-Market (MTM) Settlement & Variation Margin Ledger.
2. SPAN-style Initial & Maintenance Margin Calculator.
3. Margin Call and Liquidation Trigger Monitoring.
4. Expiry Cash Settlement & Realized P&L Closing Engine.
"""

import pandas as pd
import numpy as np
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple
from database.db_manager import DatabaseManager, get_db

class SettlementEngine:
    """
    Clearing House Settlement & Risk Management Engine.
    Interacts with the Relational Database to enforce daily MTM, cash flows, and margin checks.
    """
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or get_db()

    def run_daily_mtm_settlement(self, settlement_date: str) -> Dict[str, int]:
        """
        Execute End-of-Day Mark-to-Market (MTM) settlement run.
        1. Fetch all open positions across all traders.
        2. Determine current settlement price from latest market snapshot or LTP.
        3. Compute MTM P&L vs prior settlement price (or entry price if opened today).
        4. Insert entries into `daily_settlement_ledger`.
        5. Update trader cash balances with Variation Margin.
        """
        conn = self.db.get_connection()
        records_processed = 0
        records_cleared = 0

        try:
            cursor = conn.cursor()
            
            # Retrieve open positions with latest contract pricing
            query = """
            SELECT 
                p.position_id,
                p.trader_id,
                p.contract_id,
                p.net_quantity,
                p.avg_buy_price,
                p.avg_sell_price,
                c.contract_symbol,
                c.contract_type,
                c.strike_price,
                c.contract_size,
                c.expiry_date,
                COALESCE(ms.last_traded_price, 0) AS current_price,
                (
                    SELECT current_settlement_price 
                    FROM daily_settlement_ledger dsl 
                    WHERE dsl.contract_id = p.contract_id 
                      AND dsl.trader_id = p.trader_id 
                      AND dsl.settlement_date < ?
                    ORDER BY dsl.settlement_date DESC, dsl.settlement_id DESC 
                    LIMIT 1
                ) AS prior_settlement_price
            FROM positions p
            JOIN contracts c ON p.contract_id = c.contract_id
            LEFT JOIN (
                SELECT contract_id, last_traded_price 
                FROM market_snapshots 
                WHERE snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
            ) ms ON c.contract_id = ms.contract_id
            WHERE p.net_quantity != 0;
            """
            
            positions = cursor.execute(query, (settlement_date,)).fetchall()
            
            for pos in positions:
                trader_id = pos["trader_id"]
                contract_id = pos["contract_id"]
                net_qty = pos["net_quantity"]
                contract_size = pos["contract_size"]
                current_price = float(pos["current_price"])
                
                # Determine baseline reference price
                if pos["prior_settlement_price"] is not None:
                    prior_price = float(pos["prior_settlement_price"])
                else:
                    prior_price = float(pos["avg_buy_price"] if net_qty > 0 else pos["avg_sell_price"])
                
                if current_price <= 0.0:
                    current_price = prior_price

                # Mark to market calculation
                price_diff = current_price - prior_price
                mtm_pnl = price_diff * net_qty * contract_size
                variation_margin = mtm_pnl  # Profit credits cash, Loss debits cash

                # Upsert daily settlement ledger entry
                cursor.execute("""
                    INSERT INTO daily_settlement_ledger (
                        settlement_date, trader_id, contract_id, open_net_qty, 
                        prior_settlement_price, current_settlement_price, 
                        mtm_pnl, variation_margin, settlement_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'CLEARED')
                    ON CONFLICT(settlement_date, trader_id, contract_id) DO UPDATE SET
                        open_net_qty = excluded.open_net_qty,
                        prior_settlement_price = excluded.prior_settlement_price,
                        current_settlement_price = excluded.current_settlement_price,
                        mtm_pnl = excluded.mtm_pnl,
                        variation_margin = excluded.variation_margin,
                        processed_at = CURRENT_TIMESTAMP;
                """, (
                    settlement_date, trader_id, contract_id, net_qty,
                    round(prior_price, 4), round(current_price, 4),
                    round(mtm_pnl, 4), round(variation_margin, 4)
                ))

                # Apply Variation Margin to trader account cash balance
                cursor.execute("""
                    UPDATE traders
                    SET cash_balance = cash_balance + ?
                    WHERE trader_id = ?;
                """, (round(variation_margin, 4), trader_id))

                records_processed += 1
                records_cleared += 1

            conn.commit()
            
            # Recalculate margins for all traders
            self.calculate_all_trader_margins(settlement_date, conn)

        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

        return {"processed": records_processed, "cleared": records_cleared}

    def calculate_all_trader_margins(self, calc_date: str, conn: Optional[any] = None) -> List[Dict]:
        """
        Compute SPAN-like Initial Margin, Maintenance Margin, and Check for Margin Calls.
        """
        own_conn = False
        if conn is None:
            conn = self.db.get_connection()
            own_conn = True

        results = []
        try:
            cursor = conn.cursor()
            traders = cursor.execute("SELECT trader_id, account_number, name, cash_balance, collateral_value FROM traders").fetchall()
            
            for tr in traders:
                trader_id = tr["trader_id"]
                cash = float(tr["cash_balance"])
                collateral = float(tr["collateral_value"])

                # Query positions and current notional / risk
                pos_query = """
                SELECT 
                    p.net_quantity,
                    c.contract_type,
                    c.strike_price,
                    c.contract_size,
                    u.spot_price,
                    COALESCE(ms.last_traded_price, 0) AS ltp
                FROM positions p
                JOIN contracts c ON p.contract_id = c.contract_id
                JOIN underlying_assets u ON c.underlying_id = u.underlying_id
                LEFT JOIN (
                    SELECT contract_id, last_traded_price 
                    FROM market_snapshots 
                    WHERE snapshot_id IN (SELECT MAX(snapshot_id) FROM market_snapshots GROUP BY contract_id)
                ) ms ON c.contract_id = ms.contract_id
                WHERE p.trader_id = ? AND p.net_quantity != 0;
                """
                positions = cursor.execute(pos_query, (trader_id,)).fetchall()
                
                initial_margin = 0.0
                unrealized_pnl = 0.0

                for pos in positions:
                    qty = pos["net_quantity"]
                    c_size = pos["contract_size"]
                    ltp = float(pos["ltp"])
                    spot = float(pos["spot_price"])
                    c_type = pos["contract_type"]

                    if c_type == "FUT":
                        # Futures initial margin: ~12.5% of notional
                        initial_margin += abs(qty) * c_size * (ltp or spot) * 0.125
                    elif c_type in ("CE", "PE"):
                        if qty < 0:
                            # Short option margin: premium + 10% underlying spot exposure
                            initial_margin += abs(qty) * c_size * (ltp + (spot * 0.10))
                        else:
                            # Long option: maximum risk is premium paid
                            initial_margin += abs(qty) * c_size * ltp * 0.20

                maintenance_margin = initial_margin * 0.75
                total_equity = cash + collateral

                utilization = (initial_margin / total_equity * 100.0) if total_equity > 0 else 100.0
                is_call = total_equity < maintenance_margin and initial_margin > 0
                shortfall = max(0.0, maintenance_margin - total_equity) if is_call else 0.0

                # Upsert into margin_ledger
                cursor.execute("""
                    INSERT INTO margin_ledger (
                        trader_id, calc_date, initial_margin_req, maintenance_margin_req,
                        equity_balance, margin_utilization_pct, is_margin_call, margin_shortfall
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(trader_id, calc_date) DO UPDATE SET
                        initial_margin_req = excluded.initial_margin_req,
                        maintenance_margin_req = excluded.maintenance_margin_req,
                        equity_balance = excluded.equity_balance,
                        margin_utilization_pct = excluded.margin_utilization_pct,
                        is_margin_call = excluded.is_margin_call,
                        margin_shortfall = excluded.margin_shortfall,
                        recorded_at = CURRENT_TIMESTAMP;
                """, (
                    trader_id, calc_date, round(initial_margin, 2), round(maintenance_margin, 2),
                    round(total_equity, 2), round(utilization, 2), 1 if is_call else 0, round(shortfall, 2)
                ))

                results.append({
                    "trader_id": trader_id,
                    "account": tr["account_number"],
                    "name": tr["name"],
                    "total_equity": total_equity,
                    "initial_margin": initial_margin,
                    "maintenance_margin": maintenance_margin,
                    "margin_call": is_call,
                    "shortfall": shortfall
                })

            conn.commit()
        finally:
            if own_conn:
                conn.close()

        return results

    def execute_expiry_settlement(self, expiry_date: str) -> Dict[str, any]:
        """
        Execute final Cash Settlement for contracts expiring on `expiry_date`.
        - Calls: Max(0, Spot - Strike)
        - Puts: Max(0, Strike - Spot)
        - Futures: (Spot - Prior Settlement)
        Credited/Debited to trader, and positions closed (net_quantity set to 0).
        """
        conn = self.db.get_connection()
        settled_count = 0
        total_payout = 0.0

        try:
            cursor = conn.cursor()
            
            # Find expiring contracts with active open positions
            query = """
            SELECT 
                p.position_id,
                p.trader_id,
                p.contract_id,
                p.net_quantity,
                p.avg_buy_price,
                p.avg_sell_price,
                c.contract_symbol,
                c.contract_type,
                c.strike_price,
                c.contract_size,
                u.spot_price AS final_underlying_spot
            FROM positions p
            JOIN contracts c ON p.contract_id = c.contract_id
            JOIN underlying_assets u ON c.underlying_id = u.underlying_id
            WHERE c.expiry_date = ? AND p.net_quantity != 0;
            """
            
            expiring_positions = cursor.execute(query, (expiry_date,)).fetchall()

            for pos in expiring_positions:
                pos_id = pos["position_id"]
                trader_id = pos["trader_id"]
                contract_id = pos["contract_id"]
                net_qty = pos["net_quantity"]
                contract_size = pos["contract_size"]
                spot = float(pos["final_underlying_spot"])
                c_type = pos["contract_type"]
                strike = float(pos["strike_price"]) if pos["strike_price"] else None

                # Compute final cash payoff
                if c_type == "CE":
                    payoff_per_share = max(0.0, spot - strike)
                elif c_type == "PE":
                    payoff_per_share = max(0.0, strike - spot)
                else: # FUT
                    payoff_per_share = spot - (float(pos["avg_buy_price"]) if net_qty > 0 else float(pos["avg_sell_price"]))

                total_cash_settlement = payoff_per_share * net_qty * contract_size
                total_payout += total_cash_settlement

                # Record in daily settlement ledger as FINAL_EXPIRY
                cursor.execute("""
                    INSERT INTO daily_settlement_ledger (
                        settlement_date, trader_id, contract_id, open_net_qty,
                        prior_settlement_price, current_settlement_price,
                        mtm_pnl, variation_margin, settlement_status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'FINAL_EXPIRY');
                """, (
                    expiry_date, trader_id, contract_id, net_qty,
                    strike or spot, payoff_per_share,
                    total_cash_settlement, total_cash_settlement
                ))

                # Credit/Debit trader cash balance
                cursor.execute("""
                    UPDATE traders 
                    SET cash_balance = cash_balance + ?
                    WHERE trader_id = ?;
                """, (round(total_cash_settlement, 4), trader_id))

                # Close out position
                cursor.execute("""
                    UPDATE positions 
                    SET realized_pnl = realized_pnl + ?,
                        net_quantity = 0,
                        last_updated = CURRENT_TIMESTAMP
                    WHERE position_id = ?;
                """, (round(total_cash_settlement, 4), pos_id))

                # Deactivate contract
                cursor.execute("UPDATE contracts SET is_active = 0 WHERE contract_id = ?;", (contract_id,))

                settled_count += 1

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

        return {
            "expiry_date": expiry_date,
            "contracts_settled": settled_count,
            "net_payout_amount": round(total_payout, 2)
        }
