#!/usr/bin/env python3
"""
Clean an NSE F&O volatility CSV file.

Default input:
    F&O Vola_tility Raw.csv

Default output:
    F&O Vola_tility Cleaned.csv

Cleaning performed:
1. Strips leading/trailing whitespace from headers and values.
2. Converts common missing-value tokens (nan, null, NA, etc.) to blank.
3. Normalizes EXP_DATE from DD/MM/YYYY to YYYY-MM-DD.
4. Converts numeric columns to clean numeric text.
5. Removes rows missing SYMBOL or EXP_DATE because they cannot be reliably identified.
6. Removes exact duplicate records after normalization.
7. Removes rows with invalid/non-sensical OHLC relationships.
8. Writes a cleaning report to the terminal.

No missing market values are invented or imputed.
"""

from pathlib import Path
import argparse
import csv
from datetime import datetime
from decimal import Decimal, InvalidOperation


MISSING_TOKENS = {
    "", "nan", "na", "n/a", "null", "none", "-", "--", "nat"
}

COLUMN_ALIASES = {
    "INSTRUMENT": "INSTRUMENT",
    "SYMBOL": "SYMBOL",
    "EXP_DATE": "EXP_DATE",
    "OPEN_PRICE": "OPEN_PRICE",
    "HI_PRICE": "HI_PRICE",
    "LO_PRICE": "LO_PRICE",
    "CLOSE_PRICE": "CLOSE_PRICE",
    "OPEN_INT": "OPEN_INT",
    "TRD_VAL": "TRD_VAL",
    "TRD_QTY": "TRD_QTY",
    "NO_OF_CONT": "NO_OF_CONT",
    "NO_OF_TRADE": "NO_OF_TRADE",
}

NUMERIC_COLUMNS = {
    "OPEN_PRICE",
    "HI_PRICE",
    "LO_PRICE",
    "CLOSE_PRICE",
    "OPEN_INT",
    "TRD_VAL",
    "TRD_QTY",
    "NO_OF_CONT",
    "NO_OF_TRADE",
}

REQUIRED_COLUMNS = {"SYMBOL", "EXP_DATE"}


def normalize_header(name: str) -> str:
    name = name.replace("\ufeff", "").strip().upper()
    name = name.replace("*", "")
    name = "_".join(name.split())
    return COLUMN_ALIASES.get(name, name)


def clean_text(value) -> str:
    if value is None:
        return ""
    value = str(value).strip()
    if value.lower() in MISSING_TOKENS:
        return ""
    return value


def clean_decimal(value) -> str:
    value = clean_text(value)
    if value == "":
        return ""

    value = value.replace(",", "")
    try:
        number = Decimal(value)
    except InvalidOperation as exc:
        raise ValueError(f"Invalid numeric value: {value!r}") from exc

    if not number.is_finite():
        raise ValueError(f"Non-finite numeric value: {value!r}")

    # Avoid unnecessary trailing zeros while preserving exact decimal value.
    text = format(number, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def clean_date(value) -> str:
    value = clean_text(value)
    if value == "":
        return ""

    # Expected source format is DD/MM/YYYY.
    try:
        dt = datetime.strptime(value, "%d/%m/%Y")
    except ValueError as exc:
        raise ValueError(f"Invalid date: {value!r}") from exc

    return dt.strftime("%Y-%m-%d")


def row_is_valid_ohlc(row: dict) -> bool:
    values = []
    for col in ("OPEN_PRICE", "HI_PRICE", "LO_PRICE", "CLOSE_PRICE"):
        if row[col] == "":
            return True  # Do not reject rows just because values are missing.
        values.append(Decimal(row[col]))

    o, h, l, c = values
    return h >= max(o, l, c) and l <= min(o, h, c) and h >= l and min(o, h, l, c) >= 0


def clean_file(input_file: Path, output_file: Path) -> dict:
    stats = {
        "input_rows": 0,
        "output_rows": 0,
        "dropped_missing_key": 0,
        "dropped_duplicates": 0,
        "dropped_bad_ohlc": 0,
        "bad_numeric_rows": 0,
        "bad_date_rows": 0,
    }

    cleaned_rows = []
    seen = set()

    with input_file.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        raw_header = next(reader)
        header = [normalize_header(h) for h in raw_header]

        # Ensure required columns exist.
        missing_required = REQUIRED_COLUMNS - set(header)
        if missing_required:
            raise ValueError(
                f"Missing required columns: {', '.join(sorted(missing_required))}"
            )

        for raw_row in reader:
            if not any(clean_text(x) for x in raw_row):
                continue

            stats["input_rows"] += 1

            row = {}
            for i, col in enumerate(header):
                raw_value = raw_row[i] if i < len(raw_row) else ""
                row[col] = clean_text(raw_value)

            # Normalize dates.
            try:
                row["EXP_DATE"] = clean_date(row["EXP_DATE"])
            except ValueError:
                stats["bad_date_rows"] += 1
                continue

            # Normalize numeric columns.
            bad_numeric = False
            for col in NUMERIC_COLUMNS:
                try:
                    row[col] = clean_decimal(row[col])
                except ValueError:
                    bad_numeric = True
                    break

            if bad_numeric:
                stats["bad_numeric_rows"] += 1
                continue

            # Drop records that cannot be identified reliably.
            if row["SYMBOL"] == "" or row["EXP_DATE"] == "":
                stats["dropped_missing_key"] += 1
                continue

            # Drop impossible OHLC rows, if all four prices are available.
            if not row_is_valid_ohlc(row):
                stats["dropped_bad_ohlc"] += 1
                continue

            # Deduplicate after cleaning/normalization.
            key = tuple(row.get(col, "") for col in header)
            if key in seen:
                stats["dropped_duplicates"] += 1
                continue

            seen.add(key)
            cleaned_rows.append(row)

    # Preserve original column order, but use cleaned names.
    with output_file.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        writer.writerows(cleaned_rows)

    stats["output_rows"] = len(cleaned_rows)
    return stats


def main():
    parser = argparse.ArgumentParser(description="Clean an NSE F&O CSV dataset.")
    parser.add_argument(
        "input",
        nargs="?",
        default="F&O Vola_tility Raw.csv",
        help="Input CSV file",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="F&O Vola_tility Cleaned.csv",
        help="Output CSV file",
    )
    args = parser.parse_args()

    input_file = Path(args.input)
    output_file = Path(args.output)

    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    stats = clean_file(input_file, output_file)

    print("\nCleaning completed")
    print("-" * 40)
    for key, value in stats.items():
        print(f"{key:24}: {value}")
    print(f"\nSaved cleaned file to: {output_file.resolve()}")


if __name__ == "__main__":
    main()
