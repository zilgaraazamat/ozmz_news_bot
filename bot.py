import os
import re
import json
import time
import random
import hashlib
import requests
import schedule
import feedparser
from datetime import datetime, timezone, timedelta

# ─── Настройки ────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.environ["BOT_TOKEN"]
CHAT_ID       = os.environ["CHAT_ID"]
ANTHROPIC_KEY = os.environ["ANTHROPIC_API_KEY"]

ASTANA_TZ = timezone(timedelta(hours=5))
def now_astana():
    return datetime.now(ASTANA_TZ)

def is_night():
    return now_astana().hour < 7

# ─── RSS источники (разные платформы) ────────────────────────────────────────
RSS_FEEDS = [
    "https://lenta.ru/rss/news/sport/football",          # Lenta.ru
    "https://www.championat.com/football/rss.xml",       # Чемпионат
    "https://rsport.ria.ru/trend/football_news/",        # РИА Спорт
    "https://sports.kz/rss/",                            # Sports.kz (Казахстан)
    "https://www.soccer.ru/rss/news.xml",                # Soccer.ru
]

# ─── Фото: загружаем через Telegraph proxy (Telegram точно примет) ────────────
# Все ссылки проверены — это прямые jpg без редиректов
PHOTOS = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Wembley_Stadium_interior.jpg/1280px-Wembley_Stadium_interior.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Camp_Nou_aerial_%28cropped%29.jpg/1280px-Camp_Nou_aerial_%28cropped%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Allianz_Arena_Abend.jpg/1280px-Allianz_Arena_Abend.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg/1280px-Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Messi_vs_Nigeria_2018.jpg/1024px-Messi_vs_Nigeria_2018.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Cristiano_Ronaldo_in_2018.jpg/800px-Cristiano_Ronaldo_in_2018.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg/1280px-FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/Chelsea_vs_PSG_-_Stamford_Bridge_%28cropped%29.jpg/1280px-Chelsea_vs_PSG_-_Stamford_Bridge_%28cropped%29.jpg",
]

sent_hashes: set[str] = set()
last_poll_hash: str = ""

# ─── Получение новостей ───────────────────────────────────────────────────────

def fetch_article_text(url: str) -> str:
    try:
        r = requests.get(url, timeout=8, headers={"User-Agent": "Mozilla/5.0"})
        if not r.ok:
            return ""
        text = re.sub(r"<style[^>]*>.*?</style>", "", r.text, flags=re.DOTALL)
        text = re.sub(r"<script[^>]*>.*?</script>", "", text, flags=re.DOTALL)
        text = re.sub(r"<[^>]+>", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text[:2000]
    except:
        return ""

def fetch_all_news() -> list:
    articles = []
    for url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            source = feed.feed.get("title", url)
            print(f"[DEBUG] {source} → {len(feed.entries)} записей")
            for entry in feed.entries[:5]:
                title = entry.get("title", "").strip()
                if not title:
                    continue
                link      = entry.get("link", "").strip()
                summary   = entry.get("summary", "").strip()
                full_text = fetch_article_text(link) if link else ""
                articles.append({
                    "title":     title,
                    "summary":   summary,
                    "full_text": full_text or summary,
                    "source":    source,
                })
        except Exception as e:
            print(f"[WARN] {url}: {e}")
    return articles

def get_new(articles: list) -> list:
    return [a for a in articles if hashlib.md5(a["title"].encode()).hexdigest() not in sent_hashes]

# ─── Claude API ───────────────────────────────────────────────────────────────

def claude(prompt: str, max_tokens: int = 400) -> str:
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
        print(f"[WARN] Claude: {e}")
        return ""

# ─── Составление постов ───────────────────────────────────────────────────────

def make_post(article: dict) -> str:
    facts = (article.get("full_text") or article.get("summary", ""))[:1200]
    prompt = f"""Ты — остроумный спортивный Telegram-канал.

Напиши короткий структурный пост про эту новость. Формат строго такой:

[эмодзи] [1 предложение — суть новости с точными фактами: счёт, имена, клубы]

[2-3 предложения — смешной комментарий с эмодзи]



ПРАВИЛА:
- Если есть счёт — обязательно укажи точно (например 3:1)
- Если есть имена игроков — используй их
- Пост короткий, не больше 5 предложений всего
- Без ссылок, без казахского языка, только русский

Новость: {article["title"]}

Текст: {facts}"""
    return claude(prompt, max_tokens=300)

def make_combined_post(articles: list) -> str:
    block = "\n".join(
        f"{i+1}. {a['title']} | {(a.get('full_text') or a.get('summary',''))[:300]}"
        for i, a in enumerate(articles)
    )
    prompt = f"""Ты — остроумный спортивный Telegram-канал.

Несколько горячих новостей — напиши один компактный пост. Формат:

🔥 ГОРЯЧЕЕ

• [эмодзи] [новость 1 — 1-2 предложения, точные факты + смешной комментарий]
• [эмодзи] [новость 2 — 1-2 предложения]
• [эмодзи] [новость 3 — 1-2 предложения]

ПРАВИЛА:
- Счёт, имена, клубы — точно из текста
- Коротко и смешно
- Только русский язык, без ссылок

Новости:
{block}"""
    return claude(prompt, max_tokens=400)

# ─── Отправка ─────────────────────────────────────────────────────────────────

def try_send_photo(caption: str) -> bool:
    """Пробуем все фото по очереди пока одно не пройдёт."""
    photos = PHOTOS.copy()
    random.shuffle(photos)
    for photo_url in photos:
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
                json={
                    "chat_id":    CHAT_ID,
                    "photo":      photo_url,
                    "caption":    caption[:1024],
                    "parse_mode": "HTML",
                },
                timeout=20,
            )
            if r.ok:
                print(f"[OK] Фото отправлено: {photo_url[:60]}")
                return True
            print(f"[WARN] Фото не прошло ({r.status_code}): {photo_url[:60]}")
        except Exception as e:
            print(f"[WARN] {e}")
    # Если ни одно фото не прошло — шлём текстом
    print("[INFO] Отправляем без фото")
    return send_text(caption)

def send_text(text: str) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": text[:4096], "parse_mode": "HTML"},
            timeout=10,
        )
        return r.ok
    except Exception as e:
        print(f"[ERROR] sendMessage: {e}")
        return False

def send_poll(question: str, options: list) -> bool:
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPoll",
            json={
                "chat_id":      CHAT_ID,
                "question":     question[:300],
                "options":      [o[:100] for o in options[:10]],
                "is_anonymous": False,
            },
            timeout=10,
        )
        return r.ok
    except Exception as e:
        print(f"[ERROR] sendPoll: {e}")
        return False

# ─── Основные задачи ──────────────────────────────────────────────────────────

def post_news():
    t = now_astana().strftime("%H:%M:%S")
    print(f"[{t}] Проверяем новости...")

    if is_night():
        print("[НОЧЬ] Тихий режим, пропускаем")
        return

    all_news = fetch_all_news()
    new      = get_new(all_news)

    if not new:
        print("Нет новых новостей")
        return

    if len(new) >= 3:
        top  = new[:3]
        text = make_combined_post(top)
        for a in top:
            sent_hashes.add(hashlib.md5(a["title"].encode()).hexdigest())
    else:
        art  = new[0]
        text = make_post(art)
        sent_hashes.add(hashlib.md5(art["title"].encode()).hexdigest())

    if not text:
        print("[WARN] Нет текста от Claude")
        return

    try_send_photo(f"{text}\n\n#Футбол #Football")
    print(f"[OK] Пост опубликован")

def post_morning_schedule():
    if is_night():
        return
    print(f"[{now_astana().strftime('%H:%M:%S')}] Утренний анонс...")

    try:
        feed   = feedparser.parse("https://lenta.ru/rss/news/sport/football")
        titles = [e.get("title", "") for e in feed.entries[:12] if e.get("title")]
    except:
        titles = []

    prompt = f"""Ты — спортивный Telegram-канал. Сегодня {now_astana().strftime('%d.%m.%Y')}.

Заголовки новостей: {"; ".join(titles[:8])}

Напиши утренний анонс матчей дня. Формат:

☀️ МАТЧИ ДНЯ

🆚 Команда А — Команда Б | 🕐 время
🔮 [смешной прогноз — 1 предложение]

(3-4 матча)

Коротко, по делу, с юмором. Только русский язык. Без ссылок."""

    text = claude(prompt, max_tokens=400)
    if text:
        try_send_photo(f"{text}\n\n#АнонсМатчей #Футбол")

def post_daily_digest():
    print(f"[{now_astana().strftime('%H:%M:%S')}] Вечерний дайджест...")
    try:
        feed   = feedparser.parse("https://lenta.ru/rss/news/sport/football")
        titles = [e.get("title", "") for e in feed.entries[:10] if e.get("title")]
    except:
        titles = []

    prompt = f"""Ты — спортивный Telegram-канал.

Заголовки дня: {"; ".join(titles)}

Напиши вечерний дайджест. Формат:

🏆 ИТОГИ ДНЯ

• [результат матча со счётом — смешной комментарий]
• [ещё результат]
• [ещё]

Коротко, точные счета если есть, с юмором. Только русский язык. Без ссылок."""

    text = claude(prompt, max_tokens=400)
    if text:
        try_send_photo(f"{text}\n\n#ИтогиДня #Футбол")

def post_match_poll():
    global last_poll_hash
    if is_night():
        return
    print(f"[{now_astana().strftime('%H:%M:%S')}] Голосование...")
    try:
        feed = feedparser.parse("https://lenta.ru/rss/news/sport/football")
        matches = [e for e in feed.entries[:20]
                   if e.get("title") and any(c.isdigit() for c in e.get("title",""))]
        if not matches:
            return

        article = matches[0]
        title   = article.get("title", "")
        h       = hashlib.md5(title.encode()).hexdigest()
        if h == last_poll_hash:
            return

        raw = claude(f"""Составь опрос для Telegram по матчу.
Новость: {title}

Верни ТОЛЬКО JSON:
{{"question": "вопрос до 250 символов", "options": ["вариант1", "вариант2", "вариант3", "вариант4"]}}

Варианты: игроки, команды или смешные варианты. Только русский язык.""", max_tokens=250)

        m = re.search(r"\{.*\}", raw, re.DOTALL)
        if not m:
            return
        data = json.loads(m.group())
        q    = data.get("question","")
        opts = data.get("options",[])
        if q and len(opts) >= 2 and send_poll(q, opts):
            last_poll_hash = h
            print(f"[OK] Голосование: {q[:50]}")
    except Exception as e:
        print(f"[WARN] poll: {e}")

# ─── Запуск ───────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🤖 Футбольный бот v8 запущен! Астана: {now_astana().strftime('%H:%M')}")
    post_news()

    schedule.every(3).hours.do(post_news)
    schedule.every().day.at("09:00").do(post_morning_schedule)
    schedule.every().day.at("21:00").do(post_daily_digest)
    schedule.every(4).hours.do(post_match_poll)

    while True:
        schedule.run_pending()
        time.sleep(30)
