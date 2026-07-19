#!/usr/bin/env python3

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


# Input datasets
# CrypTop12: https://github.com/am15h/CrypTop12
# Elon Musk Tweets: https://www.kaggle.com/datasets/dadalyndell/elon-musk-tweets-2010-to-2025-march
# Trump Tweets: https://www.kaggle.com/datasets/datadrivendecision/trump-tweets-2009-2025
# Bitcoin Tweets (source of the Nayib Bukele rows):
# https://www.kaggle.com/datasets/kaushiksuresh147/bitcoin-tweets
cryp_top12_raw_folder = Path("data/CrypTop12-main/tweet/raw")
elon_musk_tweets_csv = "data/Elon Musk Tweets/all_musk_posts.csv"
trump_tweets_csv = "data/Trump Tweets(2009-2025).csv"

# Output dataset
standardized_tweets_out_csv = "data/standardized_influencer_tweets.csv"

# DOGE starts with Elon Musk's first clear Dogecoin tweet.
doge_start_date = "2019-04-02 09:24:39+00:00"

# TRUMP starts with Donald Trump's first TRUMP coin launch announcement.
trump_start_date = "2025-01-18 02:00:51+00:00"

# Elon Musk is intentionally not included here. DOGE uses all_musk_posts.csv,
# so CrypTop12 Elon Musk rows would only duplicate the same tweets.
selected_cryp_top12_accounts = {
    "michael_saylor": ("BTC", "Michael Saylor"),
    "jack": ("BTC", "Jack Dorsey"),
    "vitalikbuterin": ("ETH", "Vitalik Buterin"),
    "timbeiko": ("ETH", "Tim Beiko"),
    "ethereum": ("ETH", "Ethereum official"),
    "ethdotorg": ("ETH", "ethereum.org"),
}

# CrypTop12 has no matching @nayibbukele rows. These are the two selected
# @nayibbukele rows verified in data/Bitcoin Tweets/Bitcoin_tweets.csv.
nayib_bukele_tweets = [
    {
        "coin": "BTC",
        "source_dataset": "data/Bitcoin Tweets/Bitcoin_tweets.csv",
        "tweet_id": "",
        "tweet_url": "",
        "username": "nayibbukele",
        "influencer_name": "Nayib Bukele",
        "tweet": "You’re telling me we should buy more #BTC? https://t.co/jwvn0A1kTb",
        "created_at_utc": "2022-06-14T19:59:36Z",
        "replies_count": "",
        "retweets_count": "",
        "likes_count": "",
        "Follower_count": 4009318,
    },
    {
        "coin": "BTC",
        "source_dataset": "data/Bitcoin Tweets/Bitcoin_tweets.csv",
        "tweet_id": "",
        "tweet_url": "",
        "username": "nayibbukele",
        "influencer_name": "Nayib Bukele",
        "tweet": (
            "I see that some people are worried or anxious about the #Bitcoin market price.\n\n"
            "My advice: stop looking at the graph and enjoy life. If you invested in #BTC "
            "your investment is safe and its value will immensely grow after the bear market.\n\n"
            "Patience is the key."
        ),
        "created_at_utc": "2022-06-19T03:04:01Z",
        "replies_count": "",
        "retweets_count": "",
        "likes_count": "",
        "Follower_count": 4017517,
    },
]

ist = timezone(timedelta(hours=5, minutes=30))


def change_ist_to_utc(created_at):
    created_at = str(created_at).replace(" IST", "")
    created_at = datetime.strptime(created_at, "%Y-%m-%d %H:%M:%S")
    created_at = created_at.replace(tzinfo=ist).astimezone(timezone.utc)
    return created_at.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_cryp_top12_dataset():
    selected_tweets = {}

    for coin_folder in sorted(cryp_top12_raw_folder.iterdir()):
        if not coin_folder.is_dir():
            continue

        for json_file in sorted(coin_folder.glob("*.json")):
            with open(json_file, encoding="utf-8") as tweet_file:
                for line in tweet_file:
                    tweet_data = json.loads(line)
                    username = str(tweet_data.get("username", "")).strip().lower()

                    if username not in selected_cryp_top12_accounts:
                        continue

                    coin, influencer_name = selected_cryp_top12_accounts[username]
                    tweet_id = str(tweet_data.get("id_str") or tweet_data.get("id") or "")
                    duplicate_key = (coin, tweet_id)

                    if duplicate_key in selected_tweets:
                        continue

                    selected_tweets[duplicate_key] = {
                        "coin": coin,
                        "source_dataset": str(json_file),
                        "tweet_id": tweet_id,
                        "tweet_url": f"https://x.com/{username}/status/{tweet_id}",
                        "username": username,
                        "influencer_name": influencer_name,
                        "tweet": str(tweet_data.get("tweet", "")),
                        "created_at_utc": change_ist_to_utc(tweet_data["created_at"]),
                        "replies_count": tweet_data.get("replies_count", ""),
                        "retweets_count": tweet_data.get("retweets_count", ""),
                        "likes_count": tweet_data.get("likes_count", ""),
                        "Follower_count": tweet_data.get("Follower_count", ""),
                    }

    return pd.DataFrame(selected_tweets.values())


def make_btc_dataset(cryp_top12_df):
    btc_df = cryp_top12_df[cryp_top12_df["coin"] == "BTC"].copy()
    btc_df = pd.concat([btc_df, pd.DataFrame(nayib_bukele_tweets)], ignore_index=True)
    btc_df = btc_df.sort_values(["created_at_utc", "username", "tweet_id"])
    btc_df["source_row_number"] = range(1, len(btc_df) + 1)
    return btc_df


def make_eth_dataset(cryp_top12_df):
    eth_df = cryp_top12_df[cryp_top12_df["coin"] == "ETH"].copy()
    eth_df = eth_df.sort_values(["created_at_utc", "username", "tweet_id"])
    eth_df["source_row_number"] = range(1, len(eth_df) + 1)
    return eth_df


def make_doge_dataset():
    elon_df = pd.read_csv(elon_musk_tweets_csv, dtype={"id": "string"}, low_memory=False)
    elon_df["source_row_number"] = elon_df.index + 1
    elon_df["created_at_utc"] = pd.to_datetime(elon_df["createdAt"], utc=True)
    elon_df = elon_df[elon_df["created_at_utc"] >= pd.Timestamp(doge_start_date)].copy()

    doge_df = pd.DataFrame({
        "coin": "DOGE",
        "source_dataset": elon_musk_tweets_csv,
        "source_row_number": elon_df["source_row_number"],
        "tweet_id": elon_df["id"].fillna(""),
        "tweet_url": elon_df["url"].fillna(elon_df["twitterUrl"]).fillna(""),
        "username": "elonmusk",
        "influencer_name": "Elon Musk",
        "tweet": elon_df["fullText"].fillna(""),
        "created_at_utc": elon_df["created_at_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "replies_count": elon_df["replyCount"].fillna(""),
        "retweets_count": elon_df["retweetCount"].fillna(""),
        "likes_count": elon_df["likeCount"].fillna(""),
        "Follower_count": "",
    })
    return doge_df


def make_trump_dataset():
    trump_df = pd.read_csv(trump_tweets_csv, dtype={"id": "string"}, low_memory=False)
    trump_df["source_row_number"] = trump_df.index + 1
    trump_df["created_at_utc"] = pd.to_datetime(trump_df["date"], utc=True)
    trump_df = trump_df[trump_df["created_at_utc"] >= pd.Timestamp(trump_start_date)].copy()

    trump_coin_df = pd.DataFrame({
        "coin": "TRUMP",
        "source_dataset": trump_tweets_csv,
        "source_row_number": trump_df["source_row_number"],
        "tweet_id": trump_df["id"].fillna(""),
        "tweet_url": trump_df["post_url"].fillna(""),
        "username": trump_df["handle"].fillna(""),
        "influencer_name": "Donald Trump",
        "tweet": trump_df["text"].fillna(""),
        "created_at_utc": trump_df["created_at_utc"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "replies_count": "",
        "retweets_count": trump_df["repost_count"].fillna(""),
        "likes_count": trump_df["favorite_count"].fillna(""),
        "Follower_count": "",
    })
    return trump_coin_df


def make_standardized_dataset():
    cryp_top12_df = make_cryp_top12_dataset()
    btc_df = make_btc_dataset(cryp_top12_df)
    eth_df = make_eth_dataset(cryp_top12_df)
    doge_df = make_doge_dataset()
    trump_df = make_trump_dataset()

    standardized_df = pd.concat(
        [btc_df, eth_df, doge_df, trump_df],
        ignore_index=True,
    )
    standardized_df.insert(0, "dataset_row_number", range(1, len(standardized_df) + 1))

    return standardized_df[[
        "dataset_row_number",
        "coin",
        "source_dataset",
        "source_row_number",
        "tweet_id",
        "tweet_url",
        "username",
        "influencer_name",
        "tweet",
        "created_at_utc",
        "replies_count",
        "retweets_count",
        "likes_count",
        "Follower_count",
    ]]


def save_csv_file(standardized_df, out_csv_file):
    standardized_df.to_csv(out_csv_file, index=False)
    print(f"save complete: {out_csv_file}")

    for coin, coin_df in standardized_df.groupby("coin", sort=False):
        start_row = coin_df.index.min()
        end_row = coin_df.index.max() + 1
        print(f"{coin}: rows {start_row}:{end_row} ({len(coin_df)} tweets)")


standardized_df = make_standardized_dataset()
save_csv_file(standardized_df, standardized_tweets_out_csv)
