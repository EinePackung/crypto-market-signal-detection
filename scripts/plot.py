import pandas as pd
import matplotlib.pyplot as plt

# Load the new CSV file
df = pd.read_csv("results/online_run_500.csv")

# FILTER: Only keep the valid signals
valid_signals = ["BUY", "SELL", "NEUTRAL"]
df = df[df["signal"].isin(valid_signals)]

# Count how often each signal occurs
counts = df["signal"].value_counts()

# Create a bar chart
plt.figure(figsize=(8, 6))

# Assign matching colors directly to the signals
colors = {'BUY': '#2ca02c', 'NEUTRAL': '#7f7f7f', 'SELL': '#d62728'}
bar_colors = [colors.get(x, '#333333') for x in counts.index]

counts.plot(kind="bar", color=bar_colors, edgecolor="black")

# Label the chart
plt.title("Distribution of AI Signals (500 Crypto Tweets)", fontsize=14)
plt.xlabel("Detected Signal", fontsize=12)
plt.ylabel("Number of Tweets", fontsize=12)
plt.xticks(rotation=0) # Keeps BUY/SELL straight and readable

# Save the image
plt.tight_layout()
plt.savefig("results/signal_distribution_clean.png", dpi=300)
print("Successfully saved: results/signal_distribution_clean.png")
