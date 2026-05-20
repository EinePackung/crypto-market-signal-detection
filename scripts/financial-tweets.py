import pandas as pd

df = pd.read_csv("hf://datasets/StephanAkkerman/financial-tweets/financial_tweets.csv")

print(df.head())
print(df.columns)
print(len(df))