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
prompt_path = "prompts/minute_base_predict_prompt_v1.md"
with open(prompt_path) as default_prompt_file:
    prompt_template = default_prompt_file.read()

# 3. Data load from local
datasets_path = "data/standardized_influencer_tweets.csv"
coin = "DOGE"
out_csv_file = "results/ollama-response_influencer/DOGE/DOGE_minute_base_llm_result.csv"

# Python row ranges: start row is included, end row is excluded.
btc_start_row = 0
btc_end_row = 328
eth_start_row = 328
eth_end_row = 742
doge_start_row = 742
doge_end_row = 48877
trump_start_row = 48877
trump_end_row = 55269

is_btc = coin == "BTC"
is_eth = coin == "ETH"
is_doge = coin == "DOGE"
is_trump = coin == "TRUMP"

if is_btc:
    ollama_input_start_row = btc_start_row
    ollama_input_end_row = btc_end_row
elif is_eth:
    ollama_input_start_row = eth_start_row
    ollama_input_end_row = eth_end_row
elif is_doge:
    ollama_input_start_row = doge_start_row
    ollama_input_end_row = doge_end_row
elif is_trump:
    ollama_input_start_row = trump_start_row
    ollama_input_end_row = trump_end_row
else:
    raise ValueError("coin must be BTC, ETH, DOGE, or TRUMP")

df = pd.read_csv(datasets_path, dtype={"tweet_id": "string"}, low_memory=False)
df = df.iloc[ollama_input_start_row:ollama_input_end_row]


# Prevention from wrong response of LLM
def check_response_coin_related(value):
    if value is True or value == "true":
        return True
    return False


def check_response_impact_strength(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, min(5, value))


def check_response_confidence(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return max(0.0, min(1.0, value))


# 4. Input into the LLM
results = []
for index, row in df.iterrows():
    username_from_datasets = str(row["username"])
    tweet_text_from_datasets = str(row["tweet"])
    upload_date_from_datasets = str(row["created_at_utc"])

    prompt = prompt_template.format(
        username=username_from_datasets,
        tweet_text=tweet_text_from_datasets,
        coin=coin,
        upload_date=upload_date_from_datasets
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

        is_tweet_related_to_coin = check_response_coin_related(
            parsed.get("is_tweet_related_to_coin")
        )
        impact_strength = check_response_impact_strength(parsed.get("impact_strength"))
        confidence = check_response_confidence(parsed.get("confidence"))

        print(f"tweet #{index + 1}: {tweet_text_from_datasets[:80]}...")
        print(f"parsed: {parsed}")
        results.append({
            "coin": coin,
            "source_dataset": row["source_dataset"],
            "source_row_number": row["source_row_number"],
            "tweet_id": row["tweet_id"],
            "tweet_url": row["tweet_url"],
            "text": tweet_text_from_datasets,
            "is_tweet_related_to_coin": is_tweet_related_to_coin,
            "signal": signal,
            "impact_strength": impact_strength,
            "confidence": confidence,
            "reason": parsed.get("reason"),
            "ticker": ticker,
            "username": username_from_datasets,
            "influencer_name": row["influencer_name"],
            "created_at_utc": upload_date_from_datasets
        })

        # The DOGE dataset is large, so keep the latest result when stopped manually.
        if len(results) % 10 == 0:
            pd.DataFrame(results).to_csv(out_csv_file, index=False)

    except Exception as e:
        print(f"Error connecting to Ollama: {e}")


# 5. Save the result
pd.DataFrame(results).to_csv(out_csv_file, index=False)
print(f"save complete: ", out_csv_file)
