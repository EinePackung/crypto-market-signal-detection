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
with open("prompts/predict_signal_v1.md") as f:
    prompt_template = f.read()

# 3. Data load from local
df = pd.read_csv("data/Bitcoin Tweets/Bitcoin_tweets.csv")
sample = df.head(5)


# 4. Input into the LLM
results = []
for index, row in sample.iterrows():
    tweet_text = str(row["text"])
    prompt = prompt_template.format(tweet_text=tweet_text)

    try:
        response = llm.invoke(prompt)
        parsed = json.loads(response)

        print(f"tweet #{index + 1}: {tweet_text[:80]}...")
        print(f"parsed: {parsed}")
        results.append({
            "text": tweet_text,
            "signal": parsed.get("signal"),
            "confidence": parsed.get("confidence"),
            "reason": parsed.get("reason"),
            "ticker": parsed.get("ticker")
        })

    except Exception as e:
        print(f"Error connecting to Ollama: {e}")



# 5. Save the result
pd.DataFrame(results).to_csv("results/test_run_v1.csv", index=False)
print("save complete: results/test_run_v1.csv")






