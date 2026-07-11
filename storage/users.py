"""Профиль игрока: телефонная авторизация, ник, юзернейм, номер футболки,
и единая логика отображаемого имени по всему приложению."""
from ._db import _lock, _conn

def has_phone(user_id):
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute("SELECT phone FROM users WHERE user_id=?", (user_id,)).fetchone()
    return bool(row and row[0])


def save_phone(user_id, name, phone):
    user_id = str(user_id)
    with _lock, _conn() as c:
        c.execute("""INSERT INTO users(user_id, name, phone, joined_at)
                     VALUES(?, ?, ?, datetime('now'))
                     ON CONFLICT(user_id) DO UPDATE SET
                        name=excluded.name, phone=excluded.phone""",
                  (user_id, name, phone))


def get_user(user_id):
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT name, phone, joined_at FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
    return {"name": row[0], "phone": row[1], "joined_at": row[2]} if row else None


def get_all_users():
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT user_id, name, phone, nickname, username, joined_at FROM users ORDER BY joined_at DESC"
        ).fetchall()
    return [{"user_id": r[0], "name": r[1], "phone": r[2], "nickname": r[3],
             "username": r[4], "joined_at": r[5]} for r in rows]


def get_profile(user_id):
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT name, nickname, phone, username, jersey_number FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
    if not row:
        return None
    return {"name": row[0], "nickname": row[1], "phone": row[2], "username": row[3], "jersey_number": row[4]}


def display_name_from_profile(profile):
    """Единая логика отображаемого имени — везде в приложении. Приоритет:
    личный ник, заданный в приложении → юзернейм из Telegram (@...) → имя из
    Telegram (first_name) → «Игрок». Всё в итоге опирается на реальные данные
    Telegram — «name» берётся из Telegram при первом заходе, «username» —
    актуальный @ник, который обновляется на каждом сообщении боту."""
    if not profile:
        return "Игрок"
    nickname = (profile.get("nickname") or "").strip()
    if nickname:
        return nickname
    username = (profile.get("username") or "").strip()
    if username:
        return f"@{username}"
    name = (profile.get("name") or "").strip()
    if name:
        return name
    return "Игрок"


def get_display_name(user_id):
    return display_name_from_profile(get_profile(user_id))

def set_nickname(user_id, nickname):
    user_id = str(user_id)
    with _lock, _conn() as c:
        c.execute("""INSERT INTO users(user_id, nickname, joined_at)
                     VALUES(?, ?, datetime('now'))
                     ON CONFLICT(user_id) DO UPDATE SET nickname=excluded.nickname""",
                  (user_id, nickname))


def set_jersey_number(user_id, jersey_number):
    """Номер на футболке — от 0 до 99, не обязан быть уникальным среди игроков."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        c.execute("""INSERT INTO users(user_id, jersey_number, joined_at)
                     VALUES(?, ?, datetime('now'))
                     ON CONFLICT(user_id) DO UPDATE SET jersey_number=excluded.jersey_number""",
                  (user_id, jersey_number))


def save_username(user_id, username):
    """Кэшируем @username из Telegram — обновляем на каждом сообщении, т.к. юзер может сменить."""
    user_id = str(user_id)
    if not username:
        return
    with _lock, _conn() as c:
        c.execute("""INSERT INTO users(user_id, username, joined_at)
                     VALUES(?, ?, datetime('now'))
                     ON CONFLICT(user_id) DO UPDATE SET username=excluded.username""",
                  (user_id, username))


def get_username(user_id):
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute("SELECT username FROM users WHERE user_id=?", (user_id,)).fetchone()
    return row[0] if row else None

