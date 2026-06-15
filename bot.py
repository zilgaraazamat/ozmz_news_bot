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

# Новостные RSS источники
RSS_WORLD = [
    "https://lenta.ru/rss/news/sport/football",
    "https://rsport.ria.ru/trend/football_news/",
    "https://www.championat.com/football/rss.xml",
]

RSS_KZ = [
    "https://sports.kz/rss/",
    "https://prosports.kz/rss.xml",
    "https://www.sports.ru/rss/football/kazakhstan.xml",
]

sent_hashes: set[str] = set()

# ─── Получение новостей ───────────────────────────────────────────────────────

def fetch_feeds(urls: list[str], label: str) -> list[dict]:
    articles = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            print(f"[DEBUG] {label} | {url} → {len(feed.entries)} записей")
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                articles.append({
                    "title":   title,
                    "summary": entry.get("summary", "").strip(),
                    "source":  feed.feed.get("title", label),
                })
        except Exception as e:
            print(f"[WARN] {url}: {e}")
    return articles

# ─── Claude API ───────────────────────────────────────────────────────────────

def claude(prompt: str, max_tokens: int = 600) -> str:
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
                "max_tokens": max_tokens,
                "messages": [{"role": "user", "content": prompt}],
            },
            timeout=30,
        )
        return r.json()["content"][0]["text"].strip()
    except Exception as e:
        print(f"[WARN] Claude API: {e}")
        return ""


def make_funny_post(title: str, summary: str, is_kz: bool) -> str:
    lang_note = (
        "Напиши пост НА ДВУХ ЯЗЫКАХ: сначала на русском, потом на казахском. "
        "Разделяй языки строкой '🇰🇿 Қазақша:'. "
        "Это казахстанская спортивная новость — добавь казахский колорит и гордость."
        if is_kz else
        "Напиши пост сначала на русском, потом на казахском. "
        "Разделяй строкой '🇰🇿 Қазақша:'."
    )
    prompt = f"""Ты — остроумный спортивный комментатор Telegram-канала. 
{lang_note}
Стиль: смешно, живо, с эмодзи, сарказмом и преувеличениями. Как будто рассказываешь другу.
Без ссылок. Без заголовка отдельно — включи в текст. 3-4 предложения на каждом языке.

Новость: {title}
Детали: {summary[:400]}"""
    result = claude(prompt)
    return result if result else f"⚽ {title}\n\n{summary[:300]}"


def get_photo_url(query: str) -> str:
    """Получаем фото через Unsplash source (без API ключа)"""
    clean = query.replace(" ", "+")
    # Unsplash source даёт рандомное фото по теме
    return f"https://source.unsplash.com/800x500/?{clean},football"


def get_match_results() -> str:
    """Получаем результаты матчей через football-data.org (бесплатный план)"""
    try:
        # Бесплатный план — топ-5 лиг
        headers = {"X-Auth-Token": ""}  # без токена — публичные данные
        # Используем API-Football через rapidapi если есть, иначе парсим RSS
        feed = feedparser.parse("https://www.championat.com/football/rss/results.xml")
        if not feed.entries:
            feed = feedparser.parse("https://lenta.ru/rss/news/sport/football")
        
        results = []
        for entry in feed.entries[:8]:
            title = entry.get("title", "")
            if any(c.isdigit() for c in title):  # берём только те где есть счёт
                results.append(title)
        
        if not results:
            return ""
        
        prompt = f"""Ты — остроумный спортивный ведущий. 
Вот результаты матчей за сегодня: {'; '.join(results)}

Напиши вечерний дайджест результатов — смешно и живо, с эмодзи.
Сначала на русском, потом на казахском (раздели строкой '🇰🇿 Қазақша:').
Без ссылок. 5-7 предложений на каждом языке."""
        
        return claude(prompt, max_tokens=800)
    except Exception as e:
        print(f"[WARN] Результаты матчей: {e}")
        return ""

# ─── Отправка ─────────────────────────────────────────────────────────────────

def send_photo(caption: str, photo_url: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto"
    try:
        r = requests.post(url, json={
            "chat_id":    CHAT_ID,
            "photo":      photo_url,
            "caption":    caption[:1024],
            "parse_mode": "HTML",
        }, timeout=15)
        if not r.ok:
            print(f"[ERROR] Telegram sendPhoto: {r.status_code} — {r.text}")
            return send_text(caption)  # fallback — отправим без фото
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False


def send_text(text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id":    CHAT_ID,
            "text":       text[:4096],
            "parse_mode": "HTML",
        }, timeout=10)
        if not r.ok:
            print(f"[ERROR] Telegram sendMessage: {r.status_code} — {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

# ─── Основные задачи ──────────────────────────────────────────────────────────

def post_news():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Проверяем новости...")

    world = fetch_feeds(RSS_WORLD, "Мировой футбол")
    kz    = fetch_feeds(RSS_KZ, "Казахстанский спорт")

    # Чередуем: чётный час — мировая новость, нечётный — казахстанская
    hour = datetime.now().hour
    if hour % 2 == 0 and world:
        art, is_kz = world[0], False
    elif kz:
        art, is_kz = kz[0], True
    elif world:
        art, is_kz = world[0], False
    else:
        print("Нет новостей")
        return

    h = hashlib.md5(art["title"].encode()).hexdigest()
    if h in sent_hashes:
        print("Новость уже публиковалась, пропускаем")
        return

    text = make_funny_post(art["title"], art["summary"], is_kz)
    if not text:
        return

    # Фото по теме
    query = "Kazakhstan football" if is_kz else "football stadium match"
    photo = get_photo_url(query)

    flag = "🇰🇿" if is_kz else "⚽"
    tag  = "#КазСпорт #ҚазақстанСпорт" if is_kz else "#Футбол #Football"
    caption = f"{flag} {text}\n\n{tag}"

    if send_photo(caption, photo):
        sent_hashes.add(h)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Опубликовано: {art['title'][:50]}")


def post_daily_digest():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Публикуем вечерний дайджест...")
    digest = get_match_results()
    if not digest:
        print("Результаты матчей не найдены")
        return

    caption = f"🏆 <b>Итоги дня</b>\n\n{digest}\n\n#ИтогиДня #Футбол #Дайджест"
    photo = get_photo_url("football scoreboard trophy results")
    send_photo(caption, photo)
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Дайджест опубликован")


# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Футбольный бот v3 запущен!")
    post_news()  # сразу при старте

    schedule.every(1).hours.do(post_news)
    schedule.every().day.at("21:00").do(post_daily_digest)  # вечерний дайджест в 21:00

    while True:
        schedule.run_pending()
        time.sleep(30)
