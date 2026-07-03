import random
from api import claude, now_astana, send_msg, send_photo_msg, tg_post, from_config, pick_photo
from config import QUIZ_QUESTIONS, FOOTBALLERS, PLAYER_PHOTOS, PLAYER_CATEGORIES
from storage import set_role

quiz_used_today = ""
quiz_sessions   = {}   # {user_id: {answers, step, name}}
quiz_history    = []   # [{name, player, date, user_id}]


def quiz_result_text(answers):
    answers_text = "\n".join(
        f"{i+1}. {QUIZ_QUESTIONS[i][0]} — {a}"
        for i, a in enumerate(answers)
    )
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
        f"🎮 <b>Кто ты из футболистов?</b>\n\n"
        f"10 вопросов — отвечай честно!\n\n"
        f"<b>Вопрос 1/10:</b>\n{q}",
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
        result = quiz_result_text(session["answers"]) or f"🏆 Ты — {random.choice(FOOTBALLERS)}!"
        name   = session["name"]

        player_name = next((p for p in FOOTBALLERS if p in result), None)
        photo_url   = PLAYER_PHOTOS.get(player_name, pick_photo()) if player_name else pick_photo()
        category    = PLAYER_CATEGORIES.get(player_name, "Центр")
        set_role(user_id, name, player_name or "Неизвестно", category)

        quiz_history.append({
            "name":    name,
            "player":  player_name or "Неизвестно",
            "date":    now_astana().strftime("%d.%m.%Y %H:%M"),
            "user_id": user_id,
        })

        # личка
        send_photo_msg(user_id,
            f"🏆 <b>Твой результат:</b>\n\n{result}\n\n"
            f"👥 Поделись с командой: @football_igraem_astana",
            photo_url)

        # группа
        chat_id = from_config("CHAT_ID")
        group_text = (
            f"🎮 <b>{name}</b> прошёл тест!\n\n"
            f"{result}\n\n"
            f"👥 @football_igraem_astana\n"
            f"🤖 Пройди тест — напиши боту <b>кто я</b>\n\n"
            f"#КтоТыИзФутболистов"
        )
        tg_post(chat_id, "sendPhoto",
                photo=photo_url, caption=group_text[:1024], parse_mode="HTML")

        del quiz_sessions[user_id]
    else:
        q, opts = QUIZ_QUESTIONS[step]
        send_msg(user_id,
            f"<b>Вопрос {step+1}/10:</b>\n{q}",
            [[o] for o in opts])
