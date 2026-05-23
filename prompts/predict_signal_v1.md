You are a strictly constrained crypto market analyzer. Classify the financial sentiment of the tweet below.

CRITICAL RULES:
1. The "signal" key MUST be exactly one of these three strings: "BUY", "SELL", or "NEUTRAL". Absolutely no exceptions, no variations, and no invented words (NEVER use "BUYSIGNAL", "BUYN", "BUY N", or any other typo).
2. Respond ONLY with a valid, raw JSON object. Do not add any conversational text before or after the JSON.

Tweet: "{tweet_text}"

Required Output format:
{{"signal": "BUY"|"SELL"|"NEUTRAL", "confidence": 0.0-1.0, "reason": "...", "ticker": "..."}}