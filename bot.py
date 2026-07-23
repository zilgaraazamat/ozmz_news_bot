import time
import schedule
import requests

from config import BOT_TOKEN, RAILWAY_DOMAIN, PORT, ADMIN_IDS
from api import now_astana, send_msg, tg_post
from posts import job_morning, job_news, job_fact
from quiz import quiz_sessions, handle_quiz_answer
from predict import handle_prediction
from storage import init_db, get_role, has_phone, save_phone, save_username
from teams import handle_teams_command
import server

# ── Polling ───────────────────────────────────────────────────────────────────

_offset = 0

# user_id -> токен приглашения, если игрок пришёл по start=inv_... но ещё не
# зарегистрирован (нет телефона). После того как он поделится контактом,
# _handle_contact продолжит флоу занятия места с этим токеном.
_pending_invite = {}


def poll():
    global _offset
    try:
        r = requests.get(
            f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates",
            params={"offset": _offset, "timeout": 5},
            timeout=10,
        )
        if not r.ok:
            print(f"  [WARN] getUpdates HTTP {r.status_code}: {r.text[:300]}")
            return
        for update in r.json().get("result", []):
            _offset = update["update_id"] + 1
            msg = update.get("message", {})
            if not msg:
                continue
            user_id  = str(msg.get("from", {}).get("id", ""))
            name     = msg.get("from", {}).get("first_name", "Игрок")
            username = msg.get("from", {}).get("username")
            if not user_id:
                continue
            if username:
                save_username(user_id, username)

            contact = msg.get("contact")
            if contact:
                _handle_contact(user_id, name, contact)
                continue

            text = msg.get("text", "").strip()
            if not text:
                continue
            _handle(user_id, name, text)
    except Exception as e:
        print(f"  [WARN] poll: {e}")


def _app_url(user_id=None, invite_token=None):
    base = (f"https://{RAILWAY_DOMAIN}/app" if RAILWAY_DOMAIN
            else f"http://localhost:{PORT}/app")
    params = []
    if user_id:
        params.append(f"uid={user_id}")
    if invite_token:
        params.append(f"invite={invite_token}")
    return f"{base}?{'&'.join(params)}" if params else base


def _request_phone(user_id):
    keyboard = [[{"text": "📱 Поделиться номером", "request_contact": True}]]
    tg_post(user_id, "sendMessage", **{
        "text": (
            "👋 Привет! Я бот группы <b>OZMZ Football Astana</b>\n\n"
            "Чтобы начать — поделись номером телефона (нужно для связи по играм и записи).\n\n"
            "Жми кнопку ниже 👇"
        ),
        "parse_mode": "HTML",
        "reply_markup": {"keyboard": keyboard, "resize_keyboard": True, "one_time_keyboard": True},
    })


def _handle_contact(user_id, name, contact):
    sender_id = contact.get("user_id")
    if sender_id and str(sender_id) != user_id:
        send_msg(user_id, "⚠️ Пришли, пожалуйста, свой собственный номер — через кнопку ниже.")
        _request_phone(user_id)
        return
    phone = contact.get("phone_number", "")
    save_phone(user_id, name, phone)
    # Если игрок начинал с приглашения (start=inv_...) — после регистрации
    # сразу возвращаем его в флоу занятия места.
    pending = _pending_invite.pop(user_id, None)
    _open_app(user_id, pending)


def _open_app(user_id, invite_token=None):
    if not has_phone(user_id):
        # Незарегистрированного игрока сперва просим телефон; после того как он
        # поделится контактом, _handle_contact снова позовёт _open_app. Токен
        # приглашения передаём дальше через отложенное состояние.
        if invite_token:
            _pending_invite[user_id] = invite_token
        _request_phone(user_id)
        return

    _setup_menu_button(user_id)

    # Пришёл по приглашению — ведём сразу в приложение с токеном: оно займёт
    # оплаченное место за этим игроком. Отдельная кнопка, без лишнего текста.
    if invite_token:
        app_url = _app_url(user_id, invite_token)
        keyboard = [[{"text": "🟢 Занять моё место", "web_app": {"url": app_url}}]]
        try:
            tg_post(user_id, "sendMessage", **{
                "text": ("🎟️ Тебя пригласили на игру и место уже оплачено!\n\n"
                         "Жми кнопку — займём его за тобой 👇"),
                "parse_mode": "HTML",
                "reply_markup": {"keyboard": keyboard, "resize_keyboard": True},
            })
        except Exception:
            send_msg(user_id, f"🎟️ Открой приложение, чтобы занять место: {app_url}")
        return

    role = get_role(user_id)
    if role:
        greeting = (
            f"👋 С возвращением!\n\n"
            f"🏆 Ты — <b>{role['player']}</b> ({role['category']})\n\n"
            f"Открой приложение — тест, батл с другом и не только 👇"
        )
    else:
        greeting = (
            "👋 Привет! Я бот группы <b>OZMZ Football Astana</b>\n\n"
            "Мы организуем футбольные игры в Астане 🏙️⚽\n\n"
            "Жми на кнопку — внутри тест «Кто ты из футболистов» и батл с другом 👇"
        )
    keyboard = [[{"text": "🟢 Открыть OZMZ", "web_app": {"url": _app_url(user_id)}}]]
    if user_id in ADMIN_IDS:
        admin_url = (f"https://{RAILWAY_DOMAIN}/admin?uid={user_id}" if RAILWAY_DOMAIN
                     else f"http://localhost:{PORT}/admin?uid={user_id}")
        keyboard.append([{"text": "⚙️ Создать игру (админ)", "web_app": {"url": admin_url}}])
    try:
        tg_post(user_id, "sendMessage", **{
            "text": greeting,
            "parse_mode": "HTML",
            "reply_markup": {"keyboard": keyboard, "resize_keyboard": True},
        })
    except:
        send_msg(user_id, f"👋 Открой приложение: {_app_url(user_id)}")


def _setup_menu_button(user_id=None):
    """Системная кнопка меню (слева от поля ввода). Персонализируем под чат,
    когда знаем user_id — тогда ссылка сразу содержит ?uid=."""
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/setChatMenuButton"
    payload = {
        "menu_button": {
            "type": "web_app",
            "text": "Открыть OZMZ",
            "web_app": {"url": _app_url(user_id)},
        }
    }
    if user_id:
        payload["chat_id"] = int(user_id)
    try:
        r = requests.post(url, json=payload, timeout=10)
        print(f"  [MENU BUTTON] {r.json()}")
    except Exception as e:
        print(f"  [WARN] menu button setup: {e}")


_menu_refreshed = set()  # user_id, кому уже обновили персональную Menu Button в этом запуске


def _handle(user_id, name, text):
    tl = text.lower()

    # подстраховка: если у пользователя ещё не было свежей персональной ссылки
    # в этом запуске бота — обновляем её один раз, без спама запросов на каждое сообщение
    if user_id not in _menu_refreshed and has_phone(user_id):
        _setup_menu_button(user_id)
        _menu_refreshed.add(user_id)

    # /start (в т.ч. deep-link «/start inv_<token>» из ссылки-приглашения)
    if text == "/start" or text.startswith("/start "):
        parts = text.split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        if payload.startswith("inv_"):
            _open_app(user_id, invite_token=payload[4:])
        else:
            _open_app(user_id)

    elif text in ("/help", "помощь", "help"):
        _open_app(user_id)

    # 🎯 прогноз счёта
    elif tl.startswith("/счёт") or tl.startswith("/score"):
        handle_prediction(user_id, name, text)

    # ⚽ баланс команд
    elif tl.startswith("/teams"):
        handle_teams_command(user_id, text)

    # ⚔️ батл / 🎮 тест — всё внутри единого приложения
    elif tl.startswith("/battle") or "батл" in tl or any(kw in tl for kw in ["тест", "кто я", "футболист", "/тест", "quiz"]):
        _open_app(user_id)

    # квиз — ответ (для чат-версии теста, если где-то ещё используется)
    elif user_id in quiz_sessions:
        handle_quiz_answer(user_id, text)


# ── Main ──────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    init_db()
    try:
        r = requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/deleteWebhook",
                          json={"drop_pending_updates": False}, timeout=10)
        print(f"  [WEBHOOK] delete: {r.json()}")
    except Exception as e:
        print(f"  [WARN] deleteWebhook: {e}")
    _setup_menu_button()
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
