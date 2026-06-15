import os
import time
import random
import hashlib
import requests
import schedule
import feedparser
from datetime import datetime, timezone, timedelta

ASTANA_TZ = timezone(timedelta(hours=5))

def now_astana():
    return datetime.now(ASTANA_TZ)

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

# Фото с telegra.ph — прямые ссылки, Telegram принимает гарантированно
PHOTOS_WORLD = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg/1280px-FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/Chelsea_vs_PSG_-_Stamford_Bridge_%28cropped%29.jpg/1280px-Chelsea_vs_PSG_-_Stamford_Bridge_%28cropped%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Wembley_Stadium_interior.jpg/1280px-Wembley_Stadium_interior.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Camp_Nou_aerial_%28cropped%29.jpg/1280px-Camp_Nou_aerial_%28cropped%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Allianz_Arena_Abend.jpg/1280px-Allianz_Arena_Abend.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Cristiano_Ronaldo_in_2018.jpg/800px-Cristiano_Ronaldo_in_2018.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Messi_vs_Nigeria_2018.jpg/1024px-Messi_vs_Nigeria_2018.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg/1280px-Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg",
]
PHOTOS_KZ = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg/1280px-FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Wembley_Stadium_interior.jpg/1280px-Wembley_Stadium_interior.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Allianz_Arena_Abend.jpg/1280px-Allianz_Arena_Abend.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Camp_Nou_aerial_%28cropped%29.jpg/1280px-Camp_Nou_aerial_%28cropped%29.jpg",
]
PHOTOS_DIGEST = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg/1280px-Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Wembley_Stadium_interior.jpg/1280px-Wembley_Stadium_interior.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Camp_Nou_aerial_%28cropped%29.jpg/1280px-Camp_Nou_aerial_%28cropped%29.jpg",
]

sent_hashes: set[str] = set()

# ─── Время суток ──────────────────────────────────────────────────────────────

def is_night() -> bool:
    return now_astana().hour < 7

# ─── Получение новостей ───────────────────────────────────────────────────────

import re

def fetch_article_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if not r.ok:
            return ""
        text = re.sub(r"<style[^>]*>.*?</style>", "", r.text, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:3000]
    except:
        return ""

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
                summary   = entry.get("summary", "").strip()
                link      = entry.get("link", "").strip()
                full_text = fetch_article_text(link) if link else ""
                articles.append({
                    "title":     title,
                    "summary":   summary,
                    "full_text": full_text or summary,
                })
        except Exception as e:
            print(f"[WARN] {url}: {e}")
    return articles

def get_new_articles(articles: list) -> list:
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

SEPARATOR = "――――――――――"

def make_single_post(article: dict, is_kz: bool) -> str:
    kz_note = "Это казахстанская новость — добавь немного казахского колорита 🦅" if is_kz else ""
    facts = article.get("full_text") or article.get("summary", "")
    prompt = f"""Ты — остроумный спортивный комментатор Telegram-канала. {kz_note}

Напиши пост СТРОГО в таком формате (без отклонений):

[текст на русском языке — смешно, с эмодзи, 3-4 предложения]
――――――――――
[тот же текст на казахском языке — 3-4 предложения]

КРИТИЧЕСКИ ВАЖНО:
- Используй ТОЧНЫЕ факты из текста новости: счёт матча, имена игроков, минуты голов, названия клубов
- Юмор не должен искажать факты — шути над ситуацией, но цифры и имена точные
- Никаких слов "Русский", "Казакша", "Қазақша" или любых других меток языка
- Только сам текст, потом ――――――――――, потом казахский текст
- Без ссылок
- Заголовок включи в текст естественно

Новость: {article["title"]}
Полный текст: {facts[:1500]}"""
    return claude(prompt)

def make_combined_post(articles: list, is_kz: bool) -> str:
    kz_note = "Это казахстанские новости — добавь казахский колорит 🦅" if is_kz else ""
    news_block = "\n".join(
        f"{i+1}. {a['title']}\n   {(a.get('full_text') or a.get('summary', ''))[:500]}"
        for i, a in enumerate(articles)
    )
    prompt = f"""Ты — остроумный спортивный комментатор Telegram-канала. {kz_note}
Сегодня сразу несколько крутых новостей — объедини их в один живой пост.

Новости с деталями:
{news_block}

Напиши пост СТРОГО в таком формате:

[единый текст на русском — смешно, про все новости, 5-7 предложений с эмодзи]
――――――――――
[тот же текст на казахском языке]

КРИТИЧЕСКИ ВАЖНО:
- Используй ТОЧНЫЕ факты из текста: счёт матча, имена игроков, минуты голов, названия клубов
- Юмор над ситуацией, но цифры и имена строго точные
- Никаких слов "Русский", "Казакша", "Қазақша" или меток языка
- Только текст, потом ――――――――――, потом казахский
- Без ссылок, без нумерации"""
    return claude(prompt, max_tokens=1100)

def is_breaking_news(titles: list) -> bool:
    prompt = f"""Оцени заголовки новостей:
{chr(10).join(f'- {t}' for t in titles)}

Есть ли среди них СУПЕРВАЖНОЕ событие? (крупный трансфер, скандал, рекорд, неожиданный результат финала)
Ответь одним словом: ДА или НЕТ"""
    result = claude(prompt, max_tokens=5)
    return "ДА" in result.upper()

def get_match_results() -> str:
    try:
        feed = feedparser.parse("https://lenta.ru/rss/news/sport/football")
        titles = [e.get("title", "") for e in feed.entries[:10] if e.get("title")]
        prompt = f"""Ты — остроумный ведущий итогового спортивного шоу.
Заголовки новостей за день: {'; '.join(titles)}

Напиши вечерний дайджест СТРОГО в таком формате:

[смешной итог дня на русском — 4-5 предложений с эмодзи]
――――――――――
[тот же текст на казахском языке]

ВАЖНО: никаких слов "Русский", "Казакша" или меток языка. Без ссылок."""
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
            print(f"[OK] Фото отправлено")
            return True
        print(f"[WARN] sendPhoto {r.status_code}: {r.text[:200]}")
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
    print(f"[{now_astana().strftime('%H:%M:%S')}] Проверяем новости...")

    world  = fetch_feeds(RSS_WORLD, "Мировой футбол")
    kz     = fetch_feeds(RSS_KZ, "Казахстан")
    new_w  = get_new_articles(world)
    new_kz = get_new_articles(kz)
    all_new = new_w + new_kz

    if not all_new:
        print("Нет новых новостей")
        return

    if is_night():
        if not is_breaking_news([a["title"] for a in all_new[:6]]):
            print("[НОЧЬ] Обычные новости — пропускаем")
            return
        print("[НОЧЬ] Важное событие — публикуем!")

    is_kz = len(new_kz) > len(new_w)

    if len(all_new) >= 3:
        top = all_new[:4]
        text = make_combined_post(top, is_kz)
        flag = "🔥"
        tag  = "#Футбол #КазСпорт #ДайджестНовостей"
        for a in top:
            sent_hashes.add(hashlib.md5(a["title"].encode()).hexdigest())
    else:
        art  = all_new[0]
        is_kz = art in new_kz
        text = make_single_post(art, is_kz)
        flag = "🇰🇿" if is_kz else "⚽"
        tag  = "#КазСпорт #ҚазақстанСпорт" if is_kz else "#Футбол #Football"
        sent_hashes.add(hashlib.md5(art["title"].encode()).hexdigest())

    if not text:
        print("[WARN] Claude не вернул текст")
        return

    photo   = random.choice(PHOTOS_KZ if is_kz else PHOTOS_WORLD)
    caption = f"{flag} {text}\n\n{tag}"
    send_photo(caption, photo)

def post_daily_digest():
    print(f"[{now_astana().strftime('%H:%M:%S')}] Вечерний дайджест...")
    digest = get_match_results()
    if not digest:
        print("Нет данных")
        return
    caption = f"🏆 <b>Итоги дня</b>\n\n{digest}\n\n#ИтогиДня #Футбол #Дайджест"
    photo   = random.choice(PHOTOS_DIGEST)
    send_photo(caption, photo)
    print(f"[OK] Дайджест опубликован")

# ─── Утренний анонс матчей ────────────────────────────────────────────────────

def post_morning_schedule():
    print(f"[{now_astana().strftime('%H:%M:%S')}] Утренний анонс матчей...")
    try:
        feed = feedparser.parse("https://www.championat.com/football/rss.xml")
        titles = [e.get("title", "") for e in feed.entries[:15] if e.get("title")]
        if not titles:
            feed = feedparser.parse("https://lenta.ru/rss/news/sport/football")
            titles = [e.get("title", "") for e in feed.entries[:15] if e.get("title")]
    except Exception as e:
        print(f"[WARN] RSS для анонса: {e}")
        titles = []

    prompt = f"""Ты — весёлый спортивный ведущий утреннего шоу.
Сегодня {now_astana().strftime('%d.%m.%Y')}.

Вот последние футбольные заголовки: {"; ".join(titles[:10])}

Составь утренний анонс матчей дня:

[Приветствие + какие топ-матчи сегодня — 2-3 предложения с эмодзи]

Для каждого топового матча (3-4 штуки):
🆚 Команда А vs Команда Б
🕐 Время (если известно)
🔮 Прогноз: [смешной прогноз 1-2 предложения]

――――――――――

[То же самое на казахском языке]

ВАЖНО: никаких слов "Русский" или "Казакша". Без ссылок."""

    text = claude(prompt, max_tokens=1000)
    if not text:
        print("[WARN] Claude не вернул анонс")
        return

    photo   = random.choice(PHOTOS_WORLD)
    caption = f"☀️ <b>Матчи дня</b>\n\n{text}\n\n#АнонсМатчей #Футбол #Расписание"
    send_photo(caption, photo)
    print(f"[OK] Утренний анонс опубликован")

# ─── Голосования после матчей ─────────────────────────────────────────────────

last_poll_hash = ""

def send_poll(question: str, options: list) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll"
    try:
        r = requests.post(url, json={
            "chat_id":      CHAT_ID,
            "question":     question[:300],
            "options":      [o[:100] for o in options[:10]],
            "is_anonymous": False,
        }, timeout=10)
        if not r.ok:
            print(f"[ERROR] sendPoll: {r.status_code} — {r.text}")
            return False
        return True
    except Exception as e:
        print(f"[ERROR] sendPoll: {e}")
        return False

def post_match_poll():
    global last_poll_hash
    print(f"[{now_astana().strftime('%H:%M:%S')}] Проверяем матчи для голосования...")
    try:
        import json, re
        feed = feedparser.parse("https://lenta.ru/rss/news/sport/football")
        match_articles = [
            e for e in feed.entries[:20]
            if e.get("title") and any(c.isdigit() for c in e.get("title", ""))
        ]
        if not match_articles:
            print("Матчей с результатами не найдено")
            return

        article = match_articles[0]
        title   = article.get("title", "")
        h       = hashlib.md5(title.encode()).hexdigest()

        if h == last_poll_hash:
            print("Голосование по этому матчу уже было")
            return

        summary = article.get("summary", "")
        prompt = f"""Составь опрос для Telegram по итогам футбольного матча.

Новость: {title}
Детали: {summary[:400]}

Верни ТОЛЬКО JSON без лишнего текста:
{{"question": "вопрос (до 250 символов)", "options": ["вариант 1", "вариант 2", "вариант 3", "вариант 4"]}}

Варианты: имена игроков, названия команд, или смешные варианты типо "никто, все плохи 😂"."""

        raw = claude(prompt, max_tokens=300)
        json_match = re.search(r"\{{.*\}}", raw, re.DOTALL)
        if not json_match:
            print("[WARN] Claude не вернул JSON для опроса")
            return

        data     = json.loads(json_match.group())
        question = data.get("question", "")
        options  = data.get("options", [])

        if not question or len(options) < 2:
            print("[WARN] Неверный формат опроса")
            return

        if send_poll(question, options):
            last_poll_hash = h
            print(f"[OK] Голосование: {question[:60]}")

    except Exception as e:
        print(f"[WARN] post_match_poll: {e}")

# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print("🤖 Футбольный бот v7 запущен!")
    post_news()

    schedule.every(1).hours.do(post_news)
    schedule.every().day.at("09:00").do(post_morning_schedule)
    schedule.every().day.at("21:00").do(post_daily_digest)
    schedule.every(3).hours.do(post_match_poll)

    while True:
        schedule.run_pending()
        time.sleep(30)
