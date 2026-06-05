from datetime import timedelta

import pandas as pd
import json

from numpy.f2py.auxfuncs import throw_error


price_dataset_path = "data/CrypTop12-main/price/raw/btc.csv"
result_dataset_path = "results/ollama_response/btc/2017_10_04_with_prompt_v4_no_filtered.csv"


def load_price_dataset():
    with open(price_dataset_path) as price_dataset:
        df = pd.read_csv(price_dataset)
        return df

def load_close_price_dataset_with_date(date):
    with open(price_dataset_path) as price_dataset:
        df = pd.read_csv(price_dataset)

        for index, row in df.iterrows():
            if str(row["Date"]) == date:
                return float(row["Close"])

        return None

def load_open_price_dataset_with_date(date):
    with open(price_dataset_path) as price_dataset:
        df = pd.read_csv(price_dataset)

        for index, row in df.iterrows():
            if str(row["Date"]) == date:
               return float(row["Open"])

        return None


def load_ollama_response_result():
    with open(result_dataset_path) as results_dataset:
        df = pd.read_csv(results_dataset)
        return df


def calculate_price_change_on_date(date):

    tweet_day_open_price = load_open_price_dataset_with_date(date)
    tweet_day_close_price = load_close_price_dataset_with_date(date)

    if tweet_day_open_price is None or tweet_day_close_price is None:
        return None

    return tweet_day_close_price - tweet_day_open_price

def calculate_price_change_until_next_day(date):
    tweet_day_close_price = load_close_price_dataset_with_date(date)
    df = load_price_dataset()
    df = df.sort_values("Date").reset_index(drop=True)

    for index, row in df.iterrows():
        if str(row["Date"]) == str(date):
            if index +1 >= len(df): return None

            else:
                next_day_close_price = float(df.iloc[index+1]["Close"])
                return next_day_close_price - tweet_day_close_price

    return None


def evaluate_signal (result_csv):

    evaluation_result = result_csv.copy()


    for index, row in result_csv.iterrows():
        signal = str(row["signal"])
        date = str(row["created_at"])[:10]
        price_change = calculate_price_change_until_next_day(date)

        if price_change is None:
            evaluation = "error"
        elif signal == "BUY":
            if price_change > 0:
                evaluation = "correct"
            else:
                evaluation = "incorrect"

        elif signal == "SELL":
            if  price_change < 0:
                evaluation = "correct"
            else:
                evaluation = "incorrect"

        elif signal == "NEUTRAL":
            if abs(price_change) <= load_close_price_dataset_with_date(date) * 0.01:
                evaluation = "correct"
            else:
                evaluation = "incorrect"


        evaluation_result.at[index, "evaluation"] = evaluation

    save(evaluation_result)

def save (evaluated_csv):
    save_path = "results/evaluated/btc/2017_10_04_with_prompt_v4_no_filtered_evaluated.csv"
    pd.DataFrame(evaluated_csv).to_csv(save_path, index=False)
    print(f"save complete: ", save_path)


result_csv = load_ollama_response_result()
evaluate_signal(result_csv)
