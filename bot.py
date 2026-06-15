import os
import time
import hashlib
import requests
import schedule
import feedparser
from datetime import datetime

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.environ["BOT_TOKEN"]
CHAT_ID       = os.environ["CHAT_ID"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

# Мировые футбольные новости (русский)
RSS_FEEDS = [
    "https://lenta.ru/rss/news/sport/football",
]

# Казахстанский футбол
RSS_FEEDS_KZ = [
    "https://www.sports.ru/rss/football/kazakhstan.xml",
    "https://kazfootball.kz/rss",
    "https://prosports.kz/rss.xml",
]

sent_hashes: set[str] = set()

# ─── Получение новостей ───────────────────────────────────────────────────────

def fetch_feed(urls: list[str], label: str) -> list[dict]:
    articles = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            print(f"[DEBUG] {label} | {url} → {len(feed.entries)} записей")
            for entry in feed.entries[:4]:
                articles.append({
                    "title":   entry.get("title", "").strip(),
                    "summary": entry.get("summary", "").strip(),
                    "link":    entry.get("link", "").strip(),
                    "source":  feed.feed.get("title", label),
                })
        except Exception as e:
            print(f"[WARN] {url}: {e}")
    return articles


# ─── Claude: делает новость смешной ──────────────────────────────────────────

def make_funny(title: str, summary: str, is_kz: bool) -> str:
    kz_note = " Это новость о казахстанском футболе — добавь немного казахского колорита и гордости." if is_kz else ""
    prompt = f"""Ты — остроумный спортивный комментатор Telegram-канала о футболе. 
Перепиши эту новость смешно и живо — как будто рассказываешь другу за чаем. 
Используй эмодзи, сарказм, преувеличения. Не больше 3-4 предложений.{kz_note}
Пиши только на русском языке. Не добавляй заголовок отдельно — включи его в текст.

Заголовок: {title}
Суть: {summary[:400]}"""

    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_KEY,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": "claude-sonnet-4-6",
                "max_tokens": 300,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=20,
        )
        data = r.json()
        return data["content"][0]["text"].strip()
    except Exception as e:
        print(f"[WARN] Claude API ошибка: {e}")
        # Если Claude недоступен — возвращаем оригинал
        return f"<b>{title}</b>\n\n{summary[:300]}"


# ─── Отправка в Telegram ──────────────────────────────────────────────────────

def send_message(text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id":    CHAT_ID,
            "text":       text,
            "parse_mode": "HTML",
        }, timeout=10)
        if not r.ok:
            print(f"[ERROR] Telegram: {r.status_code} — {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


# ─── Основная задача ──────────────────────────────────────────────────────────

def post_news():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Проверяем новости...")

    world_news = fetch_feed(RSS_FEEDS, "Мировой футбол")
    kz_news    = fetch_feed(RSS_FEEDS_KZ, "Казахстанский футбол")

    # Берём 1 новость за раз: чередуем казахстанские и мировые
    to_post = []
    if kz_news:
        to_post.append((kz_news[0], True))
    elif world_news:
        to_post.append((world_news[0], False))

    posted = 0
    for art, is_kz in to_post:
        h = hashlib.md5(art["title"].encode()).hexdigest()
        if h in sent_hashes or not art["title"]:
            continue

        funny_text = make_funny(art["title"], art["summary"], is_kz)

        flag = "🇰🇿" if is_kz else "⚽"
        tag  = "#КазФутбол" if is_kz else "#Футбол"

        msg = (
            f"{flag} {funny_text}\n\n"
            f"📰 <i>{art['source']}</i>  {tag}\n"
            f"🔗 <a href='{art['link']}'>Читать полностью</a>"
        )

        if send_message(msg):
            sent_hashes.add(h)
            posted += 1
            time.sleep(3)

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Опубликовано: {posted} новостей")


# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Футбольный бот запущен!")
    post_news()

    schedule.every(1).hours.do(post_news)

    while True:
        schedule.run_pending()
        time.sleep(30)
