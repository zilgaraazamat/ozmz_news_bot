import re
import hashlib
import random
import requests
import feedparser
from datetime import datetime, timezone, timedelta

from config import (
    BOT_TOKEN, ANTHROPIC_KEY, FOOTBALL_KEY,
    ASTANA_TZ, RSS_FEEDS, PHOTOS, BAD_PHRASES
)
from storage import is_news_sent, mark_news_sent

# ── State ─────────────────────────────────────────────────────────────────────
_used_photos = []

# ── Time ──────────────────────────────────────────────────────────────────────

def now_astana():
    return datetime.now(ASTANA_TZ)

def is_night():
    h = now_astana().hour
    return h >= 23 or h < 8

# ── Photos ────────────────────────────────────────────────────────────────────

def pick_photo():
    available = [p for p in PHOTOS if p not in _used_photos[-6:]]
    if not available:
        available = PHOTOS
    photo = random.choice(available)
    _used_photos.append(photo)
    return photo

# ── Validation ────────────────────────────────────────────────────────────────

def is_valid_post(text: str) -> bool:
    if not text or len(text) < 50:
        return False
    tl = text.lower()
    for phrase in BAD_PHRASES:
        if phrase in tl:
            print(f"  [WARN] bad phrase: '{phrase}'")
            return False
    return True

# ── News ──────────────────────────────────────────────────────────────────────

def _fetch_text(url):
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if not r.ok:
            return ""
        text = re.sub(r"<style[^>]*>.*?</style>", "", r.text, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        return re.sub(r"\s+", " ", text).strip()[:2000]
    except:
        return ""

def fetch_all_news():
    articles = []
    for name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            print(f"  [{name}] {len(feed.entries)} entries")
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                link    = entry.get("link", "").strip()
                summary = entry.get("summary", "").strip()
                full    = _fetch_text(link) if link else ""
                articles.append({"title": title, "summary": summary, "full_text": full or summary})
        except Exception as e:
            print(f"  [{name}] ERROR: {e}")
    return articles

def get_new(articles):
    return [a for a in articles
            if not is_news_sent(hashlib.md5(a["title"].encode()).hexdigest())]

def mark_sent(articles):
    hashes = [hashlib.md5(a["title"].encode()).hexdigest() for a in articles]
    mark_news_sent(hashes)

# ── Matches ───────────────────────────────────────────────────────────────────

def get_upcoming_matches():
    matches = []
    now = now_astana()
    try:
        date_from = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
        date_to   = (now + timedelta(days=1)).astimezone(timezone.utc).strftime("%Y-%m-%d")
        r = requests.get(
            "https://api.football-data.org/v4/matches",
            headers={"X-Auth-Token": FOOTBALL_KEY},
            params={"dateFrom": date_from, "dateTo": date_to},
            timeout=10,
        )
        if r.ok:
            for m in r.json().get("matches", []):
                if m.get("status") not in ("TIMED", "SCHEDULED"):
                    continue
                utc_time = m.get("utcDate", "")
                home = m.get("homeTeam", {}).get("name", "")
                away = m.get("awayTeam", {}).get("name", "")
                comp = m.get("competition", {}).get("name", "")
                if utc_time and home and away:
                    utc_dt = datetime.strptime(utc_time, "%Y-%m-%dT%H:%M:%SZ")
                    ast_dt = utc_dt.replace(tzinfo=timezone.utc).astimezone(ASTANA_TZ)
                    if ast_dt > now:
                        matches.append({
                            "home": home, "away": away,
                            "time": ast_dt.strftime("%d.%m %H:%M"),
                            "comp": comp,
                            "match_id": m.get("id"),
                        })
        else:
            print(f"  [WARN] football-data.org: {r.status_code}")
    except Exception as e:
        print(f"  [WARN] football-data.org: {e}")
    return matches[:6]

# ── Claude ────────────────────────────────────────────────────────────────────

def claude(prompt, max_tokens=350):
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-sonnet-4-6",
                "max_tokens": max_tokens,
                "messages":   [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"  [Claude] ERROR: {e}")
        return ""

# ── Telegram send ─────────────────────────────────────────────────────────────

def tg_post(chat_id, method, **kwargs):
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/{method}",
            json={"chat_id": chat_id, **kwargs},
            timeout=20,
        )
        return r.json() if r.ok else None
    except Exception as e:
        print(f"  [TG] {method} ERROR: {e}")
        return None

def send_to_group(caption, photo=None):
    if not is_valid_post(caption):
        print("  [STOP] post failed validation")
        return
    if photo is None:
        photo = pick_photo()
    result = tg_post(
        from_config("CHAT_ID"), "sendPhoto",
        photo=photo, caption=caption[:1024], parse_mode="HTML"
    )
    if result:
        print("  [OK] photo sent to group")
        return
    tg_post(from_config("CHAT_ID"), "sendMessage",
            text=caption[:4096], parse_mode="HTML")
    print("  [OK] text sent to group")

def send_msg(chat_id, text, keyboard=None):
    payload = {"text": text, "parse_mode": "HTML"}
    if keyboard:
        payload["reply_markup"] = {
            "keyboard": keyboard,
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
    tg_post(chat_id, "sendMessage", **payload)

def send_photo_msg(chat_id, caption, photo_url):
    result = tg_post(chat_id, "sendPhoto",
                     photo=photo_url, caption=caption, parse_mode="HTML")
    if not result:
        send_msg(chat_id, caption)

# lazy import helper
def from_config(key):
    import config
    return getattr(config, key)
