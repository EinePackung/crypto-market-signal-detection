#!/usr/bin/env python3
"""Rebuild selected BTC/ETH influencer tweet CSVs from documented sources.

This script documents the provenance for:
  - data/BTC influencer tweets.csv
  - data/ETH influencer tweets.csv

The main source is CrypTop12 JSONL under data/CrypTop12-main/tweet/raw.
BTC also has two Nayib Bukele rows that were manually verified from
data/Bitcoin Tweets/Bitcoin_tweets.csv because CrypTop12 does not provide
matching @nayibbukele rows.

Default mode prints a summary without changing files:
  python3 scripts/extract_selected_influencer_tweets.py

To regenerate the CSV files:
  python3 scripts/extract_selected_influencer_tweets.py --write
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_RAW_ROOT = PROJECT_ROOT / "data" / "CrypTop12-main" / "tweet" / "raw"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data"
IST = timezone(timedelta(hours=5, minutes=30))

CSV_COLUMNS = [
    "influencer_group",
    "influencer_name",
    "handle",
    "tweet_id",
    "tweet_url",
    "created_at_raw",
    "created_at_utc",
    "tweet",
    "replies_count",
    "retweets_count",
    "likes_count",
    "follower_count",
    "source_dataset_coins",
    "source_files",
]


@dataclass(frozen=True)
class Account:
    group: str
    name: str
    handle: str


SELECTED_ACCOUNTS = [
    Account("BTC", "Michael Saylor", "michael_saylor"),
    Account("BTC", "Jack Dorsey", "jack"),
    Account("BTC", "Nayib Bukele", "nayibbukele"),
    Account("ETH", "Vitalik Buterin", "vitalikbuterin"),
    Account("ETH", "Tim Beiko", "timbeiko"),
    Account("ETH", "Ethereum official", "ethereum"),
    Account("ETH", "ethereum.org", "ethdotorg"),
]

# CrypTop12 has no matching @nayibbukele rows. These two rows are the
# supplementary BTC rows in the current dataset, with their source preserved.
BTC_SUPPLEMENT_ROWS = [
    {
        "influencer_group": "BTC",
        "influencer_name": "Nayib Bukele",
        "handle": "nayibbukele",
        "tweet_id": "",
        "tweet_url": "",
        "created_at_raw": "2022-06-14 19:59:36",
        "created_at_utc": "2022-06-14T19:59:36Z",
        "tweet": "You\u2019re telling me we should buy more #BTC? https://t.co/jwvn0A1kTb",
        "replies_count": "",
        "retweets_count": "",
        "likes_count": "",
        "follower_count": "4009318",
        "source_dataset_coins": "btc",
        "source_files": "data/Bitcoin Tweets/Bitcoin_tweets.csv",
    },
    {
        "influencer_group": "BTC",
        "influencer_name": "Nayib Bukele",
        "handle": "nayibbukele",
        "tweet_id": "",
        "tweet_url": "",
        "created_at_raw": "2022-06-19 03:04:01",
        "created_at_utc": "2022-06-19T03:04:01Z",
        "tweet": (
            "I see that some people are worried or anxious about the #Bitcoin market price.\n\n"
            "My advice: stop looking at the graph and enjoy life. If you invested in #BTC "
            "your investment is safe and its value will immensely grow after the bear market.\n\n"
            "Patience is the key."
        ),
        "replies_count": "",
        "retweets_count": "",
        "likes_count": "",
        "follower_count": "4017517",
        "source_dataset_coins": "btc",
        "source_files": "data/Bitcoin Tweets/Bitcoin_tweets.csv",
    },
]


def rel_path(path: Path) -> str:
    return path.resolve().relative_to(PROJECT_ROOT).as_posix()


def normalize_handle(value: object) -> str:
    return str(value or "").strip().lstrip("@").lower()


def parse_cryp_top12_time(raw_value: str) -> str:
    raw_value = raw_value.strip()
    if raw_value.endswith(" IST"):
        raw_value = raw_value[:-4]
    parsed = datetime.strptime(raw_value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=IST)
    return parsed.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_tweet_id(tweet: dict) -> str:
    value = tweet.get("id_str") or tweet.get("id") or ""
    return str(value)


def build_base_row(account: Account, tweet: dict, source_file: Path, source_coin: str) -> dict:
    tweet_id = get_tweet_id(tweet)
    handle = normalize_handle(tweet.get("username"))
    created_at_raw = str(tweet.get("created_at") or "")
    return {
        "influencer_group": account.group,
        "influencer_name": account.name,
        "handle": handle,
        "tweet_id": tweet_id,
        "tweet_url": f"https://x.com/{handle}/status/{tweet_id}" if tweet_id else "",
        "created_at_raw": created_at_raw,
        "created_at_utc": parse_cryp_top12_time(created_at_raw),
        "tweet": str(tweet.get("tweet") or ""),
        "replies_count": tweet.get("replies_count", ""),
        "retweets_count": tweet.get("retweets_count", ""),
        "likes_count": tweet.get("likes_count", ""),
        "follower_count": tweet.get("Follower_count", ""),
        "source_dataset_coins": source_coin,
        "source_files": rel_path(source_file),
    }


def row_sort_key(row: dict) -> tuple[str, str, str]:
    return (
        str(row.get("created_at_utc") or ""),
        str(row.get("influencer_name") or ""),
        str(row.get("tweet_id") or ""),
    )


def merge_source_fields(row: dict, source_coin: str, source_file: Path) -> None:
    coins = set(filter(None, str(row["source_dataset_coins"]).split(";")))
    files = set(filter(None, str(row["source_files"]).split(";")))
    coins.add(source_coin)
    files.add(rel_path(source_file))
    row["source_dataset_coins"] = ";".join(sorted(coins))
    row["source_files"] = ";".join(sorted(files))


def iter_jsonl(path: Path) -> Iterable[dict]:
    with path.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                yield json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSON in {path}:{line_number}") from exc


def extract_cryp_top12_rows(raw_root: Path, groups: set[str]) -> list[dict]:
    accounts_by_handle = {
        account.handle: account
        for account in SELECTED_ACCOUNTS
        if account.group in groups
    }
    rows_by_key: dict[tuple[str, str], dict] = {}

    for coin_dir in sorted(path for path in raw_root.iterdir() if path.is_dir()):
        source_coin = coin_dir.name.lower()
        for json_path in sorted(coin_dir.glob("*.json")):
            for tweet in iter_jsonl(json_path):
                handle = normalize_handle(tweet.get("username"))
                account = accounts_by_handle.get(handle)
                if account is None:
                    continue

                tweet_id = get_tweet_id(tweet)
                fallback_id = f"{handle}|{tweet.get('created_at', '')}|{tweet.get('tweet', '')}"
                key = (account.group, tweet_id or fallback_id)
                if key in rows_by_key:
                    merge_source_fields(rows_by_key[key], source_coin, json_path)
                else:
                    rows_by_key[key] = build_base_row(account, tweet, json_path, source_coin)

    return sorted(rows_by_key.values(), key=row_sort_key)


def append_btc_supplement(rows: list[dict], groups: set[str], include_supplement: bool) -> list[dict]:
    if "BTC" not in groups or not include_supplement:
        return rows
    dedupe_keys = {
        (
            row.get("influencer_group", ""),
            row.get("handle", ""),
            row.get("tweet_id", ""),
            row.get("created_at_utc", ""),
            row.get("tweet", ""),
        )
        for row in rows
    }
    merged = list(rows)
    for row in BTC_SUPPLEMENT_ROWS:
        key = (
            row["influencer_group"],
            row["handle"],
            row["tweet_id"],
            row["created_at_utc"],
            row["tweet"],
        )
        if key not in dedupe_keys:
            merged.append(row)
    return sorted(merged, key=row_sort_key)


def split_by_group(rows: Iterable[dict]) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row["influencer_group"]].append(row)
    return {group: sorted(group_rows, key=row_sort_key) for group, group_rows in grouped.items()}


def write_group_csvs(rows_by_group: dict[str, list[dict]], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for group, rows in sorted(rows_by_group.items()):
        output_path = output_dir / f"{group} influencer tweets.csv"
        with output_path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        print(f"Wrote {rel_path(output_path)} ({len(rows)} rows)")


def print_summary(rows_by_group: dict[str, list[dict]], output_dir: Path) -> None:
    for group, rows in sorted(rows_by_group.items()):
        print(f"{group}: {len(rows)} rows")
        by_influencer = Counter(row["influencer_name"] for row in rows)
        for name, count in sorted(by_influencer.items()):
            print(f"  {name}: {count}")

        existing_path = output_dir / f"{group} influencer tweets.csv"
        if existing_path.exists():
            with existing_path.open("r", newline="", encoding="utf-8") as file:
                existing_count = sum(1 for _ in csv.DictReader(file))
            status = "MATCH" if existing_count == len(rows) else "DIFF"
            print(f"  existing file: {existing_count} rows ({status})")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract selected BTC/ETH influencer tweets from CrypTop12 raw JSONL."
    )
    parser.add_argument(
        "--groups",
        nargs="+",
        choices=sorted({account.group for account in SELECTED_ACCOUNTS}),
        default=["BTC", "ETH"],
        help="Influencer groups to extract. Defaults to BTC ETH.",
    )
    parser.add_argument(
        "--raw-root",
        type=Path,
        default=DEFAULT_RAW_ROOT,
        help="CrypTop12 raw tweet directory.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
        help="Directory for generated group CSV files.",
    )
    parser.add_argument(
        "--skip-btc-supplement",
        action="store_true",
        help="Do not append the two Nayib Bukele rows from Bitcoin_tweets.csv.",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Write CSV files. Without this flag, only print a summary.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    groups = set(args.groups)
    rows = extract_cryp_top12_rows(args.raw_root, groups)
    rows = append_btc_supplement(
        rows,
        groups=groups,
        include_supplement=not args.skip_btc_supplement,
    )
    rows_by_group = split_by_group(rows)
    print_summary(rows_by_group, args.output_dir)
    if args.write:
        write_group_csvs(rows_by_group, args.output_dir)
    else:
        print("Dry run only. Add --write to regenerate CSV files.")


if __name__ == "__main__":
    main()
