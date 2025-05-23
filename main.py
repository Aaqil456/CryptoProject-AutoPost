import os
import json
import datetime
import requests
import base64
import re
import time

# === ENV ===
RAPIDAPI_KEY = os.getenv("RAPIDAPI_KEY")
FB_PAGE_ID = os.getenv("FB_PAGE_ID")
LONG_LIVED_USER_TOKEN = os.getenv("LONG_LIVED_USER_TOKEN")
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


def get_fb_token():
    try:
        res = requests.get(f"https://graph.facebook.com/v19.0/me/accounts?access_token={LONG_LIVED_USER_TOKEN}")
        return res.json()["data"][0]["access_token"]
    except Exception as e:
        print("[FB Token Error]", e)
        return None


def post_text_only_to_fb(token, caption):
    try:
        r = requests.post(
            f"https://graph.facebook.com/{FB_PAGE_ID}/feed",
            data={"message": caption, "access_token": token}
        )
        if r.status_code != 200:
            print(f"[FB API ERROR] {r.status_code}: {r.text[:300]}")
        return r.status_code == 200
    except Exception as e:
        print("[FB Post Error]", e)
        return False


def save_results(data):
    final_result = {
        "last_updated": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data": data
    }
    with open(RESULTS_FILE, "w", encoding="utf-8") as f:
        json.dump(final_result, f, ensure_ascii=False, indent=2)
    print("✅ All tweets processed and saved to results.json")


def post_results_to_facebook(data):
    token = get_fb_token()
    if not token:
        print("❌ Gagal dapat token Facebook.")
        return

    fb_posted_count = 0
    fb_posted_list = []

    for entry in data:
        if entry.get("fb_status") == "Posted":
            continue

        dashboard = entry.get("dashboard")
        if not isinstance(dashboard, dict):
            print(f"[⚠️ SKIPPED] No dashboard data for {entry.get('id')}")
            continue

        nama = dashboard.get("nama", "-")
        dana = dashboard.get("dana", "-")
        fasa = dashboard.get("fasa", "-")
        token_status = dashboard.get("ada_token", "-")
        pelabur = dashboard.get("pelabur", "-")
        deskripsi = dashboard.get("deskripsi", "-")
        twitter = dashboard.get("twitter", "-")

        caption = (
            f"📌 Nama Projek: {nama}\n"
            f"💰 Dana: {dana}\n"
            f"🚀 Fasa: \"{fasa}\"\n"
            f"🪙 Token: ({token_status})\n"
            f"💼 Pelabur: {pelabur}\n"
            f"𝕏 Akaun: {twitter}\n\n"
            f"📖 Deskripsi:\n{deskripsi}\n"
        )

        success = post_text_only_to_fb(token, caption)
        if success:
            entry["fb_status"] = "Posted"
            entry["date_posted"] = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            fb_posted_count += 1
            fb_posted_list.append(nama)
            print(f"[✅ FB POSTED] {nama}")
        else:
            print(f"[❌ FB FAILED] {nama}")

    if fb_posted_count:
        print("\n📢 FB POST SUMMARY:")
        for i, name in enumerate(fb_posted_list, 1):
            print(f"{i}. {name}")
        print(f"\n✅ Jumlah yang berjaya dihantar ke FB: {fb_posted_count}")
    else:
        print("\n⚠️ Tiada yang dihantar ke FB.")






def extract_dashboard_fields(text):
    lines = text.split("\n")
    result = {}
    found_nama = False

    for i, line in enumerate(lines):
        clean_line = line.strip().lstrip("-").strip()
        lower_line = clean_line.lower()

        # Nama: ...  atau fallback line pertama "Wildcard:"
        if lower_line.startswith("nama:"):
            result["nama"] = clean_line.split(":", 1)[1].rstrip(":").strip()
            found_nama = True
        elif i == 0 and ":" in clean_line and not found_nama:
            result["nama"] = clean_line.rstrip(":").strip()
            found_nama = True

        # Dana / Raised / Fasa / Ada token
        elif "fasa:" in lower_line or "dana:" in lower_line or "raised:" in lower_line or "ada token" in lower_line:
            parts = [part.strip().lstrip("-").strip() for part in clean_line.split("|")]
            for part in parts:
                part_lower = part.lower()
                if part_lower.startswith("dana:") or part_lower.startswith("raised:"):
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
            # Cuba dapatkan dari next line jika handle di bawah
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



def translate_with_gemini(text, max_retries=5):
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

✅ BEFORE PROCESSING:
- If the first line looks like a project name ending with a colon (e.g. `Deribit:`), and there is no line starting with "Name:", treat that line as the project name and prepend "Nama: (first_line)" at the beginning.
- Remove markdown code fences (e.g. triple backticks ```).

✅ If the structure is valid, proceed with the following instructions:

1. Keep the overall structure, punctuation, indentation, and line breaks **exactly the same**.  
2. Only translate the **Description** paragraph into **Bahasa Melayu**.
3. Change **"Stage"** to **"Fasa"**, but keep the value in double quotes (e.g. "Series A").
4. Change **"Has token: No"** to **Ada token: (belum)**, and **"Has token: Yes"** to **Ada token: (ada)**.
5. Change **"Raised"** to **"Dana"**, and keep it in the same position in the line.
6. Change **"Twitter:"** to **"Twitter (akaun rasmi):"**, but keep the Twitter handle format untouched.
7. Change **"Name:"** to **"Nama:"**.
8. Do NOT add any explanations, summaries, or commentary. Return only the translated result in Bahasa Melayu.

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
        "contents": [ { "parts": [ { "text": prompt } ] } ]
    }

    for attempt in range(1, max_retries + 1):
        try:
            res = requests.post(f"{gemini_url}?key={GEMINI_API_KEY}", headers=headers, json=payload)
            if res.status_code == 200:
                return res.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            elif res.status_code == 429:
                print(f"⚠️ Gemini 429 Quota hit. Retry attempt {attempt}")
                try:
                    retry_delay = json.loads(res.text)["error"]["details"][2]["retryDelay"]
                    seconds = int(retry_delay.replace("s", "").replace("\"", "").replace(":", "").replace(" ", ""))
                    time.sleep(seconds + 1)
                except:
                    time.sleep(30)  # fallback
            else:
                print("❌ Gemini API Error:", res.text)
                return None
        except Exception as e:
            print(f"❌ Gemini translation failed: {e}")
            time.sleep(5)
    print("❌ Max retries exceeded for Gemini.")
    return None



# Make sure to call post_results_to_facebook() after save_results()
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
    post_results_to_facebook(final_clean_data)
    save_results(final_clean_data)

    print("\n📦 All done.")
    print(json.dumps(final_clean_data, indent=2, ensure_ascii=False))
