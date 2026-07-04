#!/usr/bin/env python3
"""Add per-minute price-change columns and create BTC average summaries."""

from __future__ import annotations

import csv
from decimal import Decimal, DivisionByZero, InvalidOperation, getcontext
from pathlib import Path


getcontext().prec = 36

ROOT = Path(__file__).resolve().parents[1]
RAW_ROOT = ROOT / "data" / "binance_price_change_per-minute" / "raw"
BTC_SUMMARY_DIR = RAW_ROOT / "BTC" / "average_price_change"

BASE_COLUMNS = [
    "open_time",
    "open_price",
    "high_price",
    "low_price",
    "close_price",
    "volume",
    "close_time",
    "quote_asset_volume",
    "number_of_trades",
    "taker_buy_base_asset_volume",
    "taker_buy_quote_asset_volume",
    "ignore",
]

CHANGE_COLUMNS = [
    "previous_close_price",
    "price_change",
    "absolute_price_change",
    "price_change_rate",
    "absolute_price_change_rate",
]

SUMMARY_COLUMNS = [
    "coin",
    "source_file",
    "period",
    "data_row_count",
    "valid_change_count",
    "average_price_change",
    "average_absolute_price_change",
    "average_price_change_rate",
    "average_absolute_price_change_rate",
]


def parse_decimal(value: str) -> Decimal | None:
    value = (value or "").strip()
    if not value:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def format_decimal(value: Decimal | None) -> str:
    if value is None:
        return ""
    if value == 0:
        return "0"
    text = format(value.normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def month_from_filename(path: Path) -> str:
    # Example: BTCUSDT-1m-2017-12.csv -> 2017-12
    return path.stem.rsplit("-", 2)[-2] + "-" + path.stem.rsplit("-", 2)[-1]


def monthly_summary_row(coin: str, path: Path, rows: list[dict[str, str]]) -> dict[str, str]:
    totals = {
        "price_change": Decimal("0"),
        "absolute_price_change": Decimal("0"),
        "price_change_rate": Decimal("0"),
        "absolute_price_change_rate": Decimal("0"),
    }
    count = 0
    for row in rows:
        price_change = parse_decimal(row.get("price_change", ""))
        absolute_price_change = parse_decimal(row.get("absolute_price_change", ""))
        price_change_rate = parse_decimal(row.get("price_change_rate", ""))
        absolute_price_change_rate = parse_decimal(row.get("absolute_price_change_rate", ""))
        if (
            price_change is None
            or absolute_price_change is None
            or price_change_rate is None
            or absolute_price_change_rate is None
        ):
            continue
        totals["price_change"] += price_change
        totals["absolute_price_change"] += absolute_price_change
        totals["price_change_rate"] += price_change_rate
        totals["absolute_price_change_rate"] += absolute_price_change_rate
        count += 1

    def avg(key: str) -> Decimal | None:
        return totals[key] / count if count else None

    return {
        "coin": coin,
        "source_file": str(path.relative_to(ROOT)),
        "period": month_from_filename(path),
        "data_row_count": str(len(rows)),
        "valid_change_count": str(count),
        "average_price_change": format_decimal(avg("price_change")),
        "average_absolute_price_change": format_decimal(avg("absolute_price_change")),
        "average_price_change_rate": format_decimal(avg("price_change_rate")),
        "average_absolute_price_change_rate": format_decimal(avg("absolute_price_change_rate")),
    }


def add_change_columns(path: Path) -> tuple[str, list[dict[str, str]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames:
            raise ValueError(f"Missing header in {path}")
        existing_columns = reader.fieldnames
        rows = list(reader)

    missing_base = [column for column in BASE_COLUMNS if column not in existing_columns]
    if missing_base:
        raise ValueError(f"{path} is missing required columns: {missing_base}")

    fieldnames = [column for column in existing_columns if column not in CHANGE_COLUMNS]
    fieldnames.extend(CHANGE_COLUMNS)

    previous_close: Decimal | None = None
    for row in rows:
        close_price = parse_decimal(row.get("close_price", ""))
        if close_price is None or previous_close is None:
            row["previous_close_price"] = ""
            row["price_change"] = ""
            row["absolute_price_change"] = ""
            row["price_change_rate"] = ""
            row["absolute_price_change_rate"] = ""
        else:
            price_change = close_price - previous_close
            absolute_price_change = abs(price_change)
            try:
                price_change_rate = price_change / previous_close
            except (DivisionByZero, InvalidOperation):
                price_change_rate = None
            absolute_price_change_rate = abs(price_change_rate) if price_change_rate is not None else None

            row["previous_close_price"] = format_decimal(previous_close)
            row["price_change"] = format_decimal(price_change)
            row["absolute_price_change"] = format_decimal(absolute_price_change)
            row["price_change_rate"] = format_decimal(price_change_rate)
            row["absolute_price_change_rate"] = format_decimal(absolute_price_change_rate)

        if close_price is not None:
            previous_close = close_price

    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    tmp.replace(path)

    return path.parent.name, rows


def write_summary(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=SUMMARY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    raw_files = []
    for coin_dir in sorted(path for path in RAW_ROOT.iterdir() if path.is_dir()):
        for path in sorted(coin_dir.glob("*.csv")):
            raw_files.append(path)

    btc_monthly_rows = []
    updated_count = 0

    for path in raw_files:
        coin, rows = add_change_columns(path)
        updated_count += 1
        if coin == "BTC":
            summary = monthly_summary_row("BTC", path, rows)
            btc_monthly_rows.append(summary)
            monthly_name = f"{path.stem}_average_price_change.csv"
            write_summary(BTC_SUMMARY_DIR / monthly_name, [summary])

    btc_overall_totals = {
        "price_change": Decimal("0"),
        "absolute_price_change": Decimal("0"),
        "price_change_rate": Decimal("0"),
        "absolute_price_change_rate": Decimal("0"),
    }
    btc_total_rows = 0
    btc_total_valid_changes = 0
    for row in btc_monthly_rows:
        valid_count = int(row["valid_change_count"])
        btc_total_rows += int(row["data_row_count"])
        btc_total_valid_changes += valid_count
        for avg_column, total_key in [
            ("average_price_change", "price_change"),
            ("average_absolute_price_change", "absolute_price_change"),
            ("average_price_change_rate", "price_change_rate"),
            ("average_absolute_price_change_rate", "absolute_price_change_rate"),
        ]:
            avg_value = parse_decimal(row[avg_column])
            if avg_value is not None:
                btc_overall_totals[total_key] += avg_value * valid_count

    def overall_avg(key: str) -> Decimal | None:
        return btc_overall_totals[key] / btc_total_valid_changes if btc_total_valid_changes else None

    if btc_monthly_rows:
        overall_row = {
            "coin": "BTC",
            "source_file": "data/binance_price_change_per-minute/raw/BTC/*.csv",
            "period": f"{btc_monthly_rows[0]['period']}_to_{btc_monthly_rows[-1]['period']}",
            "data_row_count": str(btc_total_rows),
            "valid_change_count": str(btc_total_valid_changes),
            "average_price_change": format_decimal(overall_avg("price_change")),
            "average_absolute_price_change": format_decimal(overall_avg("absolute_price_change")),
            "average_price_change_rate": format_decimal(overall_avg("price_change_rate")),
            "average_absolute_price_change_rate": format_decimal(overall_avg("absolute_price_change_rate")),
        }
        write_summary(BTC_SUMMARY_DIR / "BTC_average_price_change_entire_time_period.csv", [overall_row])
        write_summary(BTC_SUMMARY_DIR / "BTC_monthly_average_price_change_summary.csv", btc_monthly_rows)

    print(f"updated_raw_files={updated_count}")
    print(f"btc_monthly_summary_files={len(btc_monthly_rows)}")
    print(f"btc_summary_dir={BTC_SUMMARY_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
