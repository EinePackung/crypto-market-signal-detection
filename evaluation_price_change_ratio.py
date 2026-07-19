# Compare price changes after influencer tweets with normal market price changes.

from pathlib import Path

import pandas as pd


# Choose which result files to make.
coin = "BTC+ETH"
# coin = "DOGE"
# coin = "TRUMP"

if coin == "BTC+ETH":
    input_datasets = [
        [
            "BTC",
            "results/ollama-response_influencer/BTC/BTC_minute_base_llm_result.csv",
            "data/binance_price_change_per-minute/raw/BTC",
        ],
        [
            "ETH",
            "results/ollama-response_influencer/ETH/ETH_minute_base_llm_result.csv",
            "data/binance_price_change_per-minute/raw/ETH",
        ],
    ]
    all_events_out_csv_path = "results/ollama-response_influencer/influencer_tweet_price_change_rate_events.csv"
    summary_out_csv_path = "results/ollama-response_influencer/influencer_tweet_price_change_rate_summary.csv"

elif coin == "DOGE":
    input_datasets = [
        [
            "DOGE",
            "results/ollama-response_influencer/DOGE/DOGE_minute_base_llm_result.csv",
            "data/binance_price_change_per-minute/raw/DOGE",
        ]
    ]
    all_events_out_csv_path = "results/ollama-response_influencer/influencer_tweet_price_change_rate_events_elon-DOGE.csv"
    summary_out_csv_path = "results/ollama-response_influencer/influencer_tweet_price_change_rate_summary_elon-DOGE.csv"

elif coin == "TRUMP":
    input_datasets = [
        [
            "TRUMP",
            "results/ollama-response_influencer/TRUMP/TRUMP_minute_base_llm_result.csv",
            "data/binance_price_change_per-minute/raw/TRUMP",
        ]
    ]
    all_events_out_csv_path = "results/ollama-response_influencer/influencer_tweet_price_change_rate_events_Trump-Trump coin.csv"
    summary_out_csv_path = "results/ollama-response_influencer/influencer_tweet_price_change_rate_summary_Trump-Trump coin.csv"

else:
    raise SystemExit('Set coin to "BTC+ETH", "DOGE", or "TRUMP".')

minutes_after_tweet = [1, 3, 5, 10, 15, 30, 60, 120, 360, 720, 1440]
tweet_group_names = ["all_tweets", "buy_sell_tweets"]
one_minute_ms = 60 * 1000


# Move the tweet time to the first full minute after the tweet.
def first_minute_after_tweet_ms(tweet_time):
    tweet_ms = int(tweet_time.timestamp() * 1000)
    return ((tweet_ms + one_minute_ms - 1) // one_minute_ms) * one_minute_ms


# Load the Ollama result and prepare the tweet time columns.
def load_ollama_results(csv_file):
    df = pd.read_csv(csv_file, low_memory=False)

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


# Load and clean all one-minute Binance price files for one coin.
def load_binance_prices(selected_coin, folder):
    dataframes = []

    for csv_file in sorted(Path(folder).glob(f"{selected_coin}USDT-1m-*.csv")):
        df = pd.read_csv(csv_file, usecols=["open_time", "close_price"])
        df["open_time"] = pd.to_numeric(df["open_time"], errors="coerce")

        # Some Binance files use microseconds instead of milliseconds.
        microseconds = df["open_time"] > 100_000_000_000_000
        df.loc[microseconds, "open_time"] = df.loc[microseconds, "open_time"] // 1000

        df["month"] = csv_file.stem.split("-1m-")[-1]
        dataframes.append(df)

    if not dataframes:
        raise FileNotFoundError(f"No Binance price CSV files found in: {folder}")

    prices = pd.concat(dataframes, ignore_index=True)
    prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
    prices = prices.dropna(subset=["open_time", "close_price"])
    prices["open_time"] = prices["open_time"].astype("int64")
    prices = prices.sort_values("open_time").drop_duplicates("open_time", keep="last")
    return prices.reset_index(drop=True)


# Calculate the normal price change for all data and for each month.
def calculate_price_change_baselines(price_df):
    overall_averages = {}
    monthly_averages = {}

    for minutes in minutes_after_tweet:
        start_price = price_df["close_price"]
        end_price = start_price.shift(-minutes)
        end_time = price_df["open_time"].shift(-minutes)
        expected_end_time = price_df["open_time"] + minutes * one_minute_ms

        valid = (
            start_price.notna()
            & end_price.notna()
            & (start_price != 0)
            & (end_time == expected_end_time)
        )
        change_rates = ((end_price - start_price).abs() / start_price)[valid]
        months = price_df.loc[valid, "month"]

        overall_averages[minutes] = change_rates.mean()

        monthly_table = pd.DataFrame(
            {"month": months, "price_change_rate": change_rates}
        )
        for month, month_df in monthly_table.groupby("month"):
            monthly_averages[(month, minutes)] = month_df[
                "price_change_rate"
            ].mean()

    return overall_averages, monthly_averages


# Return all tweets or only tweets with a BUY or SELL signal.
def get_tweet_group(ollama_df, group_name):
    if group_name == "all_tweets":
        return ollama_df
    return ollama_df[ollama_df["signal"].isin(["BUY", "SELL"])]


# Calculate the absolute price change rate between two prices.
def calculate_price_change_rate(start_price, end_price):
    if pd.isna(start_price) or pd.isna(end_price) or start_price == 0:
        return pd.NA
    return abs((end_price - start_price) / start_price)


# Compare one price change rate with a normal price change rate.
def calculate_ratio(value, baseline):
    if pd.isna(value) or pd.isna(baseline) or baseline == 0:
        return pd.NA
    return round(value / baseline, 6)


# Check whether the tweet price change is greater than the normal change.
def is_above_average(value, average):
    if pd.isna(average):
        return pd.NA
    return value > average


# Build one result row for each tweet group, tweet, and time period.
def make_all_events_csv(
    ollama_df,
    price_map,
    overall_averages,
    monthly_averages,
):
    rows = []

    for group_name in tweet_group_names:
        group_df = get_tweet_group(ollama_df, group_name)

        for _, tweet in group_df.iterrows():
            start_ms = int(tweet["start_minute_ms"])
            start_price = price_map.get(start_ms, pd.NA)

            for minutes in minutes_after_tweet:
                end_ms = start_ms + minutes * one_minute_ms
                end_price = price_map.get(end_ms, pd.NA)
                tweet_change_rate = calculate_price_change_rate(
                    start_price,
                    end_price,
                )

                # The all-events CSV contains only rows with both prices available.
                if pd.isna(tweet_change_rate):
                    continue

                overall_average = overall_averages.get(minutes, pd.NA)
                monthly_average = monthly_averages.get(
                    (tweet["tweet_month"], minutes),
                    pd.NA,
                )

                rows.append(
                    {
                        "coin": tweet["coin"],
                        "tweet_group": group_name,
                        "minutes": minutes,
                        "source_row_number": tweet["source_row_number"],
                        "created_at_utc": tweet["created_at_utc_text"],
                        "tweet_month": tweet["tweet_month"],
                        "username": tweet["username"],
                        "signal": tweet["signal"],
                        "coin_related": tweet["coin_related"],
                        "confidence": tweet["confidence"],
                        "impact_strength": tweet["impact_strength"],
                        "start_price": start_price,
                        "end_price": end_price,
                        "tweet_price_change_rate": tweet_change_rate,
                        "overall_avg_price_change_rate": overall_average,
                        "monthly_price_change_rate": monthly_average,
                        "after_tweet_vs_overall_avg_change_ratio": calculate_ratio(
                            tweet_change_rate, overall_average
                        ),
                        "after_tweet_vs_monthly_avg_change_ratio": calculate_ratio(
                            tweet_change_rate, monthly_average
                        ),
                        "above_usual_change_overall": is_above_average(
                            tweet_change_rate, overall_average
                        ),
                        "above_monthly_avg_change": is_above_average(
                            tweet_change_rate, monthly_average
                        ),
                    }
                )

    return pd.DataFrame(rows)


# Calculate the average after removing missing or invalid values.
def calculate_average(values):
    numbers = pd.to_numeric(values, errors="coerce").dropna()
    if numbers.empty:
        return pd.NA
    return numbers.mean()


# Convert a decimal rate into a percentage value.
def to_percent(value):
    if pd.isna(value):
        return pd.NA
    return round(value * 100, 6)


# Build the summary rows for all tweets and BUY/SELL tweets.
def make_summary_csv(
    selected_coin,
    ollama_df,
    all_events_df,
    overall_averages,
):
    rows = []

    for group_name in tweet_group_names:
        group_df = get_tweet_group(ollama_df, group_name)

        for minutes in minutes_after_tweet:
            event_df = all_events_df[
                (all_events_df["tweet_group"] == group_name)
                & (all_events_df["minutes"] == minutes)
            ]

            total_tweets = len(group_df)
            tweets_with_price = len(event_df)
            tweet_average = calculate_average(event_df["tweet_price_change_rate"])
            overall_average = overall_averages.get(minutes, pd.NA)
            monthly_average = calculate_average(event_df["monthly_price_change_rate"])

            rows.append(
                {
                    "coin": selected_coin,
                    "tweet_group": group_name,
                    "minutes": minutes,
                    "total_tweets": total_tweets,
                    "tweets_with_price": tweets_with_price,
                    "missing_price": total_tweets - tweets_with_price,
                    "avg_price_change_rate_percent_after_tweets": to_percent(
                        tweet_average
                    ),
                    "avg_price_change_rate_percent_overall": to_percent(
                        overall_average
                    ),
                    "avg_price_change_rate_percent_monthly": to_percent(
                        monthly_average
                    ),
                    "after_tweet_vs_usual_change_ratio_overall": calculate_ratio(
                        tweet_average, overall_average
                    ),
                    "after_tweet_vs_monthly_avg_change_ratio": calculate_ratio(
                        tweet_average, monthly_average
                    ),
                }
            )

    return pd.DataFrame(rows)


# Make the event and summary data for one coin.
def evaluate_one_coin(selected_coin, ollama_response_csv, price_dataset_folder):
    ollama_df = load_ollama_results(ollama_response_csv)
    price_df = load_binance_prices(selected_coin, price_dataset_folder)
    price_map = pd.Series(
        price_df["close_price"].values,
        index=price_df["open_time"],
    )
    overall_averages, monthly_averages = calculate_price_change_baselines(price_df)

    all_events_df = make_all_events_csv(
        ollama_df,
        price_map,
        overall_averages,
        monthly_averages,
    )
    summary_df = make_summary_csv(
        selected_coin,
        ollama_df,
        all_events_df,
        overall_averages,
    )

    return all_events_df, summary_df


# Evaluate the selected coins, combine their data, and save two CSV files.
def main():
    all_events_data = []
    summary_data = []

    for selected_coin, ollama_response_csv, price_dataset_folder in input_datasets:
        all_events_df, summary_df = evaluate_one_coin(
            selected_coin,
            ollama_response_csv,
            price_dataset_folder,
        )
        all_events_data.append(all_events_df)
        summary_data.append(summary_df)

    combined_all_events_df = pd.concat(all_events_data, ignore_index=True)
    combined_summary_df = pd.concat(summary_data, ignore_index=True)

    combined_all_events_df.to_csv(all_events_out_csv_path, index=False)
    combined_summary_df.to_csv(summary_out_csv_path, index=False)

    print(f"saved: {all_events_out_csv_path}")
    print(f"saved: {summary_out_csv_path}")


if __name__ == "__main__":
    main()
