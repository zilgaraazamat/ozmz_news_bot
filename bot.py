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

BOT_TOKEN     = os.environ.get("BOT_TOKEN", "")
CHAT_ID       = os.environ.get("CHAT_ID", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

ASTANA_TZ = timezone(timedelta(hours=5))

def now_astana():
    return datetime.now(ASTANA_TZ)

def is_night():
    h = now_astana().hour
    return h >= 23 or h < 8

RSS_FEEDS = [
    ("Lenta.ru",  "https://lenta.ru/rss/news/sport/football"),
    ("Чемпионат", "https://www.championat.com/football/rss.xml"),
    ("РИА Спорт", "https://rsport.ria.ru/trend/football_news/"),
    ("Sports.kz", "https://sports.kz/rss/"),
    ("Soccer.ru",  "https://www.soccer.ru/rss/news.xml"),
]

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

used_photos = []
sent_hashes = set()

def pick_photo():
    available = [p for p in PHOTOS if p not in used_photos[-6:]]
    if not available:
        available = PHOTOS
    photo = random.choice(available)
    used_photos.append(photo)
    return photo

# ── Проверка что текст — реальный пост, а не объяснение ──────────────────────

BAD_PHRASES = [
    "я не могу", "не могу написать", "у меня нет данных", "дезинформация",
    "нет информации", "к сожалению", "извините", "не имею доступа",
    "что могу сделать", "что я могу", "турнир ещё не начался",
    "могу предложить", "если ты скинешь", "шаблон поста",
]

def is_valid_post(text: str) -> bool:
    if not text or len(text) < 50:
        return False
    text_lower = text.lower()
    for phrase in BAD_PHRASES:
        if phrase in text_lower:
            print(f"  [WARN] Текст содержит запрещённую фразу: '{phrase}' — не постим")
            return False
    return True

# ── Получение новостей ────────────────────────────────────────────────────────

def fetch_article_text(url):
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

def get_new(articles):
    return [a for a in articles
            if hashlib.md5(a["title"].encode()).hexdigest() not in sent_hashes]

def mark_sent(articles):
    for a in articles:
        sent_hashes.add(hashlib.md5(a["title"].encode()).hexdigest())

# ── Расписание матчей ─────────────────────────────────────────────────────────

def get_upcoming_matches():
    matches = []
    now = now_astana()
    try:
        date_from = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
        date_to   = (now + timedelta(days=1)).astimezone(timezone.utc).strftime("%Y-%m-%d")
        r = requests.get(
            "https://api.football-data.org/v4/matches",
            headers={"X-Auth-Token": os.environ.get("FOOTBALL_API_KEY", "")},
            params={"dateFrom": date_from, "dateTo": date_to},
            timeout=10,
        )
        if r.ok:
            for m in r.json().get("matches", []):
                status   = m.get("status", "")
                if status not in ("TIMED", "SCHEDULED"):
                    continue
                utc_time = m.get("utcDate", "")
                home     = m.get("homeTeam", {}).get("name", "")
                away     = m.get("awayTeam", {}).get("name", "")
                comp     = m.get("competition", {}).get("name", "")
                if utc_time and home and away:
                    utc_dt  = datetime.strptime(utc_time, "%Y-%m-%dT%H:%M:%SZ")
                    ast_dt  = utc_dt.replace(tzinfo=timezone.utc).astimezone(ASTANA_TZ)
                    if ast_dt > now:
                        matches.append({
                            "home": home, "away": away,
                            "time": ast_dt.strftime("%d.%m %H:%M"),
                            "comp": comp,
                        })
        else:
            print(f"  [WARN] football-data.org: {r.status_code}")
    except Exception as e:
        print(f"  [WARN] football-data.org: {e}")
    return matches[:6]

# ── Claude API ────────────────────────────────────────────────────────────────

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
        print(f"  [Claude] ОШИБКА: {e}")
        return ""

# ── Составление постов ────────────────────────────────────────────────────────

def make_news_post(articles):
    if len(articles) >= 3:
        block = "\n".join(
            f"{i+1}. {a['title']} — {(a.get('full_text') or a.get('summary',''))[:400]}"
            for i, a in enumerate(articles[:3])
        )
        prompt = f"""Ты — спортивный Telegram-канал. Только русский язык.

Новости:
{block}

Напиши пост. Формат:
🔥 ГОРЯЧЕЕ

• [эмодзи] Новость 1: точный счёт/факт + 1 смешная фраза
• [эмодзи] Новость 2: точный счёт/факт + 1 смешная фраза
• [эмодзи] Новость 3: точный счёт/факт + 1 смешная фраза

Счёт и имена — строго из текста. Коротко. Без ссылок. Без объяснений."""
    else:
        a     = articles[0]
        facts = (a.get("full_text") or a.get("summary", ""))[:1200]
        prompt = f"""Ты — спортивный Telegram-канал. Только русский язык.

Новость: {a["title"]}
Текст: {facts}

Напиши короткий пост:
[эмодзи] [суть с точным счётом и именами — 1 предложение]

[2 смешных предложения с эмодзи]

Без ссылок. Без объяснений."""
    return claude(prompt)

def make_morning_post(matches):
    if not matches:
        return ""
    block = "\n".join(
        f"• {m['home']} — {m['away']} | {m['time']} AST | {m['comp']}"
        for m in matches
    )
    prompt = f"""Ты — спортивный Telegram-канал. Только русский язык.

Реальные предстоящие матчи (ближайшие 24 часа):
{block}

Напиши анонс. Формат:
⚽ МАТЧИ БЛИЖАЙШИХ 24 ЧАСОВ

🆚 Команда А — Команда Б | 🕐 ДД.ММ ЧЧ:ММ AST
🔮 одна смешная фраза-прогноз

Используй ТОЧНЫЕ названия и время из списка выше. Без ссылок. Без объяснений."""
    return claude(prompt, max_tokens=400)

def make_fact_post():
    prompt = f"""Ты — спортивный Telegram-канал. Только русский язык.
Сегодня {now_astana().strftime('%d.%m.%Y')}.

Напиши один интересный малоизвестный факт из истории футбола. Каждый раз разная тема.

Формат:
🧠 ФАКТ ДНЯ

[эмодзи] [факт — 2-3 предложения, интересно и с лёгким юмором]

Без ссылок."""
    return claude(prompt, max_tokens=250)

# ── Отправка ──────────────────────────────────────────────────────────────────

def send(caption, photo=None):
    if not is_valid_post(caption):
        print("  [СТОП] Текст не прошёл проверку — не отправляем в группу")
        return

    if photo is None:
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
            print("  [OK] Фото отправлено")
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
    print(f"\n[{now_astana().strftime('%H:%M')} AST] Утренний анонс матчей...")
    matches = get_upcoming_matches()
    if not matches:
        print("  Матчи не найдены через API — пропускаем")
        return
    text = make_morning_post(matches)
    if not text or not is_valid_post(text):
        print("  Текст не прошёл проверку — пропускаем")
        return
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
    if not text or not is_valid_post(text):
        print("  Текст не прошёл проверку — пропускаем")
        return
    mark_sent(top)
    send(f"{text}\n\n#Футбол")

def job_fact():
    print(f"\n[{now_astana().strftime('%H:%M')} AST] Факт дня...")
    text = make_fact_post()
    if not text or not is_valid_post(text):
        print("  Текст не прошёл проверку — пропускаем")
        return
    send(f"{text}\n\n#ФактДня #Футбол")

# ── Тест "Кто ты из футболистов?" ────────────────────────────────────────────

quiz_used_today = ""
quiz_sessions   = {}
quiz_offset     = 0
quiz_history    = []  # [{name, player, date, user_id}]

QUIZ_QUESTIONS = [
    ("Как ты ведёшь себя на поле?", ["Я лидер, всё через меня", "Работяга в обороне", "Творю магию в атаке", "Дирижирую из центра"]),
    ("Твой стиль игры?", ["Скорость и дриблинг", "Сила и напор", "Точность и техника", "Умная позиция"]),
    ("Что делаешь после гола?", ["Бегу к угловому флагу", "Спокойно иду на центр", "Кричу и прыгаю на партнёров", "Показываю жест команде"]),
    ("Твоя любимая позиция?", ["Нападающий", "Полузащитник", "Защитник", "Всё равно — главное играть"]),
    ("Финал, 0:0, серия пенальти. Ты:", ["Иду первым — не боюсь", "Жду своей очереди спокойно", "Отказываюсь — не мой день", "Бью последним, как герой"]),
    ("Твоё отношение к тренеру?", ["Спорю — я лучше знаю", "Уважаю и слушаюсь", "Делаю по-своему на поле", "Нейтрально, лишь бы играть"]),
    ("Как готовишься к матчу?", ["Музыка и концентрация", "Тактический разбор", "Разминка и растяжка", "Просто выхожу и играю"]),
    ("Твой кумир в детстве?", ["Роналду", "Месси", "Зидан", "Роналдиньо"]),
    ("Что важнее?", ["Личные голы и рекорды", "Командный трофей", "Красивая игра", "Признание болельщиков"]),
    ("Как заканчиваешь карьеру?", ["На вершине — ухожу чемпионом", "Играю до последнего", "Становлюсь тренером", "Ещё не думал об этом"]),
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
    answers_text = "\n".join(f"{i+1}. {QUIZ_QUESTIONS[i][0]} — {a}" for i, a in enumerate(answers))
    prompt = f"""Пользователь прошёл тест "Кто ты из футболистов?".

Ответы:
{answers_text}

Список: {", ".join(FOOTBALLERS)}

Выбери ОДНОГО футболиста и напиши результат:

🏆 Ты — [имя]!

[2-3 предложения почему — смешно и по ответам]

Только русский. Без ссылок."""
    return claude(prompt, max_tokens=250)

def start_quiz(user_id, user_name):
    global quiz_used_today
    quiz_used_today = now_astana().strftime("%d.%m.%Y")
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
        name   = session["name"]

        # Извлекаем имя футболиста из результата
        player_name = next((p for p in FOOTBALLERS if p in result), None)
        photo_url   = PLAYER_PHOTOS.get(player_name, pick_photo()) if player_name else pick_photo()

        # Сохраняем в историю
        quiz_history.append({
            "name":    name,
            "player":  player_name or "Неизвестно",
            "date":    now_astana().strftime("%d.%m.%Y %H:%M"),
            "user_id": user_id,
        })

        # 1. Отправляем результат в личку с фото
        personal_text = f"🏆 <b>Твой результат:</b>\n\n{result}\n\n👥 Поделись с командой: @football_igraem_astana"
        send_photo_msg(user_id, personal_text, photo_url)

        # 2. Постим в группу с фото и ссылками
        group_text = (
            f"🎮 <b>{name}</b> прошёл тест!\n\n"
            f"{result}\n\n"
            f"👥 Наша группа: @football_igraem_astana\n"
            f"🤖 Пройди тест сам — напиши боту <b>кто я</b>\n\n"
            f"#КтоТыИзФутболистов"
        )
        send(group_text, photo_url)
        del quiz_sessions[user_id]
    else:
        q, opts = QUIZ_QUESTIONS[step]
        send_msg(user_id, f"<b>Вопрос {step+1}/10:</b>\n{q}", [[o] for o in opts])

# Фото футболистов для результата
PLAYER_PHOTOS = {
    "Криштиану Роналду":   "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Cristiano_Ronaldo_in_2018.jpg/800px-Cristiano_Ronaldo_in_2018.jpg",
    "Лионель Месси":       "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Messi_vs_Nigeria_2018.jpg/1024px-Messi_vs_Nigeria_2018.jpg",
    "Килиан Мбаппе":       "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/2019-07-17_SG_Dynamo_Dresden_vs._Paris_Saint-Germain_F.C._by_Sandro_Halank–074_%28cropped%29.jpg/800px-2019-07-17_SG_Dynamo_Dresden_vs._Paris_Saint-Germain_F.C._by_Sandro_Halank–074_%28cropped%29.jpg",
    "Эрлинг Холанд":       "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Erling_Haaland_2022_%28cropped%29.jpg/800px-Erling_Haaland_2022_%28cropped%29.jpg",
    "Неймар":              "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Bra-Col_%281%29_%28cropped%29.jpg/800px-Bra-Col_%281%29_%28cropped%29.jpg",
    "Зинедин Зидан":       "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Zinedine_Zidane_by_Tasnim_03.jpg/800px-Zinedine_Zidane_by_Tasnim_03.jpg",
    "Роналдиньо":          "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Ronaldinho_in_2018.jpg/800px-Ronaldinho_in_2018.jpg",
    "Тьерри Анри":         "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Thierry_Henry_2.jpg/800px-Thierry_Henry_2.jpg",
    "Андрес Иньеста":      "https://upload.wikimedia.org/wikipedia/commons/thumb/5/fifty/Andres_Iniesta_2010.jpg/800px-Andres_Iniesta_2010.jpg",
    "Роберт Левандовски":  "https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/Robert_Lewandowski%2C_FC_Bayern_München_%28by_Sven_Mandel%2C_2019-09-28%29_02_%28cropped%29.jpg/800px-Robert_Lewandowski%2C_FC_Bayern_München_%28by_Sven_Mandel%2C_2019-09-28%29_02_%28cropped%29.jpg",
}

def send_photo_msg(chat_id, caption, photo_url):
    """Отправляет фото в личку пользователю."""
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            json={"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "HTML"},
            timeout=20,
        )
        if r.ok:
            return True
        # fallback — текстом
        send_msg(chat_id, caption)
        return False
    except:
        send_msg(chat_id, caption)
        return False

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

            if text in ("/start", "/help", "помощь", "help"):
                send_msg(user_id,
                    "👋 Привет! Я футбольный бот группы @football_igraem_astana\n\n"
                    "Что умею:\n"
                    "⚽ Постю новости футбола каждый день\n"
                    "🧠 Кидаю факт дня\n"
                    "📅 Анонсирую ближайшие матчи\n"
                    "🎮 Тест — кто ты из футболистов?\n\n"
                    "Напиши <b>кто я</b> или <b>тест</b> — и узнаешь на какого футболиста ты похож! 🏆"
                )
            elif any(kw in text.lower() for kw in ["тест", "кто я", "футболист", "/тест", "quiz"]):
                today = now_astana().strftime("%d.%m.%Y")
                if quiz_used_today == today:
                    send_msg(user_id,
                        "⚽ Тест уже прошли сегодня — тебе не повезло 😄\n\n"
                        "Тест можно пройти только 1 раз в день, и кто-то успел раньше тебя.\n"
                        "Возвращайся завтра — может в этот раз окажешься первым! 🏆"
                    )
                else:
                    start_quiz(user_id, name)
            elif user_id in quiz_sessions:
                handle_quiz_answer(user_id, text)
    except Exception as e:
        print(f"  [WARN] poll: {e}")

# ── Запуск ────────────────────────────────────────────────────────────────────

# ── Веб-сервер для панели админа ─────────────────────────────────────────────

from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "football2026")

class AdminHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass  # отключаем логи запросов

    def do_GET(self):
        if self.path == "/":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()

            # Статистика
            total     = len(quiz_history)
            players   = {}
            for h in quiz_history:
                players[h["player"]] = players.get(h["player"], 0) + 1
            top_player = max(players, key=players.get) if players else "—"

            rows = ""
            for i, h in enumerate(reversed(quiz_history), 1):
                rows += f"""
                <tr>
                  <td>{i}</td>
                  <td>{h['name']}</td>
                  <td><span class="badge">{h['player']}</span></td>
                  <td>{h['date']}</td>
                </tr>"""

            html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚽ Панель Админа</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: -apple-system, sans-serif; background: #0e1a12; color: #f5f5f0; min-height: 100vh; padding: 24px; }}
  .header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 28px; }}
  .header h1 {{ font-size: 24px; font-weight: 700; }}
  .header span {{ font-size: 32px; }}
  .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 28px; }}
  .stat {{ background: #1e3024; border: 1px solid rgba(126,217,87,.15); border-radius: 12px; padding: 16px; }}
  .stat-num {{ font-size: 32px; font-weight: 700; color: #7ed957; }}
  .stat-label {{ font-size: 13px; color: #6b7c6e; margin-top: 4px; }}
  .table-wrap {{ background: #1e3024; border: 1px solid rgba(126,217,87,.15); border-radius: 12px; overflow: hidden; }}
  table {{ width: 100%; border-collapse: collapse; }}
  th {{ background: rgba(126,217,87,.1); padding: 12px 16px; text-align: left; font-size: 12px; color: #7ed957; letter-spacing: 1px; text-transform: uppercase; }}
  td {{ padding: 12px 16px; border-top: 1px solid rgba(255,255,255,.05); font-size: 14px; }}
  tr:hover td {{ background: rgba(255,255,255,.03); }}
  .badge {{ background: rgba(126,217,87,.15); color: #7ed957; padding: 3px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }}
  .empty {{ text-align: center; padding: 48px; color: #6b7c6e; }}
  .refresh {{ margin-top: 16px; text-align: center; }}
  .refresh a {{ color: #7ed957; text-decoration: none; font-size: 13px; }}
</style>
</head>
<body>
<div class="header"><span>⚽</span><h1>Панель Админа — Football Bot</h1></div>
<div class="stats">
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Тестов пройдено</div></div>
  <div class="stat"><div class="stat-num">{len(players)}</div><div class="stat-label">Разных футболистов</div></div>
  <div class="stat"><div class="stat-num" style="font-size:18px">{top_player}</div><div class="stat-label">Самый популярный</div></div>
  <div class="stat"><div class="stat-num">{now_astana().strftime('%H:%M')}</div><div class="stat-label">Время (AST)</div></div>
</div>
<div class="table-wrap">
  <table>
    <thead><tr><th>#</th><th>Игрок</th><th>Футболист</th><th>Дата и время</th></tr></thead>
    <tbody>{"" if rows else '<tr><td colspan="4" class="empty">Тестов ещё не было 🎮</td></tr>'}{rows}</tbody>
  </table>
</div>
<div class="refresh"><a href="/">↻ Обновить</a></div>
</body></html>"""
            self.wfile.write(html.encode("utf-8"))
        else:
            self.send_response(404)
            self.end_headers()

def run_admin_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), AdminHandler)
    print(f"  Панель админа: http://0.0.0.0:{port}")
    server.serve_forever()

if __name__ == "__main__":
    print(f"🤖 Бот запущен | Астана: {now_astana().strftime('%d.%m.%Y %H:%M')}")
    print("Расписание:")
    print("  09:00 AST — Анонс матчей (ближайшие 24ч)")
    print("  15:00 AST — Новостной пост")
    print("  20:00 AST — Факт дня")

    # Запускаем панель админа в фоне
    admin_thread = threading.Thread(target=run_admin_server, daemon=True)
    admin_thread.start()

    job_morning()

    schedule.every().day.at("04:00").do(job_morning)  # 09:00 AST
    schedule.every().day.at("10:00").do(job_news)     # 15:00 AST
    schedule.every().day.at("15:00").do(job_fact)     # 20:00 AST

    while True:
        schedule.run_pending()
        poll_updates()
        time.sleep(5)
