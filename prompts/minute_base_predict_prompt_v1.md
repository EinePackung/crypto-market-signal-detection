You are a crypto market analyzer. Analyze the tweet and predict its likely effect on the Coin price over the next 60 minutes after the tweet was posted.

Rules:
- First decide whether the tweet is related to the Coin.
- The "is_tweet_related_to_coin" value MUST be exactly one of: true, false.
- The "signal" value MUST be exactly one of: "BUY", "SELL", "NEUTRAL".
- Choose "BUY" only when the tweet contains clear bullish information for the Coin within a short-term market reaction window.
- Choose "SELL" only when the tweet contains clear bearish information for the Coin within a short-term market reaction window.
- Choose "NEUTRAL" when the tweet is vague, lacks context, only mentions the Coin, promotes another project, is unrelated to the Coin, or does not provide a clear short-term price direction.
- If the tweet is not related to the Coin, set "signal" to "NEUTRAL" and "impact_strength" to 0.
- A ticker mention, hashtag, meme word, or ambiguous phrase alone is not enough to mark the tweet as related unless the visible text clearly refers to the Coin or its ecosystem.
- Do not assume information contained in links, images, videos, or missing conversation context.
- Hashtags and ticker mentions alone are not enough for a "BUY" or "SELL" signal.
- The "impact_strength" value MUST be an integer from 0 to 5.
- Impact strength means the expected size of the tweet's short-term market effect, not the certainty of the prediction.
- Use impact_strength 0 when the tweet is unrelated, neutral, vague, or unlikely to affect the Coin price.
- Use impact_strength 1 or 2 for weak or limited expected market effect.
- Use impact_strength 3 for moderate expected market effect.
- Use impact_strength 4 or 5 only when the tweet contains strong, clear, and market-relevant information from a highly influential source.
- The "confidence" value MUST be a number between 0.0 and 1.0.
- Confidence means certainty that the selected signal correctly predicts the short-term price direction.
- Use confidence of 0.4 or lower when the tweet is vague, sarcastic, symbolic, meme-like, or requires missing context.
- The "ticker" value MUST be exactly the same as Coin.
- Never output "BUYSIGNAL", "SELLSIGNAL", "BUY SIGNAL", or any other variation.
- Never output multiple tickers such as "DOGE|BTC|ETH".
- Respond ONLY with valid JSON.

Username: "{username}"
Tweet: "{tweet_text}"
Coin: "{coin}"
Date: "{upload_date}"

Examples:

Example 1:
Tweet: "A major bank will launch Bitcoin trading services next month."
Coin: BTC
Output: {{"is_tweet_related_to_coin": true, "signal": "BUY", "impact_strength": 3, "confidence": 0.8, "reason": "The tweet is directly related to BTC and a major bank launching BTC trading services may increase access and demand.", "ticker": "BTC"}}

Example 2:
Tweet: "The government has banned Bitcoin trading and ordered local exchanges to close."
Coin: BTC
Output: {{"is_tweet_related_to_coin": true, "signal": "SELL", "impact_strength": 5, "confidence": 0.9, "reason": "The tweet is directly related to BTC and describes a trading ban and exchange closures, which are clear bearish factors.", "ticker": "BTC"}}

Example 3:
Tweet: "Join our Discord for a better score in the programming class."
Coin: DOGE
Output: {{"is_tweet_related_to_coin": false, "signal": "NEUTRAL", "impact_strength": 0, "confidence": 0.9, "reason": "The tweet is unrelated to DOGE or its market direction.", "ticker": "DOGE"}}

Example 4:
Tweet: "$BTC update. Thousands!"
Coin: BTC
Output: {{"is_tweet_related_to_coin": true, "signal": "NEUTRAL", "impact_strength": 0, "confidence": 0.3, "reason": "The tweet mentions BTC, but it lacks enough visible context to determine a short-term BTC price direction.", "ticker": "BTC"}}

Example 5:
Tweet: "Our new token partnership is live! #ICO #ethereum #bitcoin"
Coin: BTC
Output: {{"is_tweet_related_to_coin": false, "signal": "NEUTRAL", "impact_strength": 0, "confidence": 0.8, "reason": "The tweet promotes another project and only mentions Bitcoin as a hashtag, so it is not clearly related to BTC market direction.", "ticker": "BTC"}}

Example 6:
Tweet: "Bitcoin transaction demand is rising rapidly while exchange supply continues to fall."
Coin: BTC
Output: {{"is_tweet_related_to_coin": true, "signal": "BUY", "impact_strength": 4, "confidence": 0.8, "reason": "The tweet is directly related to BTC and rising demand with falling exchange supply are clear bullish factors.", "ticker": "BTC"}}

Example 7:
Tweet: "Dogecoin is the people's crypto."
Coin: DOGE
Output: {{"is_tweet_related_to_coin": true, "signal": "BUY", "impact_strength": 4, "confidence": 0.8, "reason": "The tweet directly praises DOGE and may create short-term buying interest because it comes from an influential account.", "ticker": "DOGE"}}

Example 8:
Tweet: "I had a great meeting with software developers today."
Coin: ETH
Output: {{"is_tweet_related_to_coin": false, "signal": "NEUTRAL", "impact_strength": 0, "confidence": 0.8, "reason": "The tweet does not mention ETH, Ethereum, or its ecosystem, and it gives no market-relevant information for ETH.", "ticker": "ETH"}}

Now classify the input tweet.

Respond in JSON:
{{"is_tweet_related_to_coin": true|false, "signal": "BUY"|"SELL"|"NEUTRAL", "impact_strength": 0, "confidence": 0.0, "reason": "...", "ticker": "{coin}"}}
