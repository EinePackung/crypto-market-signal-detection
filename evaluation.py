from datetime import timedelta
from pathlib import Path

import pandas as pd
import json

from numpy.f2py.auxfuncs import throw_error


price_dataset_path = None
result_dataset_path = None

COINS = ["btc", "doge", "eth"]
BUY_RATIO_THRESHOLD = 0.60
SELL_RATIO_THRESHOLD = 0.40
NEUTRAL_PRICE_THRESHOLD_PERCENT = 1.0


def load_price_dataset():
    with open(price_dataset_path) as price_dataset:
        df = pd.read_csv(price_dataset)
        return df

def load_close_price_dataset_with_date(date):
    with open(price_dataset_path) as price_dataset:
        df = pd.read_csv(price_dataset)

        for index, row in df.iterrows():
            if str(row["Date"]) == date:
                return float(row["Close"])

        return None

def load_open_price_dataset_with_date(date):
    with open(price_dataset_path) as price_dataset:
        df = pd.read_csv(price_dataset)

        for index, row in df.iterrows():
            if str(row["Date"]) == date:
               return float(row["Open"])

        return None


def load_ollama_response_result():
    with open(result_dataset_path) as results_dataset:
        df = pd.read_csv(results_dataset)
        return df


def calculate_price_change_on_date(date):

    tweet_day_open_price = load_open_price_dataset_with_date(date)
    tweet_day_close_price = load_close_price_dataset_with_date(date)

    if tweet_day_open_price is None or tweet_day_close_price is None:
        return None

    return tweet_day_close_price - tweet_day_open_price

def calculate_price_change_until_next_day(date):
    tweet_day_close_price = load_close_price_dataset_with_date(date)
    if tweet_day_close_price is None:
        return None

    df = load_price_dataset()
    df = df.sort_values("Date").reset_index(drop=True)

    for index, row in df.iterrows():
        if str(row["Date"]) == str(date):
            if index +1 >= len(df): return None

            else:
                next_day_close_price = float(df.iloc[index+1]["Close"])
                return next_day_close_price - tweet_day_close_price

    return None


def calculate_daily_signal(daily_tweets):
    # NEUTRAL tweets do not vote for a price direction.
    signals = daily_tweets["signal"].astype(str).str.upper().str.strip()
    buy_count = int((signals == "BUY").sum())
    sell_count = int((signals == "SELL").sum())
    neutral_count = int((signals == "NEUTRAL").sum())
    directional_count = buy_count + sell_count

    if directional_count == 0:
        return "NEUTRAL", buy_count, sell_count, neutral_count, None

    buy_ratio = buy_count / directional_count

    if buy_ratio >= BUY_RATIO_THRESHOLD:
        predicted_signal = "BUY"
    elif buy_ratio <= SELL_RATIO_THRESHOLD:
        predicted_signal = "SELL"
    else:
        predicted_signal = "NEUTRAL"

    return predicted_signal, buy_count, sell_count, neutral_count, buy_ratio


def calculate_actual_signal(price_change_percent):
    # A next-day price move within +/- 1% is treated as NEUTRAL.
    if price_change_percent > NEUTRAL_PRICE_THRESHOLD_PERCENT:
        return "BUY"
    elif price_change_percent < -NEUTRAL_PRICE_THRESHOLD_PERCENT:
        return "SELL"
    else:
        return "NEUTRAL"


def calculate_tweet_result(tweet_signal, actual_signal):
    # Describe how each tweet signal relates to the actual market direction.
    if actual_signal == "error":
        return "error"
    elif tweet_signal == actual_signal:
        if tweet_signal == "NEUTRAL":
            return "aligned_neutral"
        return "aligned"
    elif tweet_signal == "NEUTRAL":
        return "no_direction"
    elif actual_signal == "NEUTRAL":
        return "not_aligned"
    else:
        return "opposite"


def evaluate_signal (result_csv, coin, result_name):
    # Combine tweet-level signals into one prediction for each date.
    result_csv = result_csv.copy()
    result_csv["date"] = result_csv["created_at"].astype(str).str[:10]
    daily_evaluation_result = []
    tweet_evaluation_result = []

    for date, daily_tweets in result_csv.groupby("date"):
        predicted_signal, buy_count, sell_count, neutral_count, buy_ratio = calculate_daily_signal(daily_tweets)
        tweet_day_close_price = load_close_price_dataset_with_date(date)
        price_change = calculate_price_change_until_next_day(date)

        if price_change is None or tweet_day_close_price is None:
            next_day_close_price = None
            price_change_percent = None
            actual_signal = "error"
            evaluation = "error"
        else:
            next_day_close_price = tweet_day_close_price + price_change
            price_change_percent = (price_change / tweet_day_close_price) * 100
            actual_signal = calculate_actual_signal(price_change_percent)
            evaluation = "correct" if predicted_signal == actual_signal else "incorrect"

        daily_evaluation_result.append({
            "date": date,
            "total_tweets": len(daily_tweets),
            "buy_count": buy_count,
            "sell_count": sell_count,
            "neutral_count": neutral_count,
            "buy_ratio": buy_ratio,
            "predicted_signal": predicted_signal,
            "actual_signal": actual_signal,
            "current_close": tweet_day_close_price,
            "next_day_close": next_day_close_price,
            "price_change": price_change,
            "price_change_percent": price_change_percent,
            "evaluation": evaluation
        })

        # Keep every tweet for prompt analysis and debugging.
        for index, tweet in daily_tweets.iterrows():
            tweet_data = tweet.to_dict()
            tweet_signal = str(tweet["signal"]).upper().strip()
            tweet_data.update({
                "daily_predicted_signal": predicted_signal,
                "actual_signal": actual_signal,
                "current_close": tweet_day_close_price,
                "next_day_close": next_day_close_price,
                "price_change": price_change,
                "price_change_percent": price_change_percent,
                "tweet_result": calculate_tweet_result(tweet_signal, actual_signal),
                "daily_evaluation": evaluation
            })
            tweet_evaluation_result.append(tweet_data)

    save(
        pd.DataFrame(daily_evaluation_result),
        pd.DataFrame(tweet_evaluation_result),
        coin,
        result_name
    )

def save (daily_evaluated_csv, tweets_evaluated_csv, coin, result_name):
    daily_folder = Path(f"results/evaluated/{coin}/daily")
    tweets_folder = Path(f"results/evaluated/{coin}/tweets")

    # Create output folders when they do not exist.
    daily_folder.mkdir(parents=True, exist_ok=True)
    tweets_folder.mkdir(parents=True, exist_ok=True)

    daily_save_path = daily_folder / f"{result_name}_daily_evaluated.csv"
    tweets_save_path = tweets_folder / f"{result_name}_tweets_evaluated.csv"

    daily_evaluated_csv.to_csv(daily_save_path, index=False)
    tweets_evaluated_csv.to_csv(tweets_save_path, index=False)
    print(f"daily save complete: ", daily_save_path)
    print(f"tweets save complete: ", tweets_save_path)


def evaluate_result_file(coin, result_path):
    global price_dataset_path
    global result_dataset_path

    result_path = Path(result_path)
    price_dataset_path = f"data/CrypTop12-main/price/raw/{coin}.csv"
    result_dataset_path = str(result_path)
    result_csv = load_ollama_response_result()

    if result_csv.empty:
        print(f"skip empty result: ", result_path)
        return

    evaluate_signal(result_csv, coin, result_path.stem)


def evaluate_all_results():
    # Evaluate every completed v5 response that does not have both output files.
    for coin in COINS:
        response_folder = Path(f"results/ollama_response/{coin}")

        for result_path in sorted(response_folder.glob("*_with_prompt_v5_popularity_filtered.csv")):
            daily_path = Path(f"results/evaluated/{coin}/daily/{result_path.stem}_daily_evaluated.csv")
            tweets_path = Path(f"results/evaluated/{coin}/tweets/{result_path.stem}_tweets_evaluated.csv")

            if daily_path.exists() and tweets_path.exists():
                continue

            evaluate_result_file(coin, result_path)


if __name__ == "__main__":
    evaluate_all_results()
