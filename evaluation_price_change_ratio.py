#!/usr/bin/env python3
"""Create influencer tweet price-change all-events and summary CSV files.

The code is intentionally organized around the output CSV columns:

1. Load one coin's Ollama response CSV.
2. Load the same coin's Binance one-minute price CSV files.
3. Calculate the overall and monthly price-change baselines.
4. Build each all-events column by calling one calculation function at a time.
5. Build each summary column by calling one calculation function at a time.
6. Save the all-events and summary CSV files.
"""

from pathlib import Path

import pandas as pd


# change these values before running the script.


# Example: "BTC", "ETH", "DOGE", or "TRUMP".
coin = ""

# Example: "results/ollama-response_influencer/BTC/BTC_minute_base_llm_result.csv"
ollama_response_csv = ""

# Example: "data/binance_price_change_per-minute/raw/BTC"
binance_price_dataset_folder = ""

# Use "all_accounts" for BTC/ETH, "dogecoin" for the official DOGE account,
# or "elonmusk" for the Elon-DOGE result.
tweet_account = "all_accounts"

all_events_out_csv_path = "results/ollama-response_influencer/influencer_tweet_price_change_rate_events.csv"
summary_out_csv_path = "results/ollama-response_influencer/influencer_tweet_price_change_rate_summary.csv"

MINUTES_AFTER_TWEET = [1, 3, 5, 10, 15, 30, 60, 120, 360, 720, 1440]
TWEET_GROUP_NAMES = ["all_tweets", "buy_sell_tweets"]

ONE_MINUTE_MS = 60 * 1000


all_events_columns = [
    "coin",
    "tweet_group",
    "minutes",
    "source_row_number",
    "created_at_utc",
    "tweet_month",
    "username",
    "signal",
    "coin_related",
    "confidence",
    "impact_strength",
    "start_price",
    "end_price",
    "tweet_price_change_rate",
    "overall_avg_price_change_rate",
    "monthly_price_change_rate",
    "after_tweet_vs_overall_avg_change_ratio",
    "after_tweet_vs_monthly_avg_change_ratio",
    "above_usual_change_overall",
    "above_monthly_avg_change",
]

SUMMARY_COLUMNS = [
    "coin",
    "tweet_group",
    "minutes",
    "total_tweets",
    "tweets_with_price",
    "missing_price",
    "avg_price_change_rate_percent_after_tweets",
    "avg_price_change_rate_percent_overall",
    "avg_price_change_rate_percent_monthly",
    "after_tweet_vs_usual_change_ratio_overall",
    "after_tweet_vs_monthly_avg_change_ratio",
]


# -----------------------------------------------------------------------------
# Load and prepare the Ollama response dataset.
# -----------------------------------------------------------------------------

def first_minute_after_tweet_ms(tweet_time):
    tweet_ms = int(tweet_time.timestamp() * 1000)
    return ((tweet_ms + ONE_MINUTE_MS - 1) // ONE_MINUTE_MS) * ONE_MINUTE_MS


def load_influencer_tweet_ollama_response(ollama_response_csv, tweet_account):
    path = Path(ollama_response_csv)
    if not path.is_file():
        raise FileNotFoundError(f"Ollama response CSV not found: {path}")

    df = pd.read_csv(path, low_memory=False)
    if df.empty:
        raise ValueError(f"Ollama response CSV is empty: {path}")

    if tweet_account != "all_accounts":
        df = df[df["username"] == tweet_account].copy()

    df = df.copy()
    df["coin_related"] = df["is_tweet_related_to_coin"]

    df["created_at_utc"] = pd.to_datetime(df["created_at_utc"], utc=True)
    df["created_at_utc_text"] = df["created_at_utc"].dt.strftime(
        "%Y-%m-%d %H:%M:%S+00:00"
    )
    df["tweet_month"] = df["created_at_utc"].dt.strftime("%Y-%m")
    df["start_minute_ms"] = df["created_at_utc"].apply(
        first_minute_after_tweet_ms
    )

    return df


# -----------------------------------------------------------------------------
# Load and prepare the Binance price dataset.
# -----------------------------------------------------------------------------

def fix_price_time_unit(price_df):
    price_df = price_df.copy()
    price_df["open_time"] = pd.to_numeric(price_df["open_time"], errors="coerce")

    # Some Binance files use microseconds instead of milliseconds.
    microsecond_rows = price_df["open_time"] > 100_000_000_000_000
    price_df.loc[microsecond_rows, "open_time"] = (
        price_df.loc[microsecond_rows, "open_time"] // 1000
    )
    return price_df


def month_from_price_file(path):
    return path.stem.split("-1m-")[-1]


def load_coin_binance_price_dataset(coin, binance_price_dataset_folder):
    coin_dir = Path(binance_price_dataset_folder)
    price_frames = []

    for path in sorted(coin_dir.glob(f"{coin}USDT-1m-*.csv")):
        frame = pd.read_csv(path, usecols=["open_time", "close_price"])
        frame = fix_price_time_unit(frame)
        frame["month"] = month_from_price_file(path)
        price_frames.append(frame)

    if not price_frames:
        raise FileNotFoundError(f"No Binance price CSV files found in: {coin_dir}")

    price_df = pd.concat(price_frames, ignore_index=True)
    price_df["close_price"] = pd.to_numeric(
        price_df["close_price"], errors="coerce"
    )
    price_df = price_df.dropna(subset=["open_time", "close_price"])
    price_df["open_time"] = price_df["open_time"].astype("int64")
    price_df = (
        price_df.sort_values("open_time")
        .drop_duplicates("open_time", keep="last")
        .reset_index(drop=True)
    )
    return price_df


def make_price_map(price_df):
    return pd.Series(
        price_df["close_price"].values,
        index=price_df["open_time"].values,
    )


def calculate_price_change_baselines(price_df):
    overall_avg_by_minutes = {}
    monthly_avg_by_minutes = {}

    close_price = price_df["close_price"]
    open_time = price_df["open_time"]

    for minutes in MINUTES_AFTER_TWEET:
        future_close = close_price.shift(-minutes)
        future_time = open_time.shift(-minutes)
        expected_time = open_time + minutes * ONE_MINUTE_MS

        valid_rows = (
            close_price.notna()
            & future_close.notna()
            & (close_price != 0)
            & (future_time == expected_time)
        )

        change_rates = ((future_close - close_price).abs() / close_price)[valid_rows]
        months = price_df.loc[valid_rows, "month"]

        overall_avg_by_minutes[minutes] = change_rates.mean()

        monthly_table = pd.DataFrame(
            {"month": months, "price_change_rate": change_rates}
        )
        for month, month_df in monthly_table.groupby("month"):
            monthly_avg_by_minutes[(month, minutes)] = month_df[
                "price_change_rate"
            ].mean()

    return overall_avg_by_minutes, monthly_avg_by_minutes


# -----------------------------------------------------------------------------
# By-event CSV column methods.
# -----------------------------------------------------------------------------

def all_events_coin(tweet):
    return tweet["coin"]


def all_events_tweet_group(tweet_group_name):
    return tweet_group_name


def all_events_minutes(minutes):
    return minutes


def all_events_source_row_number(tweet):
    return tweet["source_row_number"]


def all_events_created_at_utc(tweet):
    return tweet["created_at_utc_text"]


def all_events_tweet_month(tweet):
    return tweet["tweet_month"]


def all_events_username(tweet):
    return tweet["username"]


def all_events_signal(tweet):
    return tweet["signal"]


def all_events_coin_related(tweet):
    return tweet["coin_related"]


def all_events_confidence(tweet):
    return tweet["confidence"]


def all_events_impact_strength(tweet):
    return tweet["impact_strength"]


def all_events_start_price(tweet, price_map):
    return price_map.get(int(tweet["start_minute_ms"]), pd.NA)


def all_events_end_price(tweet, minutes, price_map):
    end_time_ms = int(tweet["start_minute_ms"]) + minutes * ONE_MINUTE_MS
    return price_map.get(end_time_ms, pd.NA)


def all_events_tweet_price_change_rate(start_price, end_price):
    if pd.isna(start_price) or pd.isna(end_price) or float(start_price) == 0:
        return pd.NA
    return abs((float(end_price) - float(start_price)) / float(start_price))


def all_events_overall_avg_price_change_rate(minutes, overall_avg_by_minutes):
    return overall_avg_by_minutes.get(minutes, pd.NA)


def all_events_monthly_price_change_rate(tweet, minutes, monthly_avg_by_minutes):
    return monthly_avg_by_minutes.get((tweet["tweet_month"], minutes), pd.NA)


def ratio_cal(top, bottom):
    if pd.isna(top) or pd.isna(bottom) or float(bottom) == 0:
        return pd.NA
    return round(float(top) / float(bottom), 6)


def all_events_after_tweet_vs_overall_avg_change_ratio(
    tweet_price_change_rate,
    overall_avg_price_change_rate,
):
    return ratio_cal(tweet_price_change_rate, overall_avg_price_change_rate)


def all_events_after_tweet_vs_monthly_avg_change_ratio(
    tweet_price_change_rate,
    monthly_price_change_rate,
):
    return ratio_cal(tweet_price_change_rate, monthly_price_change_rate)


def all_events_above_usual_change_overall(
    tweet_price_change_rate,
    overall_avg_price_change_rate,
):
    if pd.isna(tweet_price_change_rate) or pd.isna(overall_avg_price_change_rate):
        return pd.NA
    return float(tweet_price_change_rate) > float(overall_avg_price_change_rate)


def all_events_above_monthly_avg_change(
    tweet_price_change_rate,
    monthly_price_change_rate,
):
    if pd.isna(tweet_price_change_rate) or pd.isna(monthly_price_change_rate):
        return pd.NA
    return float(tweet_price_change_rate) > float(monthly_price_change_rate)


def make_all_events_row(
    tweet,
    tweet_group_name,
    minutes,
    price_map,
    overall_avg_by_minutes,
    monthly_avg_by_minutes,
):
    start_price = all_events_start_price(tweet, price_map)
    end_price = all_events_end_price(tweet, minutes, price_map)
    tweet_change_rate = all_events_tweet_price_change_rate(start_price, end_price)

    # The current all-events CSV contains only rows with both prices available.
    if pd.isna(tweet_change_rate):
        return None

    overall_change_rate = all_events_overall_avg_price_change_rate(
        minutes, overall_avg_by_minutes
    )
    monthly_change_rate = all_events_monthly_price_change_rate(
        tweet, minutes, monthly_avg_by_minutes
    )

    return {
        "coin": all_events_coin(tweet),
        "tweet_group": all_events_tweet_group(tweet_group_name),
        "minutes": all_events_minutes(minutes),
        "source_row_number": all_events_source_row_number(tweet),
        "created_at_utc": all_events_created_at_utc(tweet),
        "tweet_month": all_events_tweet_month(tweet),
        "username": all_events_username(tweet),
        "signal": all_events_signal(tweet),
        "coin_related": all_events_coin_related(tweet),
        "confidence": all_events_confidence(tweet),
        "impact_strength": all_events_impact_strength(tweet),
        "start_price": start_price,
        "end_price": end_price,
        "tweet_price_change_rate": tweet_change_rate,
        "overall_avg_price_change_rate": overall_change_rate,
        "monthly_price_change_rate": monthly_change_rate,
        "after_tweet_vs_overall_avg_change_ratio": (
            all_events_after_tweet_vs_overall_avg_change_ratio(
                tweet_change_rate, overall_change_rate
            )
        ),
        "after_tweet_vs_monthly_avg_change_ratio": (
            all_events_after_tweet_vs_monthly_avg_change_ratio(
                tweet_change_rate, monthly_change_rate
            )
        ),
        "above_usual_change_overall": all_events_above_usual_change_overall(
            tweet_change_rate, overall_change_rate
        ),
        "above_monthly_avg_change": all_events_above_monthly_avg_change(
            tweet_change_rate, monthly_change_rate
        ),
    }


def tweet_group(ollama_df, tweet_group_name):
    if tweet_group_name == "all_tweets":
        return ollama_df
    if tweet_group_name == "buy_sell_tweets":
        return ollama_df[ollama_df["signal"].isin(["BUY", "SELL"])]
    raise ValueError(f"Unknown tweet group: {tweet_group_name}")


def make_all_events_csv(
    ollama_df,
    price_map,
    overall_avg_by_minutes,
    monthly_avg_by_minutes,
):
    all_events_rows = []

    for tweet_group_name in TWEET_GROUP_NAMES:
        group_df = tweet_group(ollama_df, tweet_group_name)

        for _, tweet in group_df.iterrows():
            for minutes in MINUTES_AFTER_TWEET:
                all_events_row = make_all_events_row(
                    tweet=tweet,
                    tweet_group_name=tweet_group_name,
                    minutes=minutes,
                    price_map=price_map,
                    overall_avg_by_minutes=overall_avg_by_minutes,
                    monthly_avg_by_minutes=monthly_avg_by_minutes,
                )
                if all_events_row is not None:
                    all_events_rows.append(all_events_row)

    return pd.DataFrame(all_events_rows, columns=all_events_columns)


# -----------------------------------------------------------------------------
# Summary CSV column methods.
# -----------------------------------------------------------------------------

def summary_coin(coin):
    return coin


def summary_tweet_group(tweet_group_name):
    return tweet_group_name


def summary_minutes(minutes):
    return minutes


def total_tweets_cal(group_df):
    return int(len(group_df))


def total_tweets_with_price_cal(group_all_events_df):
    return int(len(group_all_events_df))


def missing_price_cal(total_tweets, tweets_with_price):
    return int(total_tweets - tweets_with_price)


def mean_cal(values):
    numeric_values = pd.to_numeric(values, errors="coerce").dropna()
    if numeric_values.empty:
        return pd.NA
    return float(numeric_values.mean())


def percent_cal(value):
    if pd.isna(value):
        return pd.NA
    return round(float(value) * 100, 6)


def avg_price_change_rate_percent_after_tweets_cal(group_all_events_df):
    average = mean_cal(group_all_events_df["tweet_price_change_rate"])
    return percent_cal(average)


def avg_price_change_rate_percent_overall_cal(
    minutes,
    overall_avg_by_minutes,
):
    average = overall_avg_by_minutes.get(minutes, pd.NA)
    return percent_cal(average)


def avg_price_change_rate_percent_monthly_cal(group_all_events_df):
    average = mean_cal(group_all_events_df["monthly_price_change_rate"])
    return percent_cal(average)


def after_tweet_vs_usual_change_ratio_overall_cal(
    group_all_events_df,
    minutes,
    overall_avg_by_minutes,
):
    tweet_average = mean_cal(group_all_events_df["tweet_price_change_rate"])
    overall_average = overall_avg_by_minutes.get(minutes, pd.NA)
    return ratio_cal(tweet_average, overall_average)


def after_tweet_vs_monthly_avg_change_ratio_cal(group_all_events_df):
    tweet_average = mean_cal(group_all_events_df["tweet_price_change_rate"])
    monthly_average = mean_cal(group_all_events_df["monthly_price_change_rate"])
    return ratio_cal(tweet_average, monthly_average)


def make_summary_row(
    coin,
    tweet_group_name,
    minutes,
    ollama_df,
    all_events_df,
    overall_avg_by_minutes,
):
    group_df = tweet_group(ollama_df, tweet_group_name)
    group_all_events_df = all_events_df[
        (all_events_df["tweet_group"] == tweet_group_name)
        & (all_events_df["minutes"] == minutes)
    ]

    total_tweets = total_tweets_cal(group_df)
    tweets_with_price = total_tweets_with_price_cal(group_all_events_df)

    return {
        "coin": summary_coin(coin),
        "tweet_group": summary_tweet_group(tweet_group_name),
        "minutes": summary_minutes(minutes),
        "total_tweets": total_tweets,
        "tweets_with_price": tweets_with_price,
        "missing_price": missing_price_cal(total_tweets, tweets_with_price),
        "avg_price_change_rate_percent_after_tweets": (
            avg_price_change_rate_percent_after_tweets_cal(group_all_events_df)
        ),
        "avg_price_change_rate_percent_overall": (
            avg_price_change_rate_percent_overall_cal(
                minutes, overall_avg_by_minutes
            )
        ),
        "avg_price_change_rate_percent_monthly": (
            avg_price_change_rate_percent_monthly_cal(group_all_events_df)
        ),
        "after_tweet_vs_usual_change_ratio_overall": (
            after_tweet_vs_usual_change_ratio_overall_cal(
                group_all_events_df,
                minutes,
                overall_avg_by_minutes,
            )
        ),
        "after_tweet_vs_monthly_avg_change_ratio": (
            after_tweet_vs_monthly_avg_change_ratio_cal(group_all_events_df)
        ),
    }


def make_summary_csv(
    coin,
    ollama_df,
    all_events_df,
    overall_avg_by_minutes,
):
    summary_rows = []

    for tweet_group_name in TWEET_GROUP_NAMES:
        for minutes in MINUTES_AFTER_TWEET:
            summary_rows.append(
                make_summary_row(
                    coin=coin,
                    tweet_group_name=tweet_group_name,
                    minutes=minutes,
                    ollama_df=ollama_df,
                    all_events_df=all_events_df,
                    overall_avg_by_minutes=overall_avg_by_minutes,
                )
            )

    return pd.DataFrame(summary_rows, columns=SUMMARY_COLUMNS)


# -----------------------------------------------------------------------------
# Save files and run the full evaluation.
# -----------------------------------------------------------------------------

def save_csv_file(dataframe, output_path):
    dataframe.to_csv(output_path, index=False)
    print(f"saved: {output_path}")


def main():
    selected_coin = coin.strip().upper()
    if not selected_coin:
        raise SystemExit('Set coin at the top of the file, for example coin = "BTC".')
    if not ollama_response_csv:
        raise SystemExit("Set ollama_response_csv at the top of the file.")
    if not binance_price_dataset_folder:
        raise SystemExit("Set binance_price_dataset_folder at the top of the file.")

    ollama_df = load_influencer_tweet_ollama_response(
        ollama_response_csv,
        tweet_account,
    )
    price_df = load_coin_binance_price_dataset(
        selected_coin,
        binance_price_dataset_folder,
    )
    price_map = make_price_map(price_df)
    overall_avg_by_minutes, monthly_avg_by_minutes = (
        calculate_price_change_baselines(price_df)
    )

    all_events_df = make_all_events_csv(
        ollama_df=ollama_df,
        price_map=price_map,
        overall_avg_by_minutes=overall_avg_by_minutes,
        monthly_avg_by_minutes=monthly_avg_by_minutes,
    )

    summary_df = make_summary_csv(
        coin=selected_coin,
        ollama_df=ollama_df,
        all_events_df=all_events_df,
        overall_avg_by_minutes=overall_avg_by_minutes,
    )

    save_csv_file(all_events_df, Path(all_events_out_csv_path))
    save_csv_file(summary_df, Path(summary_out_csv_path))


if __name__ == "__main__":
    main()
