import os
import time
import random
import hashlib
import requests
import schedule
import feedparser
from datetime import datetime

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.environ["BOT_TOKEN"]
CHAT_ID       = os.environ["CHAT_ID"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

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

PHOTOS_WORLD = [
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&q=80",
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&q=80",
    "https://images.unsplash.com/photo-1431324155629-1a6deb1dec8d?w=800&q=80",
    "https://images.unsplash.com/photo-1553778263-73a83bab9b0c?w=800&q=80",
    "https://images.unsplash.com/photo-1560272564-c83b66b1ad12?w=800&q=80",
    "https://images.unsplash.com/photo-1606925797300-0b35e9d1794e?w=800&q=80",
    "https://images.unsplash.com/photo-1518604666860-9ed391f76460?w=800&q=80",
    "https://images.unsplash.com/photo-1587329310686-91414b8e3cb7?w=800&q=80",
    "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=800&q=80",
    "https://images.unsplash.com/photo-1522778119026-d647f0596c20?w=800&q=80",
]
PHOTOS_KZ = [
    "https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&q=80",
    "https://images.unsplash.com/photo-1543326727-cf6c39e8f84c?w=800&q=80",
    "https://images.unsplash.com/photo-1574629810360-7efbbe195018?w=800&q=80",
    "https://images.unsplash.com/photo-1579952363873-27f3bade9f55?w=800&q=80",
    "https://images.unsplash.com/photo-1553778263-73a83bab9b0c?w=800&q=80",
]
PHOTOS_DIGEST = [
    "https://images.unsplash.com/photo-1461896836934-ffe607ba8211?w=800&q=80",
    "https://images.unsplash.com/photo-1517927033932-b3d18e61fb3a?w=800&q=80",
    "https://images.unsplash.com/photo-1504016798967-7a462f730c37?w=800&q=80",
]

sent_hashes: set[str] = set()

# ─── Время суток ──────────────────────────────────────────────────────────────

def is_night() -> bool:
    """Ночь: 00:00 — 07:00"""
    return datetime.now().hour < 7

# ─── Получение новостей ───────────────────────────────────────────────────────

def fetch_feeds(urls: list, label: str) -> list:
    articles = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            print(f"[DEBUG] {label} | {url} → {len(feed.entries)} записей")
            for entry in feed.entries[:6]:
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

def get_new_articles(articles: list) -> list:
    """Возвращает только ещё не опубликованные статьи."""
    return [a for a in articles if hashlib.md5(a["title"].encode()).hexdigest() not in sent_hashes]

# ─── Claude API ───────────────────────────────────────────────────────────────

def claude(prompt: str, max_tokens: int = 900) -> str:
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

def is_breaking_news(titles: list) -> bool:
    """Спрашиваем Claude — есть ли среди новостей что-то суперкрутое."""
    prompt = f"""Ты — редактор спортивного канала. Оцени эти заголовки новостей:
{chr(10).join(f'- {t}' for t in titles)}

Есть ли среди них СУПЕРВАЖНОЕ событие? (трансфер звезды, скандал, неожиданный результат крупного турнира, рекорд, смерть известной личности)
Ответь строго одним словом: ДА или НЕТ"""
    result = claude(prompt, max_tokens=10)
    return "ДА" in result.upper()

def make_single_post(article: dict, is_kz: bool) -> str:
    kz_note = "Это казахстанская новость — добавь немного казахского колорита 🦅" if is_kz else ""
    prompt = f"""Ты — остроумный спортивный комментатор Telegram-канала. {kz_note}

Напиши пост про эту новость:
1. Сначала на русском — смешно, живо, с эмодзи и сарказмом, 3-4 предложения.
2. Потом строго напиши "――――――――――" (только тире, ничего больше)
3. Потом то же самое на казахском языке, 3-4 предложения.

Без ссылок. Без слов "Казакша" или "Русский". Заголовок включи в текст.

Новость: {article['title']}
Детали: {article['summary'][:400]}"""
    return claude(prompt)

def make_combined_post(articles: list, is_kz: bool) -> str:
    kz_note = "Это казахстанские новости — добавь казахский колорит 🦅" if is_kz else ""
    titles_block = "\n".join(f"{i+1}. {a['title']} — {a['summary'][:150]}" for i, a in enumerate(articles))
    prompt = f"""Ты — остроумный спортивный комментатор Telegram-канала. {kz_note}
Сегодня сразу несколько крутых новостей — объедини их в один пост.

Новости:
{titles_block}

Структура поста:
1. Сначала на русском — пройдись по каждой новости смешно, с эмодзи, итого 5-7 предложений.
2. Потом строго напиши "――――――――――" (только тире, ничего больше)
3. Потом то же самое на казахском языке.

Без ссылок. Без слов "Казакша" или "Русский". Сделай текст единым и живым, не просто список."""
    return claude(prompt, max_tokens=1100)

def get_match_results() -> str:
    try:
        feed = feedparser.parse("https://lenta.ru/rss/news/sport/football")
        titles = [e.get("title", "") for e in feed.entries[:10] if e.get("title")]

        prompt = f"""Ты — остроумный ведущий итогового спортивного шоу.
Заголовки новостей за день: {'; '.join(titles)}

Напиши вечерний дайджест:
1. На русском — смешной итог дня, 4-5 предложений с эмодзи.
2. Потом строго напиши "――――――――――"
3. То же на казахском языке.

Без ссылок. Без слов "Казакша" или "Русский"."""
        return claude(prompt, max_tokens=1000)
    except Exception as e:
        print(f"[WARN] Дайджест: {e}")
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
        }, timeout=20)
        if r.ok:
            return True
        print(f"[WARN] sendPhoto failed ({r.status_code}), отправляем текстом...")
        return send_text(caption)
    except Exception as e:
        print(f"[ERROR] sendPhoto: {e}")
        return send_text(caption)

def send_text(text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(url, json={
            "chat_id":    CHAT_ID,
            "text":       text[:4096],
            "parse_mode": "HTML",
        }, timeout=10)
        if not r.ok:
            print(f"[ERROR] sendMessage: {r.status_code} — {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[ERROR] sendMessage: {e}")
        return False

# ─── Основные задачи ──────────────────────────────────────────────────────────

def post_news():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Проверяем новости...")

    world = fetch_feeds(RSS_WORLD, "Мировой футбол")
    kz    = fetch_feeds(RSS_KZ, "Казахстан")

    new_world = get_new_articles(world)
    new_kz    = get_new_articles(kz)
    all_new   = new_world + new_kz

    if not all_new:
        print("Нет новых новостей")
        return

    # Ночью — постим только если есть суперважное событие
    if is_night():
        titles = [a["title"] for a in all_new[:6]]
        if not is_breaking_news(titles):
            print("[НОЧЬ] Обычные новости — пропускаем до утра")
            return
        print("[НОЧЬ] Найдено важное событие — публикуем!")

    # Если новых новостей 3+ — объединяем в один пост
    is_kz = len(new_kz) > len(new_world)

    if len(all_new) >= 3:
        top = all_new[:4]
        text = make_combined_post(top, is_kz)
        flag = "🔥"
        tag  = "#КазСпорт #Футбол #ДайджестНовостей"
        for a in top:
            sent_hashes.add(hashlib.md5(a["title"].encode()).hexdigest())
    else:
        art = all_new[0]
        is_kz = art in new_kz
        text = make_single_post(art, is_kz)
        flag = "🇰🇿" if is_kz else "⚽"
        tag  = "#КазСпорт #ҚазақстанСпорт" if is_kz else "#Футбол #Football"
        sent_hashes.add(hashlib.md5(art["title"].encode()).hexdigest())

    if not text:
        print("[WARN] Claude не вернул текст")
        return

    photo = random.choice(PHOTOS_KZ if is_kz else PHOTOS_WORLD)
    caption = f"{flag} {text}\n\n{tag}"

    if send_photo(caption, photo):
        print(f"[OK] Опубликовано")

def post_daily_digest():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Вечерний дайджест...")
    digest = get_match_results()
    if not digest:
        print("Нет данных для дайджеста")
        return
    caption = f"🏆 <b>Итоги дня</b>\n\n{digest}\n\n#ИтогиДня #Футбол #Дайджест"
    photo = random.choice(PHOTOS_DIGEST)
    send_photo(caption, photo)
    print(f"[OK] Дайджест опубликован")

# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Футбольный бот v5 запущен!")
    post_news()

    schedule.every(1).hours.do(post_news)
    schedule.every().day.at("21:00").do(post_daily_digest)

    while True:
        schedule.run_pending()
        time.sleep(30)
