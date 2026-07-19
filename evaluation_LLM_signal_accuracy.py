# Evaluate BUY/SELL prediction accuracy from kom-ollama_influencer.py results.

from pathlib import Path

import pandas as pd


# Default run: BTC and ETH are saved in the base output files below.
# To make the separate Elon-DOGE or Trump-TRUMP files, replace the settings below
ollama_response_csv_files = [
    "results/ollama-response_influencer/BTC/BTC_minute_base_llm_result.csv",
    "results/ollama-response_influencer/ETH/ETH_minute_base_llm_result.csv",
#   "results/ollama-response_influencer/DOGE/DOGE_minute_base_llm_result.csv"
#   "results/ollama-response_influencer/TRUMP/TRUMP_minute_base_llm_result.csv"
]

binance_price_dataset_folders = {
    "BTC": "data/binance_price_change_per-minute/raw/BTC",
    "ETH": "data/binance_price_change_per-minute/raw/ETH",
#   "DOGE": "data/binance_price_change_per-minute/raw/DOGE"
#   "TRUMP": "data/binance_price_change_per-minute/raw/TRUMP"
}


by_event_out_csv_path = "results/ollama-response_influencer/buy_sell_signal_accuracy_by_event.csv"
# by_event_out_csv_path = "results/ollama-response_influencer/buy_sell_signal_accuracy_by_event_elon-DOGE.csv"
# by_event_out_csv_path = "results/ollama-response_influencer/buy_sell_signal_accuracy_by_event_Trump-Trump coin.csv"

summary_out_csv_path = "results/ollama-response_influencer/buy_sell_signal_accuracy_summary.csv"
# summary_out_csv_path = "results/ollama-response_influencer/buy_sell_signal_accuracy_summary_elon-DOGE.csv"
# summary_out_csv_path = "results/ollama-response_influencer/buy_sell_signal_accuracy_summary_Trump-Trump coin.csv"





minutes_after_tweet = [1, 3, 5, 10, 15, 30, 60, 120, 360, 720, 1440]
one_minute_ms = 60 * 1000


def first_minute_after_tweet_ms(tweet_time):
    tweet_ms = int(tweet_time.timestamp() * 1000)
    return ((tweet_ms + one_minute_ms - 1) // one_minute_ms) * one_minute_ms


def utc_text(milliseconds):
    return pd.to_datetime(milliseconds, unit="ms", utc=True).strftime(
        "%Y-%m-%d %H:%M:%S+00:00"
    )


def load_ollama_results(csv_files):
    dataframes = []

    for csv_file in csv_files:
        df = pd.read_csv(csv_file)

        df["created_at_utc"] = pd.to_datetime(df["created_at_utc"], utc=True)
        df["created_at_utc_text"] = df["created_at_utc"].dt.strftime(
            "%Y-%m-%d %H:%M:%S+00:00"
        )
        df["start_minute_ms"] = df["created_at_utc"].apply(
            first_minute_after_tweet_ms
        )
        dataframes.append(df)

    return pd.concat(dataframes, ignore_index=True)


def load_price_map(coin, folder):
    dataframes = []

    for csv_file in sorted(Path(folder).glob(f"{coin}USDT-1m-*.csv")):
        df = pd.read_csv(csv_file, usecols=["open_time", "close_price"])
        df["open_time"] = pd.to_numeric(df["open_time"], errors="coerce")

        # Some Binance files use microseconds instead of milliseconds.
        microseconds = df["open_time"] > 100_000_000_000_000
        df.loc[microseconds, "open_time"] = df.loc[microseconds, "open_time"] // 1000
        dataframes.append(df)

    if not dataframes:
        raise FileNotFoundError(f"No Binance price CSV files found in: {folder}")

    prices = pd.concat(dataframes, ignore_index=True)
    prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
    prices = prices.dropna(subset=["open_time", "close_price"])
    prices["open_time"] = prices["open_time"].astype("int64")
    prices = prices.sort_values("open_time").drop_duplicates("open_time", keep="last")

    return pd.Series(prices["close_price"].values, index=prices["open_time"])


def prediction_is_correct(signal, price_change):
    if price_change == 0:
        return pd.NA
    if signal == "BUY":
        return price_change > 0
    return price_change < 0


def make_by_event_csv(ollama_df, price_maps):
    rows = []
    buy_sell_tweets = ollama_df[ollama_df["signal"].isin(["BUY", "SELL"])]

    for _, tweet in buy_sell_tweets.iterrows():
        price_map = price_maps[tweet["coin"]]
        start_ms = int(tweet["start_minute_ms"])
        start_price = price_map.get(start_ms, pd.NA)

        for minutes in minutes_after_tweet:
            end_ms = start_ms + minutes * one_minute_ms
            end_price = price_map.get(end_ms, pd.NA)

            if pd.isna(start_price) or pd.isna(end_price) or start_price == 0:
                price_change = pd.NA
                price_change_rate = pd.NA
                is_price_flat = pd.NA
                is_correct = pd.NA
            else:
                price_change = end_price - start_price
                price_change_rate = price_change / start_price
                is_price_flat = price_change == 0
                is_correct = prediction_is_correct(tweet["signal"], price_change)

            rows.append(
                {
                    "coin": tweet["coin"],
                    "minutes_after_tweet": minutes,
                    "source_row_number": tweet["source_row_number"],
                    "created_at_utc": tweet["created_at_utc_text"],
                    "username": tweet["username"],
                    "signal": tweet["signal"],
                    "confidence": tweet["confidence"],
                    "impact_strength": tweet["impact_strength"],
                    "start_minute_utc": utc_text(start_ms),
                    "target_minute_utc": utc_text(end_ms),
                    "start_price": start_price,
                    "end_price": end_price,
                    "price_change": price_change,
                    "price_change_rate": price_change_rate,
                    "is_price_flat": is_price_flat,
                    "is_prediction_correct": is_correct,
                }
            )

    return pd.DataFrame(rows)


def make_summary_csv(event_df):
    rows = []

    for coin in sorted(event_df["coin"].dropna().unique()):
        coin_events = event_df[event_df["coin"] == coin]

        for signal_name in ["BUY_OR_SELL", "BUY", "SELL"]:
            if signal_name == "BUY_OR_SELL":
                signal_events = coin_events
            else:
                signal_events = coin_events[coin_events["signal"] == signal_name]

            for minutes in minutes_after_tweet:
                minute_df = signal_events[
                    signal_events["minutes_after_tweet"] == minutes
                ]
                valid_df = minute_df[minute_df["is_prediction_correct"].notna()]

                correct = int((valid_df["is_prediction_correct"] == True).sum())
                wrong = int((valid_df["is_prediction_correct"] == False).sum())
                flat = int((minute_df["is_price_flat"] == True).sum())
                missing_price = int(
                    (
                        minute_df["start_price"].isna()
                        | minute_df["end_price"].isna()
                    ).sum()
                )

                if correct + wrong == 0:
                    correct_percent = pd.NA
                else:
                    correct_percent = round(correct / (correct + wrong) * 100, 2)

                rows.append(
                    {
                        "coin": coin,
                        "LLM response signal": signal_name,
                        "minutes_after_tweet": minutes,
                        "total tweets": len(minute_df),
                        "tweets_without_price": missing_price,
                        "correct": correct,
                        "wrong": wrong,
                        "flat": flat,
                        "correct_probability_percent": correct_percent,
                    }
                )

    return pd.DataFrame(rows)


def main():
    ollama_df = load_ollama_results(ollama_response_csv_files)

    price_maps = {}
    for coin in sorted(ollama_df["coin"].dropna().unique()):
        price_maps[coin] = load_price_map(
            coin,
            binance_price_dataset_folders[coin],
        )

    event_df = make_by_event_csv(ollama_df, price_maps)
    summary_df = make_summary_csv(event_df)

    event_df.to_csv(by_event_out_csv_path, index=False)
    summary_df.to_csv(summary_out_csv_path, index=False)

    print(f"saved: {by_event_out_csv_path}")
    print(f"saved: {summary_out_csv_path}")


if __name__ == "__main__":
    main()
