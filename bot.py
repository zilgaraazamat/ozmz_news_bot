import os
import time
import hashlib
import requests
import schedule
import feedparser
from datetime import datetime

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN = os.environ["BOT_TOKEN"]
CHAT_ID   = os.environ["CHAT_ID"]

# RSS-ленты футбольных новостей на русском
RSS_FEEDS = [
    "https://www.sports.ru/rss/football.xml",
    "https://rsport.ria.ru/trend/football_news/",
    "https://lenta.ru/rss/news/sport/football",
    "https://matchtv.ru/rss",
]

# Храним уже отправленные новости (по хэшу заголовка), чтобы не дублировать
sent_hashes: set[str] = set()

# ─── Функции ──────────────────────────────────────────────────────────────────

def get_news() -> list[dict]:
    """Собирает новости со всех RSS-лент."""
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            count = len(feed.entries)
            print(f"[DEBUG] {url} → найдено записей: {count}")
            for entry in feed.entries[:5]:  # не более 5 с каждого источника
                articles.append({
                    "title":   entry.get("title", "").strip(),
                    "summary": entry.get("summary", "").strip(),
                    "link":    entry.get("link", "").strip(),
                    "source":  feed.feed.get("title", "Новости"),
                })
        except Exception as e:
            print(f"[WARN] Ошибка при получении {url}: {e}")
    return articles


def send_message(text: str) -> bool:
    """Отправляет сообщение в Telegram-группу."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    CHAT_ID,
        "text":       text,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        r = requests.post(url, json=payload, timeout=10)
        if not r.ok:
            print(f"[ERROR] Telegram API: {r.status_code} — {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[ERROR] Не удалось отправить сообщение: {e}")
        return False


def post_news():
    """Основная задача — получить новые новости и опубликовать их."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Проверяем новости...")
    articles = get_news()

    posted = 0
    for art in articles:
        h = hashlib.md5(art["title"].encode()).hexdigest()
        if h in sent_hashes:
            continue  # уже постили

        # Формируем сообщение
        summary = art["summary"][:300] + "..." if len(art["summary"]) > 300 else art["summary"]
        msg = (
            f"⚽ <b>{art['title']}</b>\n\n"
            f"{summary}\n\n"
            f"📰 <i>{art['source']}</i>\n"
            f"🔗 <a href='{art['link']}'>Читать полностью</a>"
        )

        if send_message(msg):
            sent_hashes.add(h)
            posted += 1
            time.sleep(2)  # небольшая пауза между сообщениями

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Опубликовано: {posted} новостей")


# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Футбольный бот запущен!")
    post_news()  # сразу при старте

    schedule.every(1).hours.do(post_news)

    while True:
        schedule.run_pending()
        time.sleep(30)
