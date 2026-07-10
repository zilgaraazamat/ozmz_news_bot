import sqlite3
import threading
from config import ROLE_DB_PATH, ASTANA_TZ

_lock = threading.Lock()


def _conn():
    return sqlite3.connect(ROLE_DB_PATH, check_same_thread=False)


def init_db():
    with _lock, _conn() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS user_roles(
            user_id    TEXT PRIMARY KEY,
            name       TEXT,
            player     TEXT,
            category   TEXT,
            updated_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS quiz_history(
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            name    TEXT,
            player  TEXT,
            date    TEXT,
            user_id TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS sent_news(
            hash    TEXT PRIMARY KEY,
            sent_at TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS predict_match(
            id         INTEGER PRIMARY KEY CHECK (id = 1),
            home       TEXT,
            away       TEXT,
            time       TEXT,
            comp       TEXT,
            match_id   TEXT,
            message_id INTEGER,
            active     INTEGER
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS predict_predictions(
            user_id TEXT PRIMARY KEY,
            name    TEXT,
            score   TEXT
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS users(
            user_id   TEXT PRIMARY KEY,
            name      TEXT,
            phone     TEXT,
            nickname  TEXT,
            username  TEXT,
            joined_at TEXT
        )""")
        try:
            c.execute("ALTER TABLE users ADD COLUMN nickname TEXT")
        except sqlite3.OperationalError:
            pass  # колонка уже есть — база создана до этого обновления
        try:
            c.execute("ALTER TABLE users ADD COLUMN username TEXT")
        except sqlite3.OperationalError:
            pass

        c.execute("""CREATE TABLE IF NOT EXISTS games(
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            game_date        TEXT,
            game_time        TEXT,
            location         TEXT,
            num_players      INTEGER,
            num_teams        INTEGER,
            players_per_team INTEGER,
            price            TEXT,
            extra_info       TEXT,
            payment_link     TEXT,
            created_by       TEXT,
            created_at       TEXT,
            status           TEXT DEFAULT 'active'
        )""")
        try:
            c.execute("ALTER TABLE games ADD COLUMN payment_link TEXT")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE games ADD COLUMN image TEXT")
        except sqlite3.OperationalError:
            pass

        c.execute("""CREATE TABLE IF NOT EXISTS game_signups(
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id         INTEGER,
            user_id         TEXT,
            name            TEXT,
            player          TEXT,
            guests_count    INTEGER DEFAULT 0,
            is_addition     INTEGER DEFAULT 0,
            team_pref       INTEGER,
            payment_claimed INTEGER DEFAULT 0,
            status          TEXT DEFAULT 'pending',
            created_at      TEXT
        )""")
        # миграция со старой схемы (составной PRIMARY KEY без surrogate id — max одна запись на игрока)
        cols = [r[1] for r in c.execute("PRAGMA table_info(game_signups)").fetchall()]
        if "id" not in cols:
            c.execute("ALTER TABLE game_signups RENAME TO game_signups_old")
            c.execute("""CREATE TABLE game_signups(
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id         INTEGER,
                user_id         TEXT,
                name            TEXT,
                player          TEXT,
                guests_count    INTEGER DEFAULT 0,
                is_addition     INTEGER DEFAULT 0,
                team_pref       INTEGER,
                payment_claimed INTEGER DEFAULT 0,
                status          TEXT DEFAULT 'pending',
                created_at      TEXT
            )""")
            old_cols = [r[1] for r in c.execute("PRAGMA table_info(game_signups_old)").fetchall()]
            common = [col for col in ["game_id", "user_id", "name", "player", "guests_count",
                                       "team_pref", "payment_claimed", "status", "created_at"] if col in old_cols]
            c.execute(f"""INSERT INTO game_signups({', '.join(common)})
                          SELECT {', '.join(common)} FROM game_signups_old""")
            c.execute("DROP TABLE game_signups_old")
        try:
            c.execute("ALTER TABLE game_signups ADD COLUMN is_addition INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass

        c.execute("""CREATE TABLE IF NOT EXISTS game_slots(
            game_id    INTEGER,
            slot_index INTEGER,
            user_id    TEXT,
            name       TEXT,
            player     TEXT,
            status     TEXT DEFAULT 'free',
            claimed_at TEXT,
            PRIMARY KEY (game_id, slot_index)
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS game_teams(
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id    INTEGER,
            user_id    TEXT,
            name       TEXT,
            player     TEXT,
            team_index INTEGER,
            is_guest   INTEGER DEFAULT 0
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS game_chat(
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id    INTEGER,
            user_id    TEXT,
            name       TEXT,
            text       TEXT,
            created_at TEXT
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS announcements(
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            title      TEXT,
            text       TEXT,
            image      TEXT,
            category   TEXT DEFAULT 'Анонс',
            event_date TEXT,
            created_by TEXT,
            created_at TEXT,
            status     TEXT DEFAULT 'active'
        )""")
        for col, ddl in [("image", "TEXT"), ("category", "TEXT DEFAULT 'Анонс'"), ("event_date", "TEXT")]:
            try:
                c.execute(f"ALTER TABLE announcements ADD COLUMN {col} {ddl}")
            except sqlite3.OperationalError:
                pass


def get_role(user_id):
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT name, player, category FROM user_roles WHERE user_id=?",
            (user_id,)
        ).fetchone()
    return {"name": row[0], "player": row[1], "category": row[2]} if row else None


def set_role(user_id, name, player, category):
    user_id = str(user_id)
    with _lock, _conn() as c:
        c.execute("""INSERT INTO user_roles(user_id, name, player, category, updated_at)
                     VALUES(?, ?, ?, ?, datetime('now'))
                     ON CONFLICT(user_id) DO UPDATE SET
                        name=excluded.name,
                        player=excluded.player,
                        category=excluded.category,
                        updated_at=excluded.updated_at""",
                  (user_id, name, player, category))


def get_roles_bulk(user_ids):
    user_ids = [str(u) for u in user_ids]
    if not user_ids:
        return {}
    placeholders = ",".join("?" * len(user_ids))
    with _lock, _conn() as c:
        rows = c.execute(
            f"SELECT user_id, name, player, category FROM user_roles WHERE user_id IN ({placeholders})",
            user_ids
        ).fetchall()
    return {r[0]: {"name": r[1], "player": r[2], "category": r[3]} for r in rows}


# ── Quiz history ──────────────────────────────────────────────────────────────

def add_quiz_history(name, player, date, user_id):
    with _lock, _conn() as c:
        c.execute("INSERT INTO quiz_history(name, player, date, user_id) VALUES(?, ?, ?, ?)",
                   (name, player, date, str(user_id)))


def get_quiz_history():
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT name, player, date, user_id FROM quiz_history ORDER BY id"
        ).fetchall()
    return [{"name": r[0], "player": r[1], "date": r[2], "user_id": r[3]} for r in rows]


# ── News dedup ────────────────────────────────────────────────────────────────

def is_news_sent(hash_):
    with _lock, _conn() as c:
        row = c.execute("SELECT 1 FROM sent_news WHERE hash=?", (hash_,)).fetchone()
    return row is not None


def mark_news_sent(hashes):
    if not hashes:
        return
    with _lock, _conn() as c:
        c.executemany(
            "INSERT OR IGNORE INTO sent_news(hash, sent_at) VALUES(?, datetime('now'))",
            [(h,) for h in hashes]
        )


# ── Prediction contest ───────────────────────────────────────────────────────

def save_predict_match(match, message_id=None, active=True):
    with _lock, _conn() as c:
        c.execute("""INSERT INTO predict_match(id, home, away, time, comp, match_id, message_id, active)
                     VALUES(1, ?, ?, ?, ?, ?, ?, ?)
                     ON CONFLICT(id) DO UPDATE SET
                        home=excluded.home, away=excluded.away, time=excluded.time,
                        comp=excluded.comp, match_id=excluded.match_id,
                        message_id=excluded.message_id, active=excluded.active""",
                  (match["home"], match["away"], match["time"], match.get("comp", ""),
                   str(match.get("match_id", "")), message_id, int(active)))


def set_predict_message_id(message_id):
    with _lock, _conn() as c:
        c.execute("UPDATE predict_match SET message_id=? WHERE id=1", (message_id,))


def set_predict_active(active):
    with _lock, _conn() as c:
        c.execute("UPDATE predict_match SET active=? WHERE id=1", (int(active),))


def get_predict_match():
    """-> (match_dict|None, active: bool, message_id)"""
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT home, away, time, comp, match_id, message_id, active FROM predict_match WHERE id=1"
        ).fetchone()
    if not row:
        return None, False, None
    match = {"home": row[0], "away": row[1], "time": row[2], "comp": row[3], "match_id": row[4]}
    return match, bool(row[6]), row[5]


def add_prediction(user_id, name, score):
    with _lock, _conn() as c:
        c.execute("""INSERT INTO predict_predictions(user_id, name, score) VALUES(?, ?, ?)
                     ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, score=excluded.score""",
                  (str(user_id), name, score))


def get_predictions():
    with _lock, _conn() as c:
        rows = c.execute("SELECT user_id, name, score FROM predict_predictions").fetchall()
    return {r[0]: {"name": r[1], "score": r[2]} for r in rows}


def clear_predictions():
    with _lock, _conn() as c:
        c.execute("DELETE FROM predict_predictions")


# ── Авторизация по номеру телефона ───────────────────────────────────────────

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
            "SELECT name, nickname, phone, username FROM users WHERE user_id=?", (user_id,)
        ).fetchone()
    if not row:
        return None
    return {"name": row[0], "nickname": row[1], "phone": row[2], "username": row[3]}


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


MATCH_DURATION_HOURS = 2  # стандартная продолжительность матча, если админ не отметил игру завершённой вручную


def _match_end_datetime(game):
    """Расчётное время окончания матча = дата+время начала + стандартная длительность.
    None, если дату/время не удаётся разобрать — тогда матч не считается завершённым автоматически."""
    import re
    from datetime import datetime, timedelta
    d = (game.get("date") or "").strip()
    t = (game.get("time") or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})$", t)
    hh, mm = (int(m.group(1)), int(m.group(2))) if m else (23, 59)  # время не указано — считаем на конец дня
    try:
        start = datetime.strptime(d, "%Y-%m-%d").replace(hour=hh, minute=mm)
    except Exception:
        return None
    return start + timedelta(hours=MATCH_DURATION_HOURS)


def is_match_completed(game):
    """Матч считается завершённым, только если:
    — админ явно отметил его завершённым (status='completed'), ИЛИ
    — расчётное время окончания (начало + стандартная длительность) уже наступило.
    Отменённые игры никогда не засчитываются. Игра НЕ считается завершённой сразу
    после регистрации/подтверждения игрока — только когда матч реально прошёл."""
    from datetime import datetime
    if game.get("status") == "completed":
        return True
    if game.get("status") != "active":
        return False
    end_dt = _match_end_datetime(game)
    if end_dt is None:
        return False
    now = datetime.now(ASTANA_TZ).replace(tzinfo=None)
    return now >= end_dt


def mark_game_completed(game_id):
    """Админ вручную отмечает матч завершённым — сразу засчитывает игру всем
    подтверждённым игрокам, не дожидаясь расчётного времени окончания."""
    with _lock, _conn() as c:
        c.execute("UPDATE games SET status='completed' WHERE id=?", (game_id,))


def get_games_played_count(user_id):
    """Считает матчи, которые реально завершились (см. is_match_completed) и в которых
    у игрока была подтверждённая регистрация, не отменённая им до начала игры.
    Один матч — максимум +1, даже если у игрока несколько записей на него (напр. основная + доп. игроки)."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        rows = c.execute("""
            SELECT DISTINCT g.id, g.game_date, g.game_time, g.status FROM game_signups s
            JOIN games g ON g.id = s.game_id
            WHERE s.user_id=? AND s.status='confirmed'
        """, (user_id,)).fetchall()

    count = 0
    for game_id, d, t, status in rows:
        if is_match_completed({"date": d, "time": t, "status": status}):
            count += 1
    return count


def get_leaderboard_most_games(limit=5):
    """Топ игроков по числу реально завершённых матчей — тот же принцип, что и
    get_games_played_count, сразу для всех игроков. Дедуплицирует по game_id, чтобы
    несколько записей одного игрока на один и тот же матч не считались как несколько игр."""
    with _lock, _conn() as c:
        rows = c.execute("""
            SELECT DISTINCT s.user_id, g.id, g.game_date, g.game_time, g.status FROM game_signups s
            JOIN games g ON g.id = s.game_id
            WHERE s.status='confirmed' AND s.user_id IS NOT NULL AND s.user_id != ''
        """).fetchall()

    counts = {}
    for user_id, game_id, d, t, status in rows:
        if is_match_completed({"date": d, "time": t, "status": status}):
            counts[user_id] = counts.get(user_id, 0) + 1

    if not counts:
        return []

    with _lock, _conn() as c:
        placeholders = ",".join("?" for _ in counts)
        profile_rows = c.execute(
            f"SELECT user_id, name, nickname, username FROM users WHERE user_id IN ({placeholders})",
            list(counts.keys())
        ).fetchall()
    profiles = {r[0]: {"name": r[1], "nickname": r[2], "username": r[3]} for r in profile_rows}

    board = []
    for user_id, count in counts.items():
        display = display_name_from_profile(profiles.get(user_id))
        board.append({"user_id": user_id, "name": display, "count": count})

    board.sort(key=lambda x: -x["count"])
    return board[:limit]



def set_nickname(user_id, nickname):
    user_id = str(user_id)
    with _lock, _conn() as c:
        c.execute("""INSERT INTO users(user_id, nickname, joined_at)
                     VALUES(?, ?, datetime('now'))
                     ON CONFLICT(user_id) DO UPDATE SET nickname=excluded.nickname""",
                  (user_id, nickname))


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


def get_all_roles():
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT user_id, name, player, category, updated_at FROM user_roles ORDER BY updated_at DESC"
        ).fetchall()
    return [{"user_id": r[0], "name": r[1], "player": r[2], "category": r[3], "updated_at": r[4]} for r in rows]


# ── Игры ──────────────────────────────────────────────────────────────────────

def create_game(game_date, game_time, location, num_players, num_teams,
                 players_per_team, price, extra_info, created_by, payment_link=None, image=None):
    with _lock, _conn() as c:
        cur = c.execute("""INSERT INTO games(
                game_date, game_time, location, num_players, num_teams,
                players_per_team, price, extra_info, payment_link, image, created_by, created_at, status
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 'active')""",
            (game_date, game_time, location, num_players, num_teams,
             players_per_team, price, extra_info, payment_link, image, str(created_by)))
        return cur.lastrowid


def get_all_games():
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, game_date, game_time, location, num_players, num_teams,
                                    players_per_team, price, extra_info, payment_link, image,
                                    created_by, created_at, status
                             FROM games ORDER BY id DESC""").fetchall()
    keys = ["id", "date", "time", "location", "num_players", "num_teams",
            "players_per_team", "price", "extra_info", "payment_link", "image", "created_by", "created_at", "status"]
    return [dict(zip(keys, r)) for r in rows]


def cancel_game(game_id):
    """Помечает игру отменённой — исчезает из активных списков, но остаётся в истории."""
    with _lock, _conn() as c:
        c.execute("UPDATE games SET status='cancelled' WHERE id=?", (game_id,))


def delete_game(game_id):
    """Полностью удаляет игру и все связанные записи (регистрации, команды, чат, слоты)."""
    with _lock, _conn() as c:
        c.execute("DELETE FROM games WHERE id=?", (game_id,))
        c.execute("DELETE FROM game_signups WHERE game_id=?", (game_id,))
        c.execute("DELETE FROM game_teams WHERE game_id=?", (game_id,))
        c.execute("DELETE FROM game_chat WHERE game_id=?", (game_id,))
        c.execute("DELETE FROM game_slots WHERE game_id=?", (game_id,))


def get_active_games():
    """Только будущие активные игры, отсортированные по ближайшей дате/времени."""
    import re
    from datetime import datetime
    try:
        now_key = datetime.now().strftime("%Y-%m-%d %H:%M")
    except Exception:
        now_key = ""

    games = [g for g in get_all_games() if g["status"] == "active"]
    iso_date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def sort_key(g):
        d = (g["date"] or "9999-99-99").strip()
        t = (g["time"] or "99:99").strip()
        return f"{d} {t}"

    def is_upcoming(g):
        d = (g["date"] or "").strip()
        if not iso_date_re.match(d):
            return True  # старый формат даты (не ISO) — не фильтруем, чтобы не потерять игру
        return sort_key(g) >= now_key

    upcoming = [g for g in games if is_upcoming(g)]
    upcoming.sort(key=sort_key)
    return upcoming


def get_history_games(user_id):
    """Прошедшие игры, реально завершившиеся (см. is_match_completed), в которых
    пользователь был зарегистрирован — для вкладки «История»."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        rows = c.execute("SELECT DISTINCT game_id FROM game_signups WHERE user_id=?", (user_id,)).fetchall()
    my_game_ids = {r[0] for r in rows}
    if not my_game_ids:
        return []

    games = [g for g in get_all_games() if g["id"] in my_game_ids and g["status"] in ("active", "completed")]

    def sort_key(g):
        d = (g["date"] or "0000-00-00").strip()
        t = (g["time"] or "00:00").strip()
        return f"{d} {t}"

    past = [g for g in games if is_match_completed(g)]
    past.sort(key=sort_key, reverse=True)
    return past


def get_game(game_id):
    with _lock, _conn() as c:
        row = c.execute("""SELECT id, game_date, game_time, location, num_players, num_teams,
                                   players_per_team, price, extra_info, payment_link, image,
                                   created_by, created_at, status
                            FROM games WHERE id=?""", (game_id,)).fetchone()
    if not row:
        return None
    keys = ["id", "date", "time", "location", "num_players", "num_teams",
            "players_per_team", "price", "extra_info", "payment_link", "image", "created_by", "created_at", "status"]
    return dict(zip(keys, row))


# ── Записи на игры ────────────────────────────────────────────────────────────

def signup_for_game(game_id, user_id, name, player, guests_count=0, team_pref=None, is_addition=False):
    """Каждый вызов создаёт НОВУЮ партию регистрации — можно регистрироваться
    повторно на одну и ту же игру, и каждая партия проходит оплату/подтверждение отдельно."""
    user_id = str(user_id)
    guests_count = max(0, int(guests_count or 0))
    with _lock, _conn() as c:
        c.execute("""INSERT INTO game_signups(game_id, user_id, name, player, guests_count,
                        is_addition, team_pref, payment_claimed, status, created_at)
                     VALUES(?, ?, ?, ?, ?, ?, ?, 0, 'pending', datetime('now'))""",
                  (game_id, user_id, name, player, guests_count, int(is_addition), team_pref))


def get_signups(game_id):
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, user_id, name, player, guests_count, is_addition, team_pref,
                                    payment_claimed, status, created_at
                             FROM game_signups WHERE game_id=? ORDER BY created_at""",
                          (game_id,)).fetchall()
    return [{"id": r[0], "user_id": r[1], "name": r[2], "player": r[3], "guests_count": r[4] or 0,
              "is_addition": bool(r[5]), "team_pref": r[6], "payment_claimed": bool(r[7]),
              "status": r[8], "created_at": r[9]} for r in rows]


def get_my_signups(game_id, user_id):
    """Все партии регистрации конкретного игрока на эту игру (может быть несколько)."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, guests_count, is_addition, payment_claimed, status, created_at
                             FROM game_signups WHERE game_id=? AND user_id=? ORDER BY created_at""",
                          (game_id, user_id)).fetchall()
    return [{"id": r[0], "guests_count": r[1] or 0, "is_addition": bool(r[2]),
             "payment_claimed": bool(r[3]), "status": r[4], "created_at": r[5]} for r in rows]


def mark_payment_claimed(entry_id):
    with _lock, _conn() as c:
        c.execute("UPDATE game_signups SET payment_claimed=1 WHERE id=?", (entry_id,))


def get_my_signup(game_id, user_id):
    """Обратная совместимость: агрегированный статус (confirmed, если есть хоть одна
    подтверждённая партия; иначе pending, если есть хоть одна; иначе None)."""
    my = get_my_signups(game_id, user_id)
    if any(s["status"] == "confirmed" for s in my):
        return "confirmed"
    if my:
        return "pending"
    return None


def cancel_signup(entry_id, user_id):
    """Игрок сам отменяет конкретную партию — можно и после подтверждения
    (предупреждение о невозврате денег — на фронте), НО только пока матч ещё не завершился.
    После завершения матча регистрация становится частью истории/статистики — отмена
    задним числом больше не должна её стирать. Возвращает True при успешной отмене,
    False если отменять уже нельзя (запись не найдена или матч уже завершён)."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT game_id FROM game_signups WHERE id=? AND user_id=?", (entry_id, user_id)
        ).fetchone()
    if not row:
        return False

    game = get_game(row[0])
    if game and is_match_completed(game):
        return False  # матч уже завершён — запись зафиксирована, отмена не выполняется

    with _lock, _conn() as c:
        c.execute("DELETE FROM game_signups WHERE id=? AND user_id=?", (entry_id, user_id))
    return True


def confirm_signup(entry_id):
    with _lock, _conn() as c:
        c.execute("UPDATE game_signups SET status='confirmed' WHERE id=?", (entry_id,))


# ── Слоты игры ────────────────────────────────────────────────────────────────

def get_team_members(game_id):
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, user_id, name, player, team_index, is_guest
                             FROM game_teams WHERE game_id=? ORDER BY team_index, id""",
                          (game_id,)).fetchall()
    return [{"id": r[0], "user_id": r[1], "name": r[2], "player": r[3],
             "team_index": r[4], "is_guest": bool(r[5])} for r in rows]


def clear_game_teams(game_id):
    with _lock, _conn() as c:
        c.execute("DELETE FROM game_teams WHERE game_id=?", (game_id,))


def add_team_member(game_id, user_id, name, player, team_index, is_guest):
    with _lock, _conn() as c:
        c.execute("""INSERT INTO game_teams(game_id, user_id, name, player, team_index, is_guest)
                     VALUES(?, ?, ?, ?, ?, ?)""",
                  (game_id, str(user_id) if user_id else None, name, player, team_index, int(is_guest)))


def move_team_member(member_id, new_team_index):
    with _lock, _conn() as c:
        c.execute("UPDATE game_teams SET team_index=? WHERE id=?", (new_team_index, member_id))


# ── Чат участников игры ──────────────────────────────────────────────────────

def is_registered_for_game(game_id, user_id):
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute("SELECT 1 FROM game_signups WHERE game_id=? AND user_id=?",
                         (game_id, user_id)).fetchone()
    return row is not None


def add_chat_message(game_id, user_id, name, text):
    with _lock, _conn() as c:
        c.execute("""INSERT INTO game_chat(game_id, user_id, name, text, created_at)
                     VALUES(?, ?, ?, ?, datetime('now'))""",
                  (game_id, str(user_id), name, text[:500]))


def get_chat_messages(game_id, since_id=0):
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, user_id, name, text, created_at
                             FROM game_chat WHERE game_id=? AND id > ? ORDER BY id""",
                          (game_id, since_id or 0)).fetchall()
    return [{"id": r[0], "user_id": r[1], "name": r[2], "text": r[3], "created_at": r[4]} for r in rows]


# ── Анонсы/новости от админа ──────────────────────────────────────────────────

def create_announcement(title, text, created_by, image=None, category=None, event_date=None):
    with _lock, _conn() as c:
        cur = c.execute("""INSERT INTO announcements(title, text, image, category, event_date,
                               created_by, created_at, status)
                           VALUES(?, ?, ?, ?, ?, ?, datetime('now'), 'active')""",
                        (title, text, image, category or "Анонс", event_date, str(created_by)))
        return cur.lastrowid


def get_active_announcements(limit=10):
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, title, text, image, category, event_date, created_at
                             FROM announcements WHERE status='active' ORDER BY id DESC LIMIT ?""",
                          (limit,)).fetchall()
    return [{"id": r[0], "title": r[1], "text": r[2], "image": r[3], "category": r[4],
             "event_date": r[5], "created_at": r[6]} for r in rows]


def get_all_announcements():
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, title, text, image, category, event_date, created_at, status
                             FROM announcements ORDER BY id DESC""").fetchall()
    return [{"id": r[0], "title": r[1], "text": r[2], "image": r[3], "category": r[4],
             "event_date": r[5], "created_at": r[6], "status": r[7]} for r in rows]


def delete_announcement(announcement_id):
    with _lock, _conn() as c:
        c.execute("DELETE FROM announcements WHERE id=?", (announcement_id,))

