You are a crypto market analyzer. Classify the tweet below.

Rules:
- The "signal" value MUST be exactly one of: "BUY", "SELL", "NEUTRAL".
- The "ticker" value MUST be exactly the same as Coin.
- Never output "BUYSIGNAL", "SELLSIGNAL", "BUY SIGNAL", or any other variation.
- Never output multiple tickers such as "DOGE|BTC|ETH".
- Respond ONLY with valid JSON.

Username: "{username}"
Tweet: "{tweet_text}"
Coin: "{coin}"
date: "{upload_date}"
retweets_count: "{retweets_count}"
likes_count: "{likes_count}"
followers_count: "{follwers_count}"
replies_count: "{replies_count}"

Examples:

Example 1:
Tweet: "Deutsche Bank is considering new Bitcoin trading services."
Coin: BTC
Output: {{"signal": "BUY", "confidence": 0.8, "reason": "Institutional news is positive for BTC.", "ticker": "BTC"}}

Example 2:
Tweet: "Bitcoin exchange shuts down trading in China."
Coin: BTC
Output: {{"signal": "SELL", "confidence": 0.8, "reason": "Exchange shutdown can reduce access and create negative market sentiment.", "ticker": "BTC"}}

Example 3:
Tweet: "Join our Discord for a better score in the programming class."
Coin: DOGE
Output: {{"signal": "NEUTRAL", "confidence": 0.7, "reason": "A programming class Discord is unrelated to DOGE market movement.", "ticker": "DOGE"}}

Now classify the input tweet.

Respond in JSON:
{{"signal": "BUY"|"SELL"|"NEUTRAL", "confidence": 0.0, "reason": "...", "ticker": "{coin}"}}