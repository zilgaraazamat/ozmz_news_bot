from api import (
    claude, is_valid_post, pick_photo, is_night,
    fetch_all_news, get_new, mark_sent,
    get_upcoming_matches, now_astana, tg_post, from_config
)

# ── Prompts ───────────────────────────────────────────────────────────────────

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
        a = articles[0]
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


# ── Send helpers ──────────────────────────────────────────────────────────────

def _send(caption, photo=None):
    from api import is_valid_post, pick_photo
    if not is_valid_post(caption):
        print("  [STOP] post failed validation")
        return
    photo = photo or pick_photo()
    chat_id = from_config("CHAT_ID")
    result = tg_post(chat_id, "sendPhoto",
                     photo=photo, caption=caption[:1024], parse_mode="HTML")
    if result:
        print("  [OK] photo sent")
        return
    tg_post(chat_id, "sendMessage", text=caption[:4096], parse_mode="HTML")
    print("  [OK] text sent")


# ── Jobs ──────────────────────────────────────────────────────────────────────

def job_morning():
    print(f"\n[{now_astana().strftime('%H:%M')} AST] Morning match announcement...")
    matches = get_upcoming_matches()
    if not matches:
        print("  No matches found — skipping")
        return
    text = make_morning_post(matches)
    if not text or not is_valid_post(text):
        print("  Text failed validation — skipping")
        return
    _send(f"{text}\n\n#АнонсМатчей")

    # 🎯 NEW: Запускаем конкурс прогнозов на первый матч
    from predict import start_prediction
    start_prediction(matches[0])


def job_news():
    print(f"\n[{now_astana().strftime('%H:%M')} AST] News post...")
    if is_night():
        print("  Night — skipping")
        return
    news = fetch_all_news()
    new  = get_new(news)
    if not new:
        print("  No new articles")
        return
    top  = new[:3] if len(new) >= 3 else new[:1]
    text = make_news_post(top)
    if not text or not is_valid_post(text):
        print("  Text failed validation — skipping")
        return
    mark_sent(top)
    _send(f"{text}\n\n#Футбол")


def job_fact():
    print(f"\n[{now_astana().strftime('%H:%M')} AST] Fact of the day...")
    text = make_fact_post()
    if not text or not is_valid_post(text):
        print("  Text failed validation — skipping")
        return
    _send(f"{text}\n\n#ФактДня #Футбол")
