import os
import json
import datetime
import requests
import base64
import re

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


def extract_dashboard_fields(text):
    lines = text.split("\n")
    result = {}
    found_nama = False

    for i, line in enumerate(lines):
        clean_line = line.strip().lstrip("-").strip()
        lower_line = clean_line.lower()

        if lower_line.startswith("nama:"):
            result["nama"] = clean_line.split(":", 1)[1].strip()
            found_nama = True

        elif i == 0 and ":" in clean_line and not found_nama:
            result["nama"] = clean_line.replace(":", "").strip()
            found_nama = True

        elif "fasa:" in lower_line or "dana:" in lower_line or "ada token" in lower_line:
            parts = [part.strip().lstrip("-").strip() for part in clean_line.split("|")]
            for part in parts:
                part_lower = part.lower()
                if part_lower.startswith("dana:"):
                    result["dana"] = part.split(":", 1)[1].strip()
                elif "fasa:" in part_lower:
                    match = re.search(r'Fasa:\s*"?([^"]+)"?', part, re.IGNORECASE)
                    if match:
                        result["fasa"] = match.group(1).strip()
                elif "ada token" in part_lower:
                    token_match = re.search(r"Ada token:\s*\((.*?)\)", part, re.IGNORECASE)
                    if token_match:
                        value = token_match.group(1).strip().lower()
                        result["ada_token"] = "ada" if value == "ada" else "belum"

        elif lower_line.startswith("pelabur:"):
            result["pelabur"] = clean_line.split(":", 1)[1].strip()

        elif lower_line.startswith("deskripsi:"):
            result["deskripsi"] = clean_line.split(":", 1)[1].strip()

        elif lower_line.startswith("twitter"):
            # Special check to get Twitter handle from next line if handle is on new line
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("@"):
                result["twitter"] = lines[i + 1].strip()
            else:
                handle = clean_line.split(":", 1)[-1].strip()
                if handle.startswith("@"):
                    result["twitter"] = handle

    return result if "nama" in result else None



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

                        note_text = tweet_result.get("note_tweet", {}) \
                            .get("note_tweet_results", {}) \
                            .get("result", {}) \
                            .get("text")

                        tweet_legacy = tweet_result.get("legacy", {})
                        retweeted_legacy = tweet_result.get("retweeted_status_result", {}) \
                            .get("result", {}) \
                            .get("legacy", {})
                        quoted_legacy = tweet_result.get("quoted_status_result", {}) \
                            .get("result", {}) \
                            .get("legacy", {})

                        text = note_text or \
                               tweet_legacy.get("full_text") or \
                               retweeted_legacy.get("full_text") or \
                               quoted_legacy.get("full_text") or \
                               tweet_legacy.get("text", "")

                        media_urls = []
                        media = tweet_legacy.get("extended_entities", {}).get("media", []) or \
                                tweet_legacy.get("entities", {}).get("media", [])
                        for m in media:
                            if m.get("type") == "photo":
                                media_url = m.get("media_url_https") or m.get("media_url")
                                if media_url:
                                    media_urls.append(media_url)

                        if not text or not tweet_id:
                            continue

                        translated_text = translate_with_gemini(text.strip())
                        if not translated_text or translated_text == "null":
                            continue

                        # Extract dashboard fields from translated_text
                        dashboard_data = extract_dashboard_fields(translated_text)

                        tweets.append({
                            "id": tweet_id,
                            "text": translated_text,
                            "images": media_urls,
                            "tweet_url": f"https://x.com/{screen_name}/status/{tweet_id}",
                            "dashboard": dashboard_data
                        })

                        if len(tweets) >= max_tweets:
                            return tweets

                    except Exception as e:
                        print(f"[⚠️ Entry skipped due to error] {e}")
                        continue

        return tweets
    except Exception as e:
        print(f"❌ Exception fetching tweets for @{username}: {e}")
        return []


def translate_with_gemini(text):
    gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
    headers = {
        "Content-Type": "application/json"
    }
    prompt = f"""
You are a translation assistant. Given a block of text, your job is to check if it follows this structure:

Name: [Project Name]  
Raised: $[Amount] | Stage: [Stage Name] | Has token: [Yes/No]  
Investors: [Investor list or "Not disclosed"]  
Description: [One paragraph in English]  
Twitter:  
@[TwitterHandle]

✅ If the text DOES NOT follow this format (no need to be exactly identical — as long as the structure is similar) — respond only with:
null

✅ If the structure is valid, proceed with the following instructions:

1. Keep the overall structure, punctuation, indentation, and line breaks **exactly the same**.  
2. Only translate the **Description** paragraph into **Bahasa Melayu**.
3. Change **"Stage"** to **"Fasa"**, but keep the value in double quotes (e.g. "Series A").
4. Change **"Has token: No"** to **Ada token: (belum)**, and **"Has token: Yes"** to **Ada token: (ada)**.
5. Change **"Raised"** to **"Dana"**, and keep it in the same position in the line.
6. Change the label **"Twitter:"** to **"Twitter (akaun rasmi):"**, but keep the Twitter handle format untouched.
7. Do NOT add any explanations, summaries, or commentary. Return only the translated result in Bahasa Melayu.

👇 Below is the correct final format example (in Bahasa Melayu):

Nama: OrbitGrift  
Dana: $1.2 juta | Fasa: "Series A" | Ada token: (belum)  
Pelabur: Binance Labs dan 3 lain-lain  
Deskripsi: OrbitGrift ialah platform modular berasaskan rantaian blok yang membolehkan pembangun melancarkan aplikasi tersuai dengan sokongan interoperabiliti merentas ekosistem.  
Twitter (akaun rasmi):  
@OrbitGriftOfficial

Now process this:
{text}
""".strip()

    payload = {
        "contents": [{
            "parts": [{"text": prompt}]
        }]
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
