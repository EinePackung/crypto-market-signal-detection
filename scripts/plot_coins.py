import pandas as pd
import matplotlib.pyplot as plt

# Load data
df = pd.read_csv("results/online_run_500.csv")

# Clean ticker names (e.g., convert '$BTC' to 'BTC', ignore empty values)
df['ticker'] = df['ticker'].astype(str).str.replace('$', '', regex=False).str.upper().str.strip()
df = df[~df['ticker'].isin(['NAN', 'NONE', '', 'UNKNOWN'])]

# Calculate the top 10 most mentioned coins
top_coins = df['ticker'].value_counts().head(10)

# Define colors
major_coins = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'BNB', 'ADA']
bar_colors = ['#f7931a' if coin in major_coins else '#95a5a6' for coin in top_coins.index]

# Bar chart
plt.figure(figsize=(10, 6))
top_coins.plot(kind="bar", color=bar_colors, edgecolor="black")

# Labeling
plt.title("Most Mentioned Cryptocurrencies in 500 Tweets", fontsize=15, fontweight='bold')
plt.xlabel("Coin Ticker", fontsize=12)
plt.ylabel("Number of Mentions", fontsize=12)
plt.xticks(rotation=0, fontsize=11)

import matplotlib.patches as mpatches
highlight_patch = mpatches.Patch(color='#f7931a', label='Major Crypto Assets')
other_patch = mpatches.Patch(color='#95a5a6', label='Other Altcoins')
plt.legend(handles=[highlight_patch, other_patch])

# Save
plt.tight_layout()
plt.savefig("results/top_coins.png", dpi=300)
print("Successfully saved: results/top_coins.png")