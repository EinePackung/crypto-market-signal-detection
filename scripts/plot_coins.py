import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Load data
df = pd.read_csv("results/online_run_1000.csv")

# Remove non alphabetic characters and normalize to uppercase
df['ticker'] = df['ticker'].astype(str).str.replace(r'[^A-Z]', '', regex=True)

# Filter for standard length (2-5 characters)
df = df[(df['ticker'].str.len() >= 2) & (df['ticker'].str.len() <= 5)]

# Remove noise, placeholder tokens, and non-crypto financial assets
filter_out = [
    'NAN', 'NONE', '', 'UNKNOWN',
    'NOTSPECIFIED', 'GENERAL', 'EURUSD', 'USD', 'ALL', 'NONE', 'NOT'
]
df = df[~df['ticker'].isin(filter_out)]


df = df[df['ticker'] != 'ALL']

# Calculate frequencies for the top 10
top_coins = df['ticker'].value_counts().head(10)

# Colors
major_coins = ['BTC', 'ETH', 'SOL', 'DOGE', 'XRP', 'BNB', 'ADA']
bar_colors = ['#f7931a' if coin in major_coins else '#95a5a6' for coin in top_coins.index]

# Generate bar chart
plt.figure(figsize=(10, 6))
top_coins.plot(kind='bar', color=bar_colors, edgecolor='black')

# Set labels and title
plt.title("Most Mentioned Cryptocurrencies in 1000 Tweets", fontsize=15, fontweight='bold')
plt.xlabel("Coin Ticker", fontsize=12)
plt.ylabel("Number of Mentions", fontsize=12)
plt.xticks(rotation=0, fontsize=11)

highlight_patch = mpatches.Patch(color='#f7931a', label='Major Crypto Assets')
other_patch = mpatches.Patch(color='#95a5a6', label='Other Altcoins')
plt.legend(handles=[highlight_patch, other_patch])

# Save
plt.tight_layout()
plt.savefig("results/top_coins1000.png", dpi=300)
print("Plot successfully saved.")