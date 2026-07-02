import time
import schedule
import requests

from config import BOT_TOKEN, RAILWAY_DOMAIN, PORT
from api import now_astana, send_msg, tg_post
from posts import job_morning, job_news, job_fact
import quiz
from quiz import quiz_sessions, start_quiz, handle_quiz_answer
from predict import predict_state, handle_prediction
import server

# ── Polling ───────────────────────────────────────────────────────────────────

_offset = 0


def poll():
    global _offset
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"offset": _offset, "timeout": 5},
            timeout=10,
        )
        if not r.ok:
            return
        for update in r.json().get("result", []):
            _offset = update["update_id"] + 1
            msg = update.get("message", {})
            if not msg:
                continue
            text    = msg.get("text", "").strip()
            user_id = str(msg.get("from", {}).get("id", ""))
            name    = msg.get("from", {}).get("first_name", "Игрок")
            if not user_id or not text:
                continue
            _handle(user_id, name, text)
    except Exception as e:
        print(f"  [WARN] poll: {e}")


def _handle(user_id, name, text):
    tl = text.lower()

    # /start
    if text in ("/start", "/help", "помощь", "help"):
        quiz_url = (
            f"https://{RAILWAY_DOMAIN}/quiz"
            if RAILWAY_DOMAIN
            else f"http://localhost:{PORT}/quiz"
        )
        keyboard = [[{"text": "🎮 Пройти тест!", "web_app": {"url": quiz_url}}]]
        payload = {
            "text": (
                "👋 Привет! Я бот группы <b>OZMZ Football Astana</b>\n\n"
                "Мы организуем футбольные игры в Астане 🏙️⚽\n\n"
                "Нажми кнопку ниже — узнай, кто ты из великих футболистов! 👇"
            ),
            "parse_mode": "HTML",
            "reply_markup": {"keyboard": keyboard, "resize_keyboard": True},
        }
        try:
            tg_post(user_id, "sendMessage", **payload)
        except:
            send_msg(user_id,
                f"👋 Привет! Пройди тест: {quiz_url}")

    # 🎯 прогноз счёта
    elif tl.startswith("/счёт") or tl.startswith("/score"):
        handle_prediction(user_id, name, text)

    # квиз — запуск
    elif any(kw in tl for kw in ["тест", "кто я", "футболист", "/тест", "quiz"]):
        today = now_astana().strftime("%d.%m.%Y")
        if quiz.quiz_used_today == today:
            send_msg(user_id,
                "⚽ Тест уже прошли сегодня — тебе не повезло 😄\n\n"
                "Тест можно пройти только 1 раз в день.\n"
                "Возвращайся завтра — может успеешь первым! 🏆")
        else:
            start_quiz(user_id, name)

    # квиз — ответ
    elif user_id in quiz_sessions:
        handle_quiz_answer(user_id, text)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    print(f"🤖 OZMZ Bot started | Астана: {now_astana().strftime('%d.%m.%Y %H:%M')}")
    print("Schedule:")
    print("  04:00 UTC (09:00 AST) — Match announcement + Prediction contest")
    print("  10:00 UTC (15:00 AST) — News post")
    print("  15:00 UTC (20:00 AST) — Fact of the day")

    server.start_background()

    job_morning()  # run once on start

    schedule.every().day.at("04:00").do(job_morning)
    schedule.every().day.at("10:00").do(job_news)
    schedule.every().day.at("15:00").do(job_fact)

    while True:
        schedule.run_pending()
        poll()
        time.sleep(5)
