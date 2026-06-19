# Meeting Notes - 12.05.2026

## Discussion Summary
* Discussed the technical setup requirements, including establishing VPN and SSH access to the lab server.
* Received the initial test script (`kom-ollama.py`) to verify the local LLM environment.
* Discussed the general strategy for the LLM: feeding social media posts into the model and observing the raw text responses.
* Addressed the need to figure out how to convert the LLM's natural language responses into structured, machine readable output.
* Agreed on the necessity of defining specific classes for categorization, particularly a class to identify "buy" or "sell" recommendations in posts.
* Outlined the timeline for the project poster.

## Goals for the Next 2 Weeks
* **Technical Setup:** Establish the VPN and SSH connections and successfully test the `kom-ollama.py` script.
* **Dataset Exploration:** Review and analyze the provided crypto dataset.
* **LLM Input Strategy:** Develop a reliable method to feed posts into the LLM and evaluate the initial outputs.
* **Machine Output:** Implement a way to transform the LLM's text answers into machine output.
* **Define Classes:** Finalize the predefined classification categories (e.g. "buy/sell" signal class).
* **Poster Preparation:** Start working on the poster to ensure the draft is sent to Leo and Florian one day before the final submission deadline.


# Meeting Notes - 26.05.2026

## Goals for the Next 2 Weeks
* **LLM & Model Refinement:**
    * Test LLM performance on correct coin recognition from tweets.
    * Implement and check prediction confidence scores.
    * Explore zero-shot vs. few-shot inference techniques.
    * Investigate if pre-processing tweets improves model accuracy.

* **Data & Analysis:**
    * Verify and validate the price history database.
    * Analyze the correlation between social media influence (popular figures) and coin price.
    * Develop evaluation code to cross-reference price movements with tweet timestamps.

* **Poster & Presentation:**
    * Revise and refine the project poster layout and content.
    * Compare DOGE price history against Elon Musk's tweet activity for the poster demonstration.


# Meeting Notes - 09.06.2026

## Goals for the Next 2 Weeks
* **Start with the Report**

* **X API:**
    * Decision to exclude the integration of the X API
    * But technically possible

* **Code Refinement**
    * Filtering.
    * Price history.



