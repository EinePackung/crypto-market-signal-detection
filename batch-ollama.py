#!/usr/bin/env python
#
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "langchain-ollama>=0.1.0",
#     "pandas>=2.0.0",
# ]
# ///
import json
import argparse
import time
from itertools import zip_longest
from pathlib import Path

import pandas as pd
from langchain_ollama import OllamaLLM

from evaluation import evaluate_result_file


COINS = ["btc", "doge", "eth"]
MAX_RUNTIME_SECONDS = 2 * 60 * 60
MAX_RETRIES = 3
TEST_DATASET_PATH = Path("data/TEST_DATASET_LLM_RESULT.JSON")
TEST_RESULT_PATH = Path("results/TEST_LLM_RESULT.csv")

MIN_FOLLOWERS = 100000
MIN_LIKES = 100
MIN_RETWEETS = 50
MIN_REPLIES = 5

HIGH_FOLLOWERS = 1000000
HIGH_LIKES = 250
HIGH_RETWEETS = 200
HIGH_REPLIES = 25

prompt_path = "prompts/predict_signal_v5.md"
with open(prompt_path) as default_prompt_file:
    prompt_template = default_prompt_file.read()

llm = OllamaLLM(
    model="llama3.1",
    base_url="http://10.0.100.10:11434",
    format="json",
    temperature=0,
    num_predict=200
)


def get_popularity_label(row):
    low_popularity = (
        row["Follower_count"] < MIN_FOLLOWERS
        and row["likes_count"] < MIN_LIKES
        and row["retweets_count"] < MIN_RETWEETS
        and row["replies_count"] < MIN_REPLIES
    )

    if low_popularity:
        return "EXCLUDE"

    high_attention = (
        row["Follower_count"] >= HIGH_FOLLOWERS
        or row["likes_count"] >= HIGH_LIKES
        or row["retweets_count"] >= HIGH_RETWEETS
        or row["replies_count"] >= HIGH_REPLIES
    )

    if high_attention:
        return "HIGH_ATTENTION"

    return "NORMAL"


def normalize_signal(signal):
    signal = str(signal).upper().strip()

    if signal in ("BUYSIGNAL", "BUY SIGNAL", "BU", "B"):
        return "BUY"
    elif signal in ("SELLSIGNAL", "SELL SIGNAL", "SEL", "SE", "S"):
        return "SELL"
    elif signal not in ("BUY", "SELL", "NEUTRAL"):
        return "NEUTRAL"

    return signal


def build_tasks():
    # Use small files first and alternate coins to maximize completed CSV files.
    files_by_coin = {}

    for coin in COINS:
        tweet_folder = Path(f"data/CrypTop12-main/tweet/raw/{coin}")
        price_path = Path(f"data/CrypTop12-main/price/raw/{coin}.csv")
        prices = pd.read_csv(price_path).sort_values("Date").reset_index(drop=True)
        valid_dates = set(prices.iloc[:-1]["Date"].astype(str))
        coin_files = [
            path for path in tweet_folder.glob("*.json")
            if path.stem in valid_dates
        ]
        files_by_coin[coin] = sorted(coin_files, key=lambda path: path.stat().st_size)

    tasks = []
    for group in zip_longest(*(files_by_coin[coin] for coin in COINS)):
        for coin, path in zip(COINS, group):
            if path is not None:
                tasks.append((coin, path))

    return tasks


def get_output_paths(coin, input_path):
    date_name = input_path.stem.replace("-", "_")
    output_folder = Path(f"results/ollama_response/{coin}")
    output_folder.mkdir(parents=True, exist_ok=True)
    output_path = output_folder / f"{date_name}_with_prompt_v5_popularity_filtered.csv"
    partial_path = output_folder / f"{date_name}_with_prompt_v5_popularity_filtered.partial.csv"
    return output_path, partial_path


def process_tweet(row, coin):
    tweet_id = str(row.get("id_str", row.get("id", "")))
    username = str(row["username"])
    tweet_text = str(row["tweet"])
    upload_date = str(row["created_at"])

    prompt = prompt_template.format(
        username=username,
        tweet_text=tweet_text,
        coin=coin.upper(),
        upload_date=upload_date,
        retweets_count=str(row["retweets_count"]),
        likes_count=str(row["likes_count"]),
        follwers_count=str(row["Follower_count"]),
        replies_count=str(row["replies_count"])
    )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = llm.invoke(prompt)
            parsed = json.loads(response)
            signal = normalize_signal(parsed.get("signal"))
            ticker = str(parsed.get("ticker", "")).upper().strip()

            if ticker != coin.upper():
                ticker = coin.upper()

            return {
                "tweet_id": tweet_id,
                "text": tweet_text,
                "signal": signal,
                "confidence": parsed.get("confidence"),
                "reason": parsed.get("reason"),
                "ticker": ticker,
                "username": username,
                "created_at": upload_date,
                "retweets_count": row["retweets_count"],
                "likes_count": row["likes_count"],
                "followers_count": row["Follower_count"],
                "replies_count": row["replies_count"],
                "popularity_label": row["popularity_label"]
            }
        except Exception as error:
            last_error = error
            print(f"retry {attempt}/{MAX_RETRIES}: {error}", flush=True)
            time.sleep(3)

    raise RuntimeError(last_error)


def process_file(coin, input_path):
    output_path, partial_path = get_output_paths(coin, input_path)

    if output_path.exists():
        evaluate_result_file(coin, output_path)
        return True

    df = pd.read_json(input_path, lines=True)
    df["popularity_label"] = df.apply(get_popularity_label, axis=1)
    df = df[df["popularity_label"] != "EXCLUDE"].copy()

    if df.empty:
        print(f"skip empty filtered file: {input_path}", flush=True)
        return True

    results = []
    completed_ids = set()

    if partial_path.exists():
        partial_results = pd.read_csv(partial_path)
        results = partial_results.to_dict("records")
        completed_ids = set(partial_results["tweet_id"].astype(str))

    print(
        f"start {coin.upper()} {input_path.stem}: "
        f"{len(df)} tweets, {len(completed_ids)} resumed",
        flush=True
    )

    for index, row in df.iterrows():
        tweet_id = str(row.get("id_str", row.get("id", "")))
        if tweet_id in completed_ids:
            continue

        try:
            result = process_tweet(row, coin)
            results.append(result)
            completed_ids.add(tweet_id)
        except Exception as error:
            pd.DataFrame(results).to_csv(partial_path, index=False)
            print(f"pause file after model error: {input_path} - {error}", flush=True)
            return False

        if len(results) % 5 == 0:
            pd.DataFrame(results).to_csv(partial_path, index=False)

        print(
            f"{coin.upper()} {input_path.stem}: {len(completed_ids)}/{len(df)}",
            flush=True
        )

    pd.DataFrame(results).to_csv(partial_path, index=False)
    partial_path.replace(output_path)
    evaluate_result_file(coin, output_path)
    return True


def process_test_dataset(input_path=TEST_DATASET_PATH, output_path=TEST_RESULT_PATH):
    df = pd.read_json(input_path, lines=True)
    results = []

    print(f"start TEST dataset: {len(df)} tweets", flush=True)

    for index, row in df.iterrows():
        row = row.copy()
        if "popularity_label" not in row or pd.isna(row["popularity_label"]):
            row["popularity_label"] = "TEST"

        result = process_tweet(row, "btc")
        result["source_index"] = int(index) + 1
        results.append(result)

        print(f"TEST: {len(results)}/{len(df)}", flush=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(results).to_csv(output_path, index=False)
    print(f"save complete: {output_path}", flush=True)
    return True


def run_batch():
    start_time = time.time()
    tasks = build_tasks()
    completed_files = 0

    print(f"batch start: {len(tasks)} available files", flush=True)

    for coin, input_path in tasks:
        if time.time() - start_time >= MAX_RUNTIME_SECONDS:
            break

        if process_file(coin, input_path):
            completed_files += 1

    elapsed_minutes = (time.time() - start_time) / 60
    print(
        f"batch finished: {completed_files} files in {elapsed_minutes:.1f} minutes",
        flush=True
    )


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run data/TEST_DATASET_LLM_RESULT.JSON and save results/TEST_LLM_RESULT.csv.",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    if args.test:
        process_test_dataset()
    else:
        run_batch()
