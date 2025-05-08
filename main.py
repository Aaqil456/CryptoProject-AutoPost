import os
import json
import time
import datetime
import requests
import base64

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

def fetch_tweets_rapidapi(username, max_tweets=10):
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

                        tweets.append({
                            "id": tweet_id,
                            "text": translated_text,
                            "images": media_urls,
                            "tweet_url": f"https://x.com/{screen_name}/status/{tweet_id}"
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
    gemini_url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    headers = {
        "Content-Type": "application/json"
    }
    payload = {
        "contents": [{
            "parts": [{
                "text": f"""First, check if the following content follows this exact template structure:
name: [Project Name]
Raised: $[Amount] | Stage: [Stage Name] | Has token: [Yes/No]
Investors: [Investor list or "Not disclosed"]
Description: [Description in one paragraph]
Twitter:
@[TwitterHandle]
If the structure does not match exactly — including the spacing and hyphens — return:
null
If the structure is valid, translate the content into Malay as follows:
Keep the format and spacing exactly the same.
Translate "Stage" to "fasa" but keep the phase (e.g. "Undisclosed", "Series A") in double quotes.
Translate "Has token: No" to Has token: (belum).
Translate the description to casual Malay in one paragraph.
At the end, translate "Twitter:" to "Twitter (akaun rasmi):" and retain the Twitter handle.
Do not include slang or shouting. Keep tone friendly, chill, and neutral.
Do not add any explanation or header. Just return the translated block as-is.
Input:
{text}"""
            }]
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

def post_to_wordpress(entry):
    credentials = f"{WP_USER}:{WP_APP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    headers = {
        "Authorization": f"Basic {token}",
        "Content-Type": "application/json"
    }

    images = entry.get("images", [])
    image_url = images[0] if images else None

    media_id = None
    uploaded_image_url = ""

    if image_url:
        try:
            img_resp = requests.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
            if img_resp.status_code == 200:
                file_name = image_url.split("/")[-1] or "image.jpg"
                media_headers = {
                    "Authorization": f"Basic {token}",
                    "Content-Disposition": f"attachment; filename={file_name}",
                    "Content-Type": "image/jpeg"
                }
                upload = requests.post(f"{WP_URL}/media", headers=media_headers, data=img_resp.content)
                if upload.status_code == 201:
                    media = upload.json()
                    media_id = media.get("id")
                    uploaded_image_url = media.get("source_url")
        except Exception as e:
            print(f"⚠️ Failed to upload image: {e}")

    content_html = f"<p>{entry['text']}</p>"
    if uploaded_image_url:
        content_html = f"<img src='{uploaded_image_url}' alt='tweet image' /><br>" + content_html
    if entry.get("tweet_url"):
        content_html += f"<p>📌 Sumber: <a href='{entry['tweet_url']}'>{entry['tweet_url']}</a></p>"

    post_data = {
        "title": entry["text"][:60].strip(),
        "content": content_html.strip(),
        "status": "private",
        "categories": [CATEGORY_ID]
    }
    if media_id:
        post_data["featured_media"] = media_id

    response = requests.post(f"{WP_URL}/posts", headers=headers, json=post_data)
    return response.status_code == 201

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

            success = post_to_wordpress(tweet)
            if success:
                print(f"✅ Posted: {tweet['tweet_url']}")
                result_data.append(tweet)
                existing_ids.add(tweet["id"])
            else:
                print(f"❌ Failed to post: {tweet['tweet_url']}")

    save_results(result_data)
    print("\n📦 All done.")
    print(json.dumps(result_data, indent=2, ensure_ascii=False))
