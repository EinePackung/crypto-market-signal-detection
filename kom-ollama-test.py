# ]
# ///

from langchain_ollama import OllamaLLM
import pandas as pd
import json
import os

# Configure the Ollama instance
llm = OllamaLLM(
    model="llama3.1",
    base_url="http://10.0.100.10:11434"
)

# Path to your CSV file
csv_file = "test_tweets.csv"

# Check if the file exists before running
if not os.path.exists(csv_file):
    print(f"Error: The file '{csv_file}' was not found.")
    print("Please create it or upload it to the directory first.")
    exit(1)

# Read the CSV file using pandas
print(f"Reading dataset from {csv_file}...")
df = pd.read_csv(csv_file)

# You need a CSV file with e.g. text "Bitcoin is breaking resistance right now! Institutional whales are accumulating. HODL to the moon! 🚀 #BTC"
if 'text' not in df.columns:
    print("Error: CSV must contain a column named 'text'")
    exit(1)

print(f"Found {len(df)} rows. Starting analysis with Llama 3.1...\n")

# Base Prompt template
system_prompt_base = """
You are a crypto market analysis tool. Analyze the tweet below and classify it into one of these signals: BUY, SELL, or NEUTRAL.

You must output NOTHING else except a single, valid JSON object. Do not include introductory text, markdown formatting blocks (like ```json), or conversational commentary.

Expected JSON format:
{
  "signal": "BUY",
  "confidence": 0.89,
  "reason": "Short explanation here"
}

Tweet to analyze: """

# Loop through each row in the CSV
for index, row in df.iterrows():
    tweet_text = str(row['text'])
    print(f"--- Analyzing Tweet #{index + 1} ---")
    print(f"Text: {tweet_text}")

    # Combine the base prompt with the specific tweet text
    prompt = system_prompt_base + '"' + tweet_text + '"'

    try:
        # Invoke the local LLM
        response = llm.invoke(prompt)
        print("Ollama Response:")
        print(response)
        print("-" * 40 + "\n")
    except Exception as e:
        print(f"Error connecting to Ollama on row {index + 1}: {e}\n")
