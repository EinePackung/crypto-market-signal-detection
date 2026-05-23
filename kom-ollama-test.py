#!/usr/bin/env python
#
# /// script
# requires-python = ">=3.8"
# dependencies = [
#     "langchain-ollama>=0.1.0",
#     "requests>=2.31.0",
#     "pandas",
#     "fsspec",
#     "huggingface_hub"
# ]
# ///
import json
import pandas as pd
from langchain_ollama import OllamaLLM

llm = OllamaLLM(
    model="llama3.1",
    base_url="http://10.0.100.10:11434",
    format="json"
)

# Load prompt
with open("prompts/predict_signal_v1.md") as f:
    prompt_template = f.read()

# Data load
df = pd.read_csv("hf://datasets/StephanAkkerman/financial-tweets/financial_tweets.csv")
# Number of Tweets
sample = df.head(500)


# Input into the LLM
results = []
for index, row in sample.iterrows():
    tweet_text = str(row["description"])
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



# Save
pd.DataFrame(results).to_csv("results/online_run_500.csv", index=False)
print("save complete: results/online_run_500.csv")