You are a crypto market analyzer. Classify the tweet below.

Username: "{username}" 
Tweet: "{tweet_text}"
Coin: "{coin}"
date: "{upload_date}"
retweets_count: "{retweets_count}"
likes_count: "{likes_count}"
follwers_count: "{follwers_count}"
replies_count: "{replies_count}"

Respond in JSON:
{{"signal": "BUY"|"SELL"|"NEUTRAL", "confidence": 0.0-1.0, "reason": "...", "ticker": "DOGE|BTC|ETH|SOL|XRP|ADA"}}

