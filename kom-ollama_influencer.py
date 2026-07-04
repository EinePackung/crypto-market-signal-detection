#!/usr/bin/env python
#
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "langchain-ollama>=0.1.0",
#     "requests>=2.31.0",
# ]
# ///
import json
from pathlib import Path

import pandas as pd
from langchain_ollama import OllamaLLM

# 1. Configure the Ollama instance
# Note: We must include http:// for the base_url
# Outputs must be in Json
llm = OllamaLLM(
    model="llama3.1",
    base_url="http://10.0.100.10:11434",
    format="json"
)

# 2. Load prompt
prompt_path = "prompts/minute_base_predigt_prompt_v1.md"
with open(prompt_path) as default_prompt_file:
    prompt_template = default_prompt_file.read()

# 3. Data load from local
datasets = [
    {
        "coin": "BTC",
        "path": "data/BTC influencer tweets.csv",
        "dataset_type": "influencer_csv"
    },
    {
        "coin": "ETH",
        "path": "data/ETH influencer tweets.csv",
        "dataset_type": "influencer_csv"
    },
    {
        "coin": "SOL",
        "path": "data/SOL influencer tweets.csv",
        "dataset_type": "influencer_csv"
    },
    {
        "coin": "DOGE",
        "path": "data/Elon Musk Tweets/all_musk_posts.csv",
        "dataset_type": "elon_musk_csv"
    },
]
result_root = Path("results/ollama-response_influencer")


def check_response_coin_related(value):
    if value == "true":
        return True
    if value == "false":
        return False
    if isinstance(value, bool):
        return value
    # Convert to string, remove surrounding spaces, and compare in lowercase.
    value = str(value).strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    return False


def check_response_impact_strength(value):
    try:
        impact_strength = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, impact_strength))


def check_response_confidence(value):
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, confidence))


def get_tweet_data(row, dataset_type):
    if dataset_type == "elon_musk_csv":
        return {
            "username": "elonmusk",
            "influencer_name": "Elon Musk",
            "tweet_text": str(row["fullText"]),
            "upload_date": str(row["createdAt"]),
            "tweet_id": str(row.get("id", "")),
            "tweet_url": str(row.get("url", row.get("twitterUrl", ""))),
        }
    return {
        "username": str(row["handle"]),
        "influencer_name": str(row.get("influencer_name", "")),
        "tweet_text": str(row["tweet"]),
        "upload_date": str(row["created_at_utc"]),
        "tweet_id": str(row.get("tweet_id", "")),
        "tweet_url": str(row.get("tweet_url", "")),
    }


def load_saved_results(save_path):
    if not save_path.exists() or save_path.stat().st_size == 0:
        return []
    try:
        saved_df = pd.read_csv(save_path)
    except pd.errors.EmptyDataError:
        return []
    return saved_df.to_dict("records")


# 4. Input into the LLM
for dataset in datasets:
    coin = dataset["coin"]
    datasets_path = dataset["path"]
    dataset_type = dataset["dataset_type"]
    consecutive_errors = 0
    save_dir = result_root / coin
    save_dir.mkdir(parents=True, exist_ok=True)
    save_path = save_dir / f"{coin}_minute_base_llm_result.csv"
    df = pd.read_csv(datasets_path, low_memory=False)
    results = load_saved_results(save_path)
    completed_rows = set()
    for saved_row in results:
        try:
            completed_rows.add(int(saved_row["source_row_number"]))
        except (KeyError, TypeError, ValueError):
            pass

    print(f"start {coin}: {datasets_path} ({len(df)} tweets)")
    if completed_rows:
        print(f"resume {coin}: {len(completed_rows)} tweets already saved")

    for index, row in df.iterrows():
        source_row_number = index + 1
        if source_row_number in completed_rows:
            continue

        tweet_data = get_tweet_data(row, dataset_type)
        username_from_datasets = tweet_data["username"]
        influencer_name_from_datasets = tweet_data["influencer_name"]
        tweet_text_from_datasets = tweet_data["tweet_text"]
        upload_date_from_datasets = tweet_data["upload_date"]
        tweet_id_from_datasets = tweet_data["tweet_id"]
        tweet_url_from_datasets = tweet_data["tweet_url"]

        prompt = prompt_template.format(
            username=username_from_datasets,
            tweet_text=tweet_text_from_datasets,
            coin=coin,
            upload_date=upload_date_from_datasets
        )

        try:
            response = llm.invoke(prompt)
            parsed = json.loads(response)
            consecutive_errors = 0

            # Correct wrong response like BUYSIGNAL instead of BUY
            signal = parsed.get("signal")
            signal = str(signal).upper().strip()
            if signal == "BUYSIGNAL" or signal == "BUY SIGNAL" or signal == "BU" or signal == "B":
                signal = "BUY"
            if signal == "SELLSIGNAL" or signal == "SELL SIGNAL" or signal == "SEL" or signal == "SE" or signal == "S":
                signal = "SELL"
            if signal not in ("BUY", "SELL", "NEUTRAL"):
                signal = "NEUTRAL"

            ticker = parsed.get("ticker")
            if ticker != coin:
                ticker = coin

            is_tweet_related_to_coin = check_response_coin_related(parsed.get("is_tweet_related_to_coin"))
            impact_strength = check_response_impact_strength(parsed.get("impact_strength"))
            confidence = check_response_confidence(parsed.get("confidence"))

            if index == 0 or (index + 1) % 50 == 0:
                print(f"{coin} tweet #{index + 1}: {tweet_text_from_datasets[:80]}...")
            results.append({
                "coin": coin,
                "source_dataset": datasets_path,
                "source_row_number": source_row_number,
                "tweet_id": tweet_id_from_datasets,
                "tweet_url": tweet_url_from_datasets,
                "text": tweet_text_from_datasets,
                "is_tweet_related_to_coin": is_tweet_related_to_coin,
                "signal": signal,
                "impact_strength": impact_strength,
                "confidence": confidence,
                "reason": parsed.get("reason"),
                "ticker": ticker,
                "username": username_from_datasets,
                "influencer_name": influencer_name_from_datasets,
                "created_at_utc": upload_date_from_datasets
            })
            if len(results) % 10 == 0:
                pd.DataFrame(results).to_csv(save_path, index=False)

        except Exception as e:
            print(f"Error connecting to Ollama for {coin} tweet #{index + 1}: {e}")
            consecutive_errors += 1
            if consecutive_errors >= 5:
                pd.DataFrame(results).to_csv(save_path, index=False)
                raise SystemExit(f"Stopped after {consecutive_errors} consecutive Ollama errors.")



    # 5. Save the result
    pd.DataFrame(results).to_csv(save_path, index=False)
    print(f"save complete: {save_path}")
