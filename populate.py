#!/usr/bin/env python3
"""Generate MySQL data.sql using the two cleaned source datasets."""

import csv
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).parent
VOLATILITY = ROOT / "Cleaned Datasets" / "F&O Volatility.csv"
DERIVATIVES = ROOT / "Cleaned Datasets" / "F&O Vola_tility.csv"
OUTPUT = ROOT / "data.sql"


def read_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as source:
        return [{str(key).strip(): (value or "").strip() for key, value in row.items()} for row in csv.DictReader(source)]


def quote(value):
    if value is None or str(value).strip() == "":
        return "NULL"
    return "'" + str(value).strip().replace("'", "''") + "'"


def number(value):
    if value is None or str(value).strip() == "":
        return "NULL"
    return str(Decimal(str(value).strip().replace(",", "")))


def sql_date(value, source_format):
    return datetime.strptime(value.strip(), source_format).strftime("%Y-%m-%d")


def main():
    volatility = [row for row in read_rows(VOLATILITY) if row["Symbol"] and row["Date"]]
    derivatives = [row for row in read_rows(DERIVATIVES) if row["SYMBOL"] and row["EXP_DATE"]]
    lines = [
        "-- Generated MySQL data load for the four TAE 2 tables.",
        "USE fno_tae2_db;",
        "-- Disable foreign-key checks only while clearing tables in dependency order.",
        "SET FOREIGN_KEY_CHECKS = 0;",
        "TRUNCATE TABLE data2;",
        "TRUNCATE TABLE data1;",
        "TRUNCATE TABLE data4;",
        "TRUNCATE TABLE data3;",
        "SET FOREIGN_KEY_CHECKS = 1;",
    ]

    data1_rows = []
    data2_rows = []
    for index, row in enumerate(volatility, 1):
        data1_rows.append("({}, {}, {}, {}, {}, {}, {})".format(
            index, quote(sql_date(row["Date"], "%d-%b-%y")), quote(row["Symbol"]),
            number(row["Underlying Close Price (A)"]), number(row["Underlying Previous Day Close Price (B)"]),
            number(row["Futures Close Price (G)"]), number(row["Futures Previous Day Close Price (H)"])))
        data2_rows.append("({}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {})".format(
            index, index, number(row["Underlying Log Returns (C) = LN(A/B)"]),
            number(row["Previous Day Underlying Volatility (D)"]),
            number(row["Current Day Underlying Daily Volatility (E) = Sqrt (0.995*D*D + 0.005* C*C)"]),
            number(row["Underlying Annualised Volatility (F) = E*sqrt(365)"]),
            number(row["Futures Log Returns (I) = LN(G/H)"]), number(row["Previous Day Futures Volatility (J)"]),
            number(row["Current Day Futures Daily Volatility (K) = Sqrt (0.995*J*J + 0.005* I*I)"]),
            number(row["Futures Annualised Volatility (L) = K*sqrt(365)"]),
            number(row["Applicable Daily Volatility (M) = Max (E or K)"]),
            number(row["Applicable Annualised Volatility (N) = Max (F or L)"])))
    lines.append("-- Load source price fields into data1 before its dependent metrics in data2.")
    lines.append("INSERT INTO data1 (data1_id, trade_date, symbol, underlying_close, underlying_previous_close, futures_close, futures_previous_close) VALUES\n" + ",\n".join(data1_rows) + ";")
    lines.append("-- Load calculated returns and daily/annualised volatility measures into data2.")
    lines.append("INSERT INTO data2 (data2_id, data1_id, underlying_log_return, previous_underlying_volatility, current_underlying_daily_volatility, underlying_annualised_volatility, futures_log_return, previous_futures_volatility, current_futures_daily_volatility, futures_annualised_volatility, applicable_daily_volatility, applicable_annualised_volatility) VALUES\n" + ",\n".join(data2_rows) + ";")

    data3_rows = []
    data4_rows = []
    for index, row in enumerate(derivatives, 1):
        data3_rows.append("({}, {}, {}, {}, {}, {}, {}, {}, {})".format(
            index, quote(row["INSTRUMENT"]), quote(row["SYMBOL"]), quote(sql_date(row["EXP_DATE"], "%d/%m/%Y")),
            number(row["OPEN_INT*"]), number(row["TRD_VAL"]), number(row["TRD_QTY"]),
            number(row["NO_OF_CONT"]), number(row["NO_OF_TRADE"])))
        data4_rows.append("({}, {}, {}, {}, {}, {})".format(
            index, index, number(row["OPEN_PRICE"]), number(row["HI_PRICE"]),
            number(row["LO_PRICE"]), number(row["CLOSE_PRICE"])))
    lines.append("-- Load derivative contract, quantity and trading-value fields into data3.")
    lines.append("INSERT INTO data3 (data3_id, instrument, symbol, expiry_date, open_interest, trade_value, trade_quantity, number_of_contracts, number_of_trades) VALUES\n" + ",\n".join(data3_rows) + ";")
    lines.append("-- Load OHLC price details into data4 after its parent contract rows exist.")
    lines.append("INSERT INTO data4 (data4_id, data3_id, open_price, high_price, low_price, close_price) VALUES\n" + ",\n".join(data4_rows) + ";")
    lines.append("-- Generated from {} volatility rows and {} derivative rows.".format(len(volatility), len(derivatives)))
    OUTPUT.write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print("Generated data.sql: {} volatility rows, {} derivative rows".format(len(volatility), len(derivatives)))


if __name__ == "__main__":
    main()