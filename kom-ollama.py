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
prompt_path = "prompts/predict_signal_v5.md"
with open(prompt_path) as default_prompt_file :
    prompt_template = default_prompt_file.read()

# 3. Data load from local
datasets_path = "data/TEST_DATASET_LLM_RESULT.JSON"
coin = "BTC"
df = pd.read_json(datasets_path, lines=True)

MIN_FOLLOWERS = 100000
MIN_LIKES = 100
MIN_RETWEETS = 50
MIN_REPLIES = 5

HIGH_FOLLOWERS = 1000000
HIGH_LIKES = 250
HIGH_RETWEETS = 200
HIGH_REPLIES = 25


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


df["popularity_label"] = "TEST"

# 4. Input into the LLM
results = []
for index, row in df.iterrows():
    username_from_datasets = str(row["username"])
    tweet_text_from_datasets = str(row["tweet"])
    upload_date_from_datasets = str(row["created_at"])
    retweets_count_from_datasets = str(row["retweets_count"])
    likes_count_from_datasets = str(row["likes_count"])
    follwers_count_from_datasets = str(row["Follower_count"])
    replies_count_from_datasets = str(row["replies_count"])

    prompt = prompt_template.format(
        username=username_from_datasets,
        tweet_text=tweet_text_from_datasets,
        coin=coin,
        upload_date=upload_date_from_datasets,
        retweets_count=retweets_count_from_datasets,
        likes_count=likes_count_from_datasets,
        follwers_count=follwers_count_from_datasets,
        replies_count=replies_count_from_datasets
    )

    try:
        response = llm.invoke(prompt)
        parsed = json.loads(response)

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

        print(f"tweet #{index + 1}: {tweet_text_from_datasets[:80]}...")
        print(f"parsed: {parsed}")
        results.append({
            "text": tweet_text_from_datasets,
            "signal": signal,
            "confidence": parsed.get("confidence"),
            "reason": parsed.get("reason"),
            "ticker": ticker,
            "username": username_from_datasets,
            "created_at": upload_date_from_datasets,
            "retweets_count": retweets_count_from_datasets,
            "likes_count": likes_count_from_datasets,
            "followers_count": follwers_count_from_datasets,
            "replies_count": replies_count_from_datasets,
            "popularity_label": row["popularity_label"]
        })

    except Exception as e:
        print(f"Error connecting to Ollama: {e}")



# 5. Save the result
save_path = "results/TEST_LLM_RESULT.csv"
pd.DataFrame(results).to_csv(save_path, index=False)
print(f"save complete: ", save_path)
