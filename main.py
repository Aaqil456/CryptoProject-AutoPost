# Re-execute final corrected full code block after reset

import os
import json
import datetime
import requests
import time


# === ENV ===
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
WP_URL = os.getenv("WP_API_URL")
WP_USER = os.getenv("WP_USER")
WP_APP_PASSWORD = os.getenv("WP_APP_PASS")
CATEGORY_ID = 1433
RESULTS_FILE = "results.json"
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

def load_existing_results():
    if os.path.exists(RESULTS_FILE):
        with open(RESULTS_FILE, "r", encoding="utf-8") as f:
            try:
                return json.load(f).get("data", [])
            except:
                return []
    return []

def save_results(data):
    final_result = {
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": data
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print("✅ All tweets processed and saved to results.json")

def extract_with_gemini_to_json(text, tweet_url=None, max_retries=3):
    gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {
        "Content-Type": "application/json"
    }

    prompt = f"""
    You are a data parser.

    Extract all available fields from the following project text and return the result in a valid JSON object using this exact structure:

    {{
      "nama": "...",
      "dana": "...",
      "fasa": "...",
      "ada_token": "...",
      "pelabur": "...",
      "deskripsi": "...",
      "twitter": "...",
      "tweet_url": "{tweet_url or '-'}"
    }}

    Rules:
    - If any field is not available, return "-" as the value.
    - Only use "ada" or "belum" for the "ada_token" field.
    - Do not include any explanations or extra text — just valid JSON.
    - Keep all formatting JSON-compatible, and do not return markdown.

    Text to process:
    {text}
    """.strip()

    payload = {
        "contents": [{ "parts": [{ "text": prompt }] }]
    }

    for attempt in range(max_retries):
        try:
            response = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", headers=headers, json=payload)
            if response.status_code == 200:
                gemini_data = response.json()
                output = gemini_data["candidates"][0]["content"]["parts"][0]["text"].strip()
                return json.loads(output)
            elif response.status_code == 429:
                print("🔁 Hit rate limit. Retrying in 6 seconds...")
                time.sleep(6)
            else:
                print("❌ Gemini JSON extractor error:", response.text)
                return None
        except Exception as e:
            print(f"❌ Gemini JSON extraction failed: {e}")
            return None

    print("❌ Max retries reached for Gemini.")
    return None

def translate_with_gemini(text):
    gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = { "Content-Type": "application/json" }
    prompt = f"""
You are a translation assistant. Given a block of text, your job is to check if it follows this structure:

name: [Project Name]  
Raised: $[Amount] | Stage: [Stage Name] | Has token: [Yes/No]  
Investors: [Investor list or "Not disclosed"]  
Description: [One paragraph in English]  
Twitter:  
@[TwitterHandle]  

✅ If the text DOES NOT follow this format — respond with: null

✅ If valid, follow these instructions:
- Keep all formatting and line breaks.
- Only translate the Description to Bahasa Melayu.
- Change "Stage" to "Fasa", "Has token" to "Ada token", and "Twitter:" to "Twitter (akaun rasmi):"
- Do not add any explanations.

Now process this:  
{text}
""".strip()

    payload = {
        "contents": [{ "parts": [{ "text": prompt }] }]
    }

    try:
        response = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", headers=headers, json=payload)
        if response.status_code == 200:
            gemini_data = response.json()
            return gemini_data["candidates"][0]["content"]["parts"][0]["text"].strip()
        else:
            print("❌ Gemini API Error:", response.text)
    except Exception as e:
        print(f"❌ Gemini translation failed: {e}")
    return None

def fetch_tweets_rapidapi(username, max_tweets=30):
    url = "https://twttrapi.p.rapidapi.com/user-tweets"
    querystring = {"username": username}
    headers = {
        "x-rapidapi-key": RAPIDAPI_KEY,
        "x-rapidapi-host": "twttrapi.p.rapidapi.com"
    }

    try:
        response = requests.get(url, headers=headers, params=querystring, timeout=30)
        if response.status_code != 200:
            return []

        data = response.json()
        tweets = []

        possible_paths = [
            data.get("user_result", {}).get("result", {}),
            data.get("data", {}).get("user_result", {}).get("result", {})
        ]

        instructions = []
        for path in possible_paths:
            timeline = path.get("timeline_response", {}).get("timeline", {})
            ins = timeline.get("instructions", [])
            if ins:
                instructions = ins
                break

        for instruction in instructions:
            if instruction.get("__typename") == "TimelineAddEntries":
                entries = instruction.get("entries", [])
                for entry in entries:
                    try:
                        tweet_result = entry.get("content", {}) \
                                            .get("content", {}) \
                                            .get("tweetResult", {}) \
                                            .get("result", {})

                        tweet_id = tweet_result.get("rest_id", "")
                        screen_name = tweet_result.get("core", {}) \
                            .get("user_result", {}) \
                            .get("result", {}) \
                            .get("legacy", {}) \
                            .get("screen_name", username)

                        text = tweet_result.get("note_tweet", {}) \
                            .get("note_tweet_results", {}) \
                            .get("result", {}) \
                            .get("text") or tweet_result.get("legacy", {}).get("full_text", "")

                        tweet_url = f"https://x.com/{screen_name}/status/{tweet_id}"
                        if not text or not tweet_id:
                            continue

                        translated_text = translate_with_gemini(text.strip())
                        if not translated_text or translated_text == "null":
                            continue

                        dashboard_info = extract_with_gemini_to_json(translated_text, tweet_url)
                        if not dashboard_info:
                            continue

                        tweets.append({
                            "id": tweet_id,
                            "text": translated_text,
                            "tweet_url": tweet_url,
                            "dashboard": dashboard_info
                        })

                        if len(tweets) >= max_tweets:
                            return tweets
                    except Exception as e:
                        print(f"[⚠️ Skipped] {e}")
                        continue
        return tweets
    except Exception as e:
        print(f"❌ Exception fetching tweets for @{username}: {e}")
        return []

if __name__ == "__main__":
    usernames = ["codeglitch"]
    existing = load_existing_results()
    existing_ids = set(e["id"] for e in existing if "id" in e)
    result_data = existing.copy()

    for username in usernames:
        tweets = fetch_tweets_rapidapi(username)
        for tweet in tweets:
            if tweet["id"] in existing_ids:
                print(f"⏭️ Skipped (already posted): {tweet['tweet_url']}")
                continue
            if not tweet["text"] or tweet["text"].strip().lower() == "null":
                print(f"❌ Skipped invalid translation: {tweet['tweet_url']}")
                continue
            result_data.append(tweet)
            existing_ids.add(tweet["id"])
            print(f"✅ Collected: {tweet['tweet_url']}")

    final_clean_data = [t for t in result_data if t.get("text") and t["text"].strip().lower() != "null"]
    save_results(final_clean_data)
    print("\n📦 All done.")
    print(json.dumps(final_clean_data, indent=2, ensure_ascii=False))
