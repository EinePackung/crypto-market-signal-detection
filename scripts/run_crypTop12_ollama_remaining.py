#!/usr/bin/env python3
"""Run remaining CrypTop12 tweets through Ollama and save response CSVs.

This runner intentionally only creates files under results/ollama_response.
It skips final CSVs that already exist and resumes from .partial.csv files.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from itertools import zip_longest
from pathlib import Path

import pandas as pd
from langchain_ollama import OllamaLLM


ROOT = Path(__file__).resolve().parents[1]
PROMPT_PATH = ROOT / "prompts" / "predict_signal_v5.md"
RAW_ROOT = ROOT / "data" / "CrypTop12-main" / "tweet" / "raw"
OUTPUT_ROOT = ROOT / "results" / "ollama_response"

MIN_FOLLOWERS = 100000
MIN_LIKES = 100
MIN_RETWEETS = 50
MIN_REPLIES = 5

HIGH_FOLLOWERS = 1000000
HIGH_LIKES = 250
HIGH_RETWEETS = 200
HIGH_REPLIES = 25

MAX_RETRIES = 3
DEFAULT_COINS = ("btc", "eth", "doge")


def numeric(value) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def get_popularity_label(row: pd.Series) -> str:
    low_popularity = (
        numeric(row["Follower_count"]) < MIN_FOLLOWERS
        and numeric(row["likes_count"]) < MIN_LIKES
        and numeric(row["retweets_count"]) < MIN_RETWEETS
        and numeric(row["replies_count"]) < MIN_REPLIES
    )
    if low_popularity:
        return "EXCLUDE"

    high_attention = (
        numeric(row["Follower_count"]) >= HIGH_FOLLOWERS
        or numeric(row["likes_count"]) >= HIGH_LIKES
        or numeric(row["retweets_count"]) >= HIGH_RETWEETS
        or numeric(row["replies_count"]) >= HIGH_REPLIES
    )
    return "HIGH_ATTENTION" if high_attention else "NORMAL"


def normalize_signal(signal) -> str:
    signal = str(signal).upper().strip()
    if signal in ("BUYSIGNAL", "BUY SIGNAL", "BU", "B"):
        return "BUY"
    if signal in ("SELLSIGNAL", "SELL SIGNAL", "SEL", "SE", "S"):
        return "SELL"
    if signal not in ("BUY", "SELL", "NEUTRAL"):
        return "NEUTRAL"
    return signal


def output_paths(coin: str, input_path: Path) -> tuple[Path, Path]:
    date_name = input_path.stem.replace("-", "_")
    folder = OUTPUT_ROOT / coin
    folder.mkdir(parents=True, exist_ok=True)
    output_path = folder / f"{date_name}_with_prompt_v5_popularity_filtered.csv"
    partial_path = folder / f"{date_name}_with_prompt_v5_popularity_filtered.partial.csv"
    return output_path, partial_path


def build_tasks(coins: tuple[str, ...]) -> list[tuple[str, Path]]:
    files_by_coin: dict[str, list[Path]] = {}
    for coin in coins:
        coin_dir = RAW_ROOT / coin
        files = sorted(coin_dir.glob("*.json"), key=lambda path: path.stat().st_size)
        files_by_coin[coin] = files

    tasks: list[tuple[str, Path]] = []
    for group in zip_longest(*(files_by_coin[coin] for coin in coins)):
        for coin, path in zip(coins, group):
            if path is not None:
                tasks.append((coin, path))
    return tasks


def process_tweet(row: pd.Series, coin: str, llm: OllamaLLM, prompt_template: str) -> dict:
    tweet_id = str(row.get("id_str", row.get("id", "")))
    prompt = prompt_template.format(
        username=str(row["username"]),
        tweet_text=str(row["tweet"]),
        coin=coin.upper(),
        upload_date=str(row["created_at"]),
        retweets_count=str(row["retweets_count"]),
        likes_count=str(row["likes_count"]),
        follwers_count=str(row["Follower_count"]),
        replies_count=str(row["replies_count"]),
    )

    last_error: Exception | None = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            parsed = json.loads(llm.invoke(prompt))
            ticker = str(parsed.get("ticker", "")).upper().strip()
            if ticker != coin.upper():
                ticker = coin.upper()
            return {
                "tweet_id": tweet_id,
                "text": str(row["tweet"]),
                "signal": normalize_signal(parsed.get("signal")),
                "confidence": parsed.get("confidence"),
                "reason": parsed.get("reason"),
                "ticker": ticker,
                "username": str(row["username"]),
                "created_at": str(row["created_at"]),
                "retweets_count": row["retweets_count"],
                "likes_count": row["likes_count"],
                "followers_count": row["Follower_count"],
                "replies_count": row["replies_count"],
                "popularity_label": row["popularity_label"],
            }
        except Exception as error:  # noqa: BLE001 - keep batch resilient.
            last_error = error
            print(f"retry {attempt}/{MAX_RETRIES}: {error}", flush=True)
            time.sleep(3)
    raise RuntimeError(last_error)


def process_file(
    coin: str,
    input_path: Path,
    llm: OllamaLLM,
    prompt_template: str,
    deadline: float | None,
    max_tweets: int | None,
    processed_counter: list[int],
) -> bool:
    output_path, partial_path = output_paths(coin, input_path)
    if output_path.exists():
        return True

    df = pd.read_json(input_path, lines=True)
    df["popularity_label"] = df.apply(get_popularity_label, axis=1)
    df = df[df["popularity_label"] != "EXCLUDE"].copy()
    if df.empty:
        return True

    results: list[dict] = []
    completed_ids: set[str] = set()
    if partial_path.exists():
        partial = pd.read_csv(partial_path)
        results = partial.to_dict("records")
        completed_ids = set(partial["tweet_id"].astype(str))

    print(
        f"start {coin.upper()} {input_path.stem}: "
        f"{len(df)} tweets, {len(completed_ids)} resumed",
        flush=True,
    )

    for _, row in df.iterrows():
        if deadline is not None and time.time() >= deadline:
            pd.DataFrame(results).to_csv(partial_path, index=False)
            return False
        if max_tweets is not None and processed_counter[0] >= max_tweets:
            pd.DataFrame(results).to_csv(partial_path, index=False)
            return False

        tweet_id = str(row.get("id_str", row.get("id", "")))
        if tweet_id in completed_ids:
            continue

        result = process_tweet(row, coin, llm, prompt_template)
        results.append(result)
        completed_ids.add(tweet_id)
        processed_counter[0] += 1

        if len(results) % 5 == 0:
            pd.DataFrame(results).to_csv(partial_path, index=False)

        print(
            f"{coin.upper()} {input_path.stem}: {len(completed_ids)}/{len(df)} "
            f"session_processed={processed_counter[0]}",
            flush=True,
        )

    pd.DataFrame(results).to_csv(partial_path, index=False)
    partial_path.replace(output_path)
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--coins", nargs="+", default=list(DEFAULT_COINS))
    parser.add_argument("--max-runtime-seconds", type=int, default=0)
    parser.add_argument("--max-tweets", type=int, default=0)
    parser.add_argument("--base-url", default="http://10.0.100.10:11434")
    parser.add_argument("--model", default="llama3.1")
    parser.add_argument("--daemon", action="store_true")
    parser.add_argument(
        "--log-path",
        default=str(OUTPUT_ROOT / "crypTop12_full_run.log"),
    )
    parser.add_argument(
        "--pid-path",
        default=str(OUTPUT_ROOT / "crypTop12_full_run.pid"),
    )
    args = parser.parse_args()

    coins = tuple(coin.lower() for coin in args.coins)

    if args.daemon:
        command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "--coins",
            *coins,
            "--max-runtime-seconds",
            str(args.max_runtime_seconds),
            "--max-tweets",
            str(args.max_tweets),
            "--base-url",
            args.base_url,
            "--model",
            args.model,
        ]
        log_path = Path(args.log_path)
        pid_path = Path(args.pid_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_file = log_path.open("a", encoding="utf-8")
        process = subprocess.Popen(
            command,
            cwd=ROOT,
            stdout=log_file,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        pid_path.write_text(f"{process.pid}\n", encoding="utf-8")
        print(f"started pid={process.pid}")
        print(f"log={log_path}")
        print(f"pid_file={pid_path}")
        return 0

    prompt_template = PROMPT_PATH.read_text(encoding="utf-8")
    llm = OllamaLLM(
        model=args.model,
        base_url=args.base_url,
        format="json",
        temperature=0,
        num_predict=200,
    )
    deadline = time.time() + args.max_runtime_seconds if args.max_runtime_seconds else None
    max_tweets = args.max_tweets or None
    processed_counter = [0]

    tasks = build_tasks(coins)
    print(f"batch start: {len(tasks)} files coins={','.join(coins)}", flush=True)
    start = time.time()
    completed_files = 0
    for coin, input_path in tasks:
        ok = process_file(
            coin,
            input_path,
            llm,
            prompt_template,
            deadline,
            max_tweets,
            processed_counter,
        )
        if ok:
            completed_files += 1
        else:
            break

    elapsed = time.time() - start
    print(
        f"batch finished: files_completed_or_skipped={completed_files} "
        f"new_tweets={processed_counter[0]} elapsed_seconds={elapsed:.1f}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
