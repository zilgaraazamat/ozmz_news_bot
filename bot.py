import os
import re
import time
import random
import hashlib
import requests
import schedule
import feedparser
from datetime import datetime, timezone, timedelta

# ── Настройки ─────────────────────────────────────────────────────────────────
BOT_TOKEN     = os.environ.get("BOT_TOKEN", "")
CHAT_ID       = os.environ.get("CHAT_ID", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ASTANA_TZ = timezone(timedelta(hours=5))

def now_astana():
    return datetime.now(ASTANA_TZ)

def is_night():
    h = now_astana().hour
    return h >= 23 or h < 8

# ── RSS источники ─────────────────────────────────────────────────────────────
RSS_FEEDS = [
    ("Lenta.ru",  "https://lenta.ru/rss/news/sport/football"),
    ("Чемпионат", "https://www.championat.com/football/rss.xml"),
    ("РИА Спорт", "https://rsport.ria.ru/trend/football_news/"),
    ("Sports.kz", "https://sports.kz/rss/"),
    ("Soccer.ru",  "https://www.soccer.ru/rss/news.xml"),
]

# ── 16 фото ───────────────────────────────────────────────────────────────────
PHOTOS = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Wembley_Stadium_interior.jpg/1280px-Wembley_Stadium_interior.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Camp_Nou_aerial_%28cropped%29.jpg/1280px-Camp_Nou_aerial_%28cropped%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Allianz_Arena_Abend.jpg/1280px-Allianz_Arena_Abend.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg/1280px-Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Stadio_Giuseppe_Meazza_%28Milano%29.jpg/1280px-Stadio_Giuseppe_Meazza_%28Milano%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Stade_de_France_2007.jpg/1280px-Stade_de_France_2007.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Luzhniki_Stadium_2018_FIFA_World_Cup.jpg/1280px-Luzhniki_Stadium_2018_FIFA_World_Cup.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Metropolitano_-_Atletico_de_Madrid.jpg/1280px-Metropolitano_-_Atletico_de_Madrid.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg/1280px-FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/4/43/Chelsea_vs_PSG_-_Stamford_Bridge_%28cropped%29.jpg/1280px-Chelsea_vs_PSG_-_Stamford_Bridge_%28cropped%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Messi_vs_Nigeria_2018.jpg/1024px-Messi_vs_Nigeria_2018.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Cristiano_Ronaldo_in_2018.jpg/800px-Cristiano_Ronaldo_in_2018.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/a/ad/Football_iu_1996.jpg/1280px-Football_iu_1996.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Soccerball.jpg/800px-Soccerball.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/FIFA_World_Cup_2018_-_Group_F_-_Germany_v_Sweden_%2821%29_%28cropped%29.jpg/1280px-FIFA_World_Cup_2018_-_Group_F_-_Germany_v_Sweden_%2821%29_%28cropped%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/2018_FIFA_World_Cup_Russia%2C_Round_of_16%2C_France_vs_Argentina_%2801%29.jpg/1280px-2018_FIFA_World_Cup_Russia%2C_Round_of_16%2C_France_vs_Argentina_%2801%29.jpg",
]

used_photos: list = []
sent_hashes: set  = set()

def pick_photo() -> str:
    available = [p for p in PHOTOS if p not in used_photos[-6:]]
    if not available:
        available = PHOTOS
    photo = random.choice(available)
    used_photos.append(photo)
    return photo

# ── Получение новостей ────────────────────────────────────────────────────────

def fetch_article_text(url: str) -> str:
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

def fetch_all_news() -> list:
    articles = []
    for name, url in RSS_FEEDS:
        try:
            feed = feedparser.parse(url)
            print(f"  [{name}] {len(feed.entries)} записей")
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
                })
        except Exception as e:
            print(f"  [{name}] ОШИБКА: {e}")
    return articles

def get_new(articles: list) -> list:
    return [a for a in articles
            if hashlib.md5(a["title"].encode()).hexdigest() not in sent_hashes]

def mark_sent(articles: list):
    for a in articles:
        sent_hashes.add(hashlib.md5(a["title"].encode()).hexdigest())

# ── Claude API ────────────────────────────────────────────────────────────────

def claude(prompt: str, max_tokens: int = 350) -> str:
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
        print(f"  [Claude] ОШИБКА: {e}")
        return ""

# ── Составление постов ────────────────────────────────────────────────────────

def make_news_post(articles: list) -> str:
    if len(articles) >= 3:
        block = "\n".join(
            f"{i+1}. {a['title']} — {(a.get('full_text') or a.get('summary',''))[:400]}"
            for i, a in enumerate(articles[:3])
        )
        prompt = f"""Ты — спортивный Telegram-канал. Только русский язык.

Новости:
{block}

Формат поста:
🔥 ГОРЯЧЕЕ

• [эмодзи] Новость 1: точный счёт/факт + 1 смешная фраза
• [эмодзи] Новость 2: точный счёт/факт + 1 смешная фраза
• [эмодзи] Новость 3: точный счёт/факт + 1 смешная фраза

Счёт и имена — строго из текста. Коротко. Без ссылок."""
    else:
        a     = articles[0]
        facts = (a.get("full_text") or a.get("summary", ""))[:1200]
        prompt = f"""Ты — спортивный Telegram-канал. Только русский язык.

Новость: {a["title"]}
Текст: {facts}

Формат поста:
[эмодзи] [1 предложение: суть с точным счётом и именами]

[2 предложения смешного комментария с эмодзи]

Если есть счёт — пиши точно (например 2:1). Без ссылок."""
    return claude(prompt)

def make_morning_post() -> str:
    try:
        feed   = feedparser.parse("https://lenta.ru/rss/news/sport/football")
        titles = [e.get("title","") for e in feed.entries[:10] if e.get("title")]
    except:
        titles = []

    prompt = f"""Ты — спортивный Telegram-канал. Только русский язык.
Сегодня {now_astana().strftime('%d.%m.%Y')}.
Заголовки: {"; ".join(titles[:8])}

Формат поста:
☀️ МАТЧИ ДНЯ — {now_astana().strftime('%d.%m')}

🆚 Команда А — Команда Б | 🕐 ЧЧ:ММ (AST)
🔮 одна смешная фраза-прогноз

(3-4 матча)

Без ссылок. Если точное время неизвестно — не пиши время."""
    return claude(prompt, max_tokens=350)

def make_fact_post() -> str:
    prompt = f"""Ты — спортивный Telegram-канал. Только русский язык.

Напиши один интересный футбольный факт. Это должно быть что-то неожиданное, малоизвестное или смешное из истории футбола.
Каждый раз выбирай разную тему: рекорды, курьёзы, странные правила, необычные истории игроков, удивительная статистика.
Сегодня {now_astana().strftime('%d.%m.%Y')} — придумай факт который ещё не приелся.

Формат:
🧠 ФАКТ ДНЯ

[эмодзи] [сам факт — 2-3 предложения, интересно и с лёгким юмором]

Без ссылок. Только русский."""
    return claude(prompt, max_tokens=250)

# ── Отправка ──────────────────────────────────────────────────────────────────

def send(caption: str):
    photo = pick_photo()
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={
                "chat_id":    CHAT_ID,
                "photo":      photo,
                "caption":    caption[:1024],
                "parse_mode": "HTML",
            },
            timeout=20,
        )
        if r.ok:
            print(f"  [OK] Фото отправлено")
            return
        print(f"  [WARN] Фото не прошло ({r.status_code}), шлём текстом")
    except Exception as e:
        print(f"  [WARN] {e}")

    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": CHAT_ID, "text": caption[:4096], "parse_mode": "HTML"},
            timeout=10,
        )
        print("  [OK] Текст отправлен")
    except Exception as e:
        print(f"  [ERROR] {e}")

# ── Задачи ────────────────────────────────────────────────────────────────────

def job_morning():
    print(f"\n[{now_astana().strftime('%H:%M')} AST] Утренний анонс...")
    text = make_morning_post()
    if text:
        send(f"{text}\n\n#АнонсМатчей")

def job_news():
    print(f"\n[{now_astana().strftime('%H:%M')} AST] Новостной пост...")
    if is_night():
        print("  Ночь — пропускаем")
        return
    news = fetch_all_news()
    new  = get_new(news)
    if not new:
        print("  Нет новых новостей")
        return
    top  = new[:3] if len(new) >= 3 else new[:1]
    text = make_news_post(top)
    if not text:
        return
    mark_sent(top)
    send(f"{text}\n\n#Футбол")

def job_fact():
    print(f"\n[{now_astana().strftime('%H:%M')} AST] Факт дня...")
    text = make_fact_post()
    if text:
        send(f"{text}\n\n#ФактДня #Футбол")

# ── Тест "Кто ты из футболистов?" ────────────────────────────────────────────

quiz_used_today: str = ""
quiz_sessions: dict  = {}
quiz_offset: int     = 0

QUIZ_QUESTIONS = [
    ("Как ты ведёшь себя на поле?", ["Я лидер, всё через меня", "Работяга в обороне", "Творю магию в атаке", "Дирижирую из центра"]),
    ("Твой стиль игры?", ["Скорость и дриблинг", "Сила и напор", "Точность и техника", "Умная позиция"]),
    ("Что делаешь после гола?", ["Бегу к угловому флагу", "Спокойно иду на центр", "Кричу и прыгаю", "Показываю жест команде"]),
    ("Твоя любимая позиция?", ["Нападающий", "Полузащитник", "Защитник", "Всё равно — главное играть"]),
    ("Ты в финале, счёт 0:0, пенальти. Ты:", ["Иду первым — не боюсь", "Жду своей очереди спокойно", "Отказываюсь — не мой день", "Бью последним, как герой"]),
    ("Твоё отношение к тренеру?", ["Спорю — я лучше знаю", "Уважаю, слушаюсь", "Делаю по-своему на поле", "Нейтрально"]),
    ("Как ты готовишься к матчу?", ["Музыка и концентрация", "Тактический разбор", "Разминка и растяжка", "Просто выхожу и играю"]),
    ("Твой кумир в детстве?", ["Роналду", "Месси", "Зидан", "Роналдиньо"]),
    ("Что важнее?", ["Личные голы и рекорды", "Командный трофей", "Красивая игра", "Деньги и слава"]),
    ("Как заканчиваешь карьеру?", ["На вершине — ухожу чемпионом", "Играю до последнего", "Тренером после", "Ещё не думал об этом"]),
]

FOOTBALLERS = ["Криштиану Роналду", "Лионель Месси", "Килиан Мбаппе", "Эрлинг Холанд",
               "Неймар", "Зинедин Зидан", "Роналдиньо", "Тьерри Анри", "Андрес Иньеста", "Роберт Левандовски"]

def send_msg(chat_id, text, keyboard=None):
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard:
        payload["reply_markup"] = {"keyboard": keyboard, "resize_keyboard": True, "one_time_keyboard": True}
    try:
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", json=payload, timeout=10)
    except Exception as e:
        print(f"  [ERROR] send_msg: {e}")

def quiz_result(answers):
    answers_text = "\n".join(f"{i+1}. {QUIZ_QUESTIONS[i][0]} - {a}" for i, a in enumerate(answers))
    prompt = f"""Пользователь прошёл тест "Кто ты из футболистов?".

Его ответы:
{answers_text}

Список футболистов: {", ".join(FOOTBALLERS)}

Выбери ОДНОГО подходящего футболиста и напиши:

🏆 Ты — [имя]!

[2-3 предложения почему именно он, смешно и по ответам]

Только русский. Без ссылок."""
    return claude(prompt, max_tokens=250)

def start_quiz(user_id, user_name):
    global quiz_used_today
    today = now_astana().strftime("%d.%m.%Y")
    if quiz_used_today == today:
        send_msg(user_id, "⚽ Тест уже прошли сегодня! Возвращайся завтра 😄")
        return
    quiz_used_today = today
    quiz_sessions[user_id] = {"answers": [], "step": 0, "name": user_name}
    q, opts = QUIZ_QUESTIONS[0]
    send_msg(user_id,
        f"🎮 <b>Кто ты из футболистов?</b>\n\n10 вопросов — отвечай честно!\n\n<b>Вопрос 1/10:</b>\n{q}",
        [[o] for o in opts])

def handle_quiz_answer(user_id, text):
    session = quiz_sessions.get(user_id)
    if not session:
        return
    step = session["step"]
    _, opts = QUIZ_QUESTIONS[step]
    if text not in opts:
        return
    session["answers"].append(text)
    session["step"] += 1
    step = session["step"]
    if step >= len(QUIZ_QUESTIONS):
        send_msg(user_id, "⏳ Анализирую результат...")
        result = quiz_result(session["answers"]) or f"🏆 Ты — {random.choice(FOOTBALLERS)}!"
        name = session["name"]
        send(f"🎮 <b>{name}</b> прошёл тест!\n\n{result}\n\n#КтоТыИзФутболистов")
        del quiz_sessions[user_id]
    else:
        q, opts = QUIZ_QUESTIONS[step]
        send_msg(user_id, f"<b>Вопрос {step+1}/10:</b>\n{q}", [[o] for o in opts])

def poll_updates():
    global quiz_offset
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"offset": quiz_offset, "timeout": 5},
            timeout=10,
        )
        if not r.ok:
            return
        for update in r.json().get("result", []):
            quiz_offset = update["update_id"] + 1
            msg = update.get("message", {})
            if not msg:
                continue
            text    = msg.get("text", "").strip()
            user_id = str(msg.get("from", {}).get("id", ""))
            name    = msg.get("from", {}).get("first_name", "Игрок")
            if not user_id or not text:
                continue
            if any(kw in text.lower() for kw in ["тест", "кто я", "футболист", "/тест", "quiz"]):
                start_quiz(user_id, name)
            elif user_id in quiz_sessions:
                handle_quiz_answer(user_id, text)
    except Exception as e:
        print(f"  [WARN] poll: {e}")

# ── Запуск ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🤖 Бот запущен | Астана: {now_astana().strftime('%d.%m.%Y %H:%M')}")
    print("Расписание:")
    print("  09:00 AST — Утренний анонс матчей")
    print("  15:00 AST — Новостной пост")
    print("  20:00 AST — Факт дня")
    print("  Тест: пиши боту в ЛС слово 'тест'")

    job_morning()

    schedule.every().day.at("04:00").do(job_morning)  # 09:00 AST
    schedule.every().day.at("10:00").do(job_news)     # 15:00 AST
    schedule.every().day.at("15:00").do(job_fact)     # 20:00 AST

    while True:
        schedule.run_pending()
        poll_updates()
        time.sleep(5)
