import json
import time
from pathlib import Path

import pandas as pd
from langchain_ollama import OllamaLLM


PROMPT_PATH = Path("prompts/predict_signal_v5.md")
TWEET_FOLDER = Path("data/CrypTop12-main/tweet/raw/doge")
DOGE_PRICE_PATH = Path("data/CrypTop12-main/price/raw/doge.csv")
BTC_PRICE_PATH = Path("data/CrypTop12-main/price/raw/btc.csv")
OUTPUT_FOLDER = Path("results/analysis/elon_musk_doge")
MODEL_RESPONSE_PATH = OUTPUT_FOLDER / "elon_musk_tweets_prompt_v5.csv"
DAILY_EVENTS_PATH = OUTPUT_FOLDER / "elon_musk_daily_events.csv"
TWEET_EVENTS_PATH = OUTPUT_FOLDER / "elon_musk_tweet_events.csv"
SUMMARY_PATH = OUTPUT_FOLDER / "elon_musk_summary.csv"

NEUTRAL_PRICE_THRESHOLD_PERCENT = 1.0
MAX_RETRIES = 3

with open(PROMPT_PATH) as prompt_file:
    prompt_template = prompt_file.read()

llm = OllamaLLM(
    model="llama3.1",
    base_url="http://10.0.100.10:11434",
    format="json",
    temperature=0,
    num_predict=200
)


def normalize_signal(signal):
    signal = str(signal).upper().strip()

    if signal in ("BUYSIGNAL", "BUY SIGNAL", "BU", "B"):
        return "BUY"
    elif signal in ("SELLSIGNAL", "SELL SIGNAL", "SEL", "SE", "S"):
        return "SELL"
    elif signal not in ("BUY", "SELL", "NEUTRAL"):
        return "NEUTRAL"

    return signal


def get_popularity_label(row):
    high_attention = (
        row["Follower_count"] >= 1000000
        or row["likes_count"] >= 250
        or row["retweets_count"] >= 200
        or row["replies_count"] >= 25
    )

    return "HIGH_ATTENTION" if high_attention else "NORMAL"


def load_elon_tweets():
    rows = []

    for input_path in TWEET_FOLDER.glob("*.json"):
        df = pd.read_json(input_path, lines=True)
        df = df[df["username"].astype(str).str.lower() == "elonmusk"].copy()

        if df.empty:
            continue

        df["date"] = input_path.stem
        rows.append(df)

    tweets = pd.concat(rows, ignore_index=True)
    tweets["tweet_id"] = tweets["id_str"].astype(str)
    tweets = tweets.drop_duplicates("tweet_id").sort_values(["date", "created_at"])
    tweets["popularity_label"] = tweets.apply(get_popularity_label, axis=1)
    return tweets


def classify_tweet(row):
    prompt = prompt_template.format(
        username=str(row["username"]),
        tweet_text=str(row["tweet"]),
        coin="DOGE",
        upload_date=str(row["created_at"]),
        retweets_count=str(row["retweets_count"]),
        likes_count=str(row["likes_count"]),
        follwers_count=str(row["Follower_count"]),
        replies_count=str(row["replies_count"])
    )

    last_error = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            parsed = json.loads(llm.invoke(prompt))
            return {
                "tweet_id": str(row["tweet_id"]),
                "date": row["date"],
                "created_at": row["created_at"],
                "text": row["tweet"],
                "signal": normalize_signal(parsed.get("signal")),
                "confidence": parsed.get("confidence"),
                "reason": parsed.get("reason"),
                "ticker": "DOGE",
                "username": row["username"],
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


def classify_all_tweets(tweets):
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    results = []
    completed_ids = set()

    if MODEL_RESPONSE_PATH.exists():
        previous_results = pd.read_csv(MODEL_RESPONSE_PATH)
        results = previous_results.to_dict("records")
        completed_ids = set(previous_results["tweet_id"].astype(str))

    for index, row in tweets.iterrows():
        if str(row["tweet_id"]) in completed_ids:
            continue

        result = classify_tweet(row)
        results.append(result)
        completed_ids.add(str(row["tweet_id"]))
        pd.DataFrame(results).to_csv(MODEL_RESPONSE_PATH, index=False)
        print(f"classified {len(completed_ids)}/{len(tweets)}", flush=True)

    return pd.DataFrame(results).sort_values(["date", "created_at"])


def load_price_data(price_path):
    return pd.read_csv(price_path).sort_values("Date").reset_index(drop=True)


def calculate_return(price_df, date, days_after):
    matching_rows = price_df.index[price_df["Date"].astype(str) == str(date)]

    if len(matching_rows) == 0:
        return None

    index = matching_rows[0]
    target_index = index + days_after

    if target_index < 0 or target_index >= len(price_df):
        return None

    current_close = float(price_df.iloc[index]["Close"])
    target_close = float(price_df.iloc[target_index]["Close"])

    if days_after < 0:
        return ((current_close - target_close) / target_close) * 100

    return ((target_close - current_close) / current_close) * 100


def calculate_actual_signal(price_change_percent):
    if price_change_percent is None:
        return "error"
    elif price_change_percent > NEUTRAL_PRICE_THRESHOLD_PERCENT:
        return "BUY"
    elif price_change_percent < -NEUTRAL_PRICE_THRESHOLD_PERCENT:
        return "SELL"
    else:
        return "NEUTRAL"


def calculate_daily_signal(daily_tweets):
    buy_count = int((daily_tweets["signal"] == "BUY").sum())
    sell_count = int((daily_tweets["signal"] == "SELL").sum())
    neutral_count = int((daily_tweets["signal"] == "NEUTRAL").sum())
    directional_count = buy_count + sell_count

    if directional_count == 0:
        return "NEUTRAL", buy_count, sell_count, neutral_count

    buy_ratio = buy_count / directional_count

    if buy_ratio >= 0.60:
        predicted_signal = "BUY"
    elif buy_ratio <= 0.40:
        predicted_signal = "SELL"
    else:
        predicted_signal = "NEUTRAL"

    return predicted_signal, buy_count, sell_count, neutral_count


def calculate_tweet_result(tweet_signal, actual_signal):
    if tweet_signal == actual_signal:
        return "aligned"
    elif tweet_signal == "NEUTRAL":
        return "no_direction"
    elif actual_signal == "NEUTRAL":
        return "not_aligned"
    else:
        return "opposite"


def build_event_results(tweet_results):
    doge_prices = load_price_data(DOGE_PRICE_PATH)
    btc_prices = load_price_data(BTC_PRICE_PATH)
    daily_results = []

    for date, daily_tweets in tweet_results.groupby("date"):
        predicted_signal, buy_count, sell_count, neutral_count = calculate_daily_signal(daily_tweets)
        doge_event_day_return = calculate_return(doge_prices, date, -1)
        doge_return_1d = calculate_return(doge_prices, date, 1)
        doge_return_3d = calculate_return(doge_prices, date, 3)
        doge_return_7d = calculate_return(doge_prices, date, 7)
        btc_return_1d = calculate_return(btc_prices, date, 1)
        actual_signal = calculate_actual_signal(doge_return_1d)
        evaluation = "correct" if predicted_signal == actual_signal else "incorrect"

        daily_results.append({
            "date": date,
            "tweet_count": len(daily_tweets),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "neutral_count": neutral_count,
            "predicted_signal": predicted_signal,
            "actual_signal": actual_signal,
            "doge_event_day_return_percent": doge_event_day_return,
            "doge_return_1d_percent": doge_return_1d,
            "doge_return_3d_percent": doge_return_3d,
            "doge_return_7d_percent": doge_return_7d,
            "btc_return_1d_percent": btc_return_1d,
            "market_adjusted_return_1d_percent": doge_return_1d - btc_return_1d,
            "evaluation": evaluation
        })

    daily_events = pd.DataFrame(daily_results).sort_values("date")
    event_columns = daily_events[[
        "date",
        "predicted_signal",
        "actual_signal",
        "doge_return_1d_percent",
        "market_adjusted_return_1d_percent",
        "evaluation"
    ]]
    tweet_events = tweet_results.merge(event_columns, on="date", how="left")
    tweet_events["tweet_result"] = tweet_events.apply(
        lambda row: calculate_tweet_result(row["signal"], row["actual_signal"]),
        axis=1
    )
    return daily_events, tweet_events


def build_summary(daily_events, tweet_events):
    correct_count = int((daily_events["evaluation"] == "correct").sum())
    actual_counts = daily_events["actual_signal"].value_counts()
    baseline_accuracy = actual_counts.max() / len(daily_events)

    return pd.DataFrame([{
        "tweet_count": len(tweet_events),
        "event_dates": len(daily_events),
        "correct_dates": correct_count,
        "accuracy_percent": (correct_count / len(daily_events)) * 100,
        "majority_baseline_percent": baseline_accuracy * 100,
        "positive_next_day_dates": int((daily_events["doge_return_1d_percent"] > 0).sum()),
        "average_doge_event_day_return_percent": daily_events["doge_event_day_return_percent"].mean(),
        "average_doge_return_1d_percent": daily_events["doge_return_1d_percent"].mean(),
        "median_doge_return_1d_percent": daily_events["doge_return_1d_percent"].median(),
        "average_market_adjusted_return_1d_percent": daily_events["market_adjusted_return_1d_percent"].mean(),
        "average_doge_return_3d_percent": daily_events["doge_return_3d_percent"].mean(),
        "average_doge_return_7d_percent": daily_events["doge_return_7d_percent"].mean()
    }])


def main():
    tweets = load_elon_tweets()
    tweet_results = classify_all_tweets(tweets)
    daily_events, tweet_events = build_event_results(tweet_results)
    summary = build_summary(daily_events, tweet_events)

    daily_events.to_csv(DAILY_EVENTS_PATH, index=False)
    tweet_events.to_csv(TWEET_EVENTS_PATH, index=False)
    summary.to_csv(SUMMARY_PATH, index=False)

    print(summary.to_string(index=False))
    print(f"daily events saved: {DAILY_EVENTS_PATH}")
    print(f"tweet events saved: {TWEET_EVENTS_PATH}")
    print(f"summary saved: {SUMMARY_PATH}")


if __name__ == "__main__":
    main()
