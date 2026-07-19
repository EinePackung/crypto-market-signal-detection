# Evaluate BUY/SELL prediction accuracy from kom-ollama_influencer.py results.



from pathlib import Path

import pandas as pd


# Change these input and output paths before running the script.
ollama_response_csv_files = [
    "results/ollama-response_influencer/BTC/BTC_minute_base_llm_result.csv",
    "results/ollama-response_influencer/DOGE/DOGE_minute_base_llm_result.csv",
    "results/ollama-response_influencer/ETH/ETH_minute_base_llm_result.csv",
]

binance_price_dataset_folders = {
    "BTC": "data/binance_price_change_per-minute/raw/BTC",
    "ETH": "data/binance_price_change_per-minute/raw/ETH",
    "DOGE": "data/binance_price_change_per-minute/raw/DOGE",
}

# Each standardized Ollama result already contains the selected accounts for its coin.
tweet_account_by_coin = {
    "BTC": "all_accounts",
    "ETH": "all_accounts",
    "DOGE": "elonmusk",
}

by_event_out_csv_path = "results/ollama-response_influencer/buy_sell_signal_accuracy_by_event.csv"
summary_out_csv_path = "results/ollama-response_influencer/buy_sell_signal_accuracy_summary.csv"

MINUTES_AFTER_TWEET = [1, 3, 5, 10, 15, 30, 60, 120, 360, 720, 1440]
ONE_MINUTE_MS = 60 * 1000


# Round the tweet time up to the next minute and convert it to milliseconds.
# E.g. 16:46:15 -> 16:47:00 -> 1517417220000
def first_minute_after_tweet_in_ms(tweet_time):
    tweet_ms = int(tweet_time.timestamp() * 1000)
    return ((tweet_ms + ONE_MINUTE_MS - 1) // ONE_MINUTE_MS) * ONE_MINUTE_MS


def fix_price_time_unit(price_df):
    price_df["open_time"] = pd.to_numeric(price_df["open_time"], errors="coerce")

    # Some price files use microseconds instead of milliseconds.
    microsecond_rows = price_df["open_time"] > 100_000_000_000_000
    price_df.loc[microsecond_rows, "open_time"] = (
        price_df.loc[microsecond_rows, "open_time"] // 1000
    )

    return price_df


def ms_to_utc_text(ms):
    if pd.isna(ms):
        return ""
    return pd.to_datetime(int(ms), unit="ms", utc=True).strftime("%Y-%m-%d %H:%M:%S+00:00")




def load_ollama_results(ollama_response_csv_files, tweet_account_by_coin):
    read_results = []

    for csv_file in ollama_response_csv_files:
        path = Path(csv_file)
        df = pd.read_csv(path)

        coin = df["coin"].iloc[0]
        tweet_account = tweet_account_by_coin[coin]
        if tweet_account != "all_accounts":
            df = df[df["username"] == tweet_account].copy()

        df["created_at_utc"] = pd.to_datetime(df["created_at_utc"], utc=True)
        df["start_minute_ms"] = df["created_at_utc"].apply(
            first_minute_after_tweet_in_ms
        )
        df["created_at_utc_text"] = df["created_at_utc"].dt.strftime(
            "%Y-%m-%d %H:%M:%S+00:00"
        )
        read_results.append(df)

    return pd.concat(read_results, ignore_index=True)


def load_price_map(coin, binance_price_dataset_folder):
    coin_dir = Path(binance_price_dataset_folder)
    price_frames = []

    for path in sorted(coin_dir.glob(f"{coin.upper()}USDT-1m-*.csv")):
        df = pd.read_csv(path, usecols=["open_time", "close_price"])
        df = fix_price_time_unit(df)
        price_frames.append(df)

    if not price_frames:
        raise FileNotFoundError(f"No Binance price CSV files found in: {coin_dir}")

    prices = pd.concat(price_frames, ignore_index=True)
    prices["close_price"] = pd.to_numeric(prices["close_price"], errors="coerce")
    prices = prices.dropna(subset=["open_time", "close_price"])
    prices["open_time"] = prices["open_time"].astype("int64")
    prices = prices.sort_values("open_time").drop_duplicates("open_time", keep="last")
    return pd.Series(prices["close_price"].values, index=prices["open_time"])


def is_correct(signal, price_change):
    if pd.isna(price_change):
        return pd.NA
    if price_change == 0:
        return pd.NA
    if signal == "BUY":
        return price_change > 0
    if signal == "SELL":
        return price_change < 0
    return pd.NA


def make_event_rows(ollama_df, price_maps):
    rows = []
    buy_sell_df = ollama_df[ollama_df["signal"].isin(["BUY", "SELL"])].copy()

    for _, tweet in buy_sell_df.iterrows():
        coin = tweet["coin"]
        price_map = price_maps[coin]
        start_ms = int(tweet["start_minute_ms"])
        start_price = price_map.get(start_ms, pd.NA)

        for minutes in MINUTES_AFTER_TWEET:
            target_ms = start_ms + minutes * 60000
            target_price = price_map.get(target_ms, pd.NA)

            if pd.isna(start_price) or pd.isna(target_price) or start_price == 0:
                price_change = pd.NA
                price_change_rate = pd.NA
                is_price_flat = pd.NA
                correct = pd.NA
            else:
                price_change = target_price - start_price
                price_change_rate = price_change / start_price
                is_price_flat = price_change == 0
                correct = is_correct(tweet["signal"], price_change)

            rows.append(
                {
                    "coin": coin,
                    "minutes_after_tweet": minutes,
                    "source_row_number": tweet["source_row_number"],
                    "created_at_utc": tweet["created_at_utc_text"],
                    "username": tweet["username"],
                    "signal": tweet["signal"],
                    "confidence": tweet["confidence"],
                    "impact_strength": tweet["impact_strength"],
                    "start_minute_utc": ms_to_utc_text(start_ms),
                    "target_minute_utc": ms_to_utc_text(target_ms),
                    "start_price": start_price,
                    "target_price": target_price,
                    "price_change": price_change,
                    "price_change_rate": price_change_rate,
                    "is_price_flat": is_price_flat,
                    "is_prediction_correct": correct,
                }
            )

    return pd.DataFrame(rows)


def summarize_events(event_df):
    summary_rows = []

    groups = []
    for coin in sorted(event_df["coin"].dropna().unique()):
        groups.append(("coin", coin, "BUY_OR_SELL", event_df["coin"] == coin))
        for signal in ["BUY", "SELL"]:
            mask = (event_df["coin"] == coin) & (event_df["signal"] == signal)
            if mask.any():
                groups.append(("coin_signal", coin, signal, mask))

    groups.append(("overall", "ALL", "BUY_OR_SELL", pd.Series(True, index=event_df.index)))

    for group_type, coin, signal_name, mask in groups:
        group_df = event_df[mask]
        for minutes in MINUTES_AFTER_TWEET:
            after_minutes_df = group_df[group_df["minutes_after_tweet"] == minutes]
            valid_df = after_minutes_df[after_minutes_df["is_prediction_correct"].notna()]
            correct = int((valid_df["is_prediction_correct"] == True).sum())
            wrong = int((valid_df["is_prediction_correct"] == False).sum())
            flat = int((after_minutes_df["is_price_flat"] == True).sum())
            tweets_without_price = int(
                (
                    after_minutes_df["start_price"].isna()
                    | after_minutes_df["target_price"].isna()
                ).sum()
            )
            denominator = correct + wrong
            if denominator:
                correct_percent = round(correct / denominator * 100, 2)
            else:
                correct_percent = pd.NA
            flat_denominator = correct + wrong + flat
            if flat_denominator:
                flat_ratio = round(flat / flat_denominator, 6)
            else:
                flat_ratio = pd.NA

            summary_rows.append(
                {
                    "group_type": group_type,
                    "coin": coin,
                    "LLM response signal": signal_name,
                    "minutes_after_tweet": minutes,
                    "total tweets": int(len(after_minutes_df)),
                    "tweets_without_price": tweets_without_price,
                    "correct": correct,
                    "wrong": wrong,
                    "flat": flat,
                    "flat_ratio": flat_ratio,
                    "correct_probability_percent": correct_percent,
                }
            )

    return pd.DataFrame(summary_rows)


def main():
    ollama_df = load_ollama_results(
        ollama_response_csv_files,
        tweet_account_by_coin,
    )

    coins = sorted(ollama_df["coin"].dropna().unique())
    price_maps = {
        coin: load_price_map(coin, binance_price_dataset_folders[coin])
        for coin in coins
    }

    event_df = make_event_rows(ollama_df, price_maps)
    summary_df = summarize_events(event_df)

    event_df.to_csv(by_event_out_csv_path, index=False)
    summary_df.to_csv(summary_out_csv_path, index=False)

    print(f"saved: {by_event_out_csv_path}")
    print(f"saved: {summary_out_csv_path}")


if __name__ == "__main__":
    main()
