import sqlite3
import threading
from config import ROLE_DB_PATH

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
            created_by       TEXT,
            created_at       TEXT,
            status           TEXT DEFAULT 'active'
        )""")

        c.execute("""CREATE TABLE IF NOT EXISTS game_signups(
            game_id      INTEGER,
            user_id      TEXT,
            name         TEXT,
            player       TEXT,
            guests_count INTEGER DEFAULT 0,
            status       TEXT DEFAULT 'pending',
            created_at   TEXT,
            PRIMARY KEY (game_id, user_id)
        )""")
        try:
            c.execute("ALTER TABLE game_signups ADD COLUMN guests_count INTEGER DEFAULT 0")
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
                 players_per_team, price, extra_info, created_by):
    with _lock, _conn() as c:
        cur = c.execute("""INSERT INTO games(
                game_date, game_time, location, num_players, num_teams,
                players_per_team, price, extra_info, created_by, created_at, status
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 'active')""",
            (game_date, game_time, location, num_players, num_teams,
             players_per_team, price, extra_info, str(created_by)))
        return cur.lastrowid


def get_all_games():
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, game_date, game_time, location, num_players, num_teams,
                                    players_per_team, price, extra_info, created_by, created_at, status
                             FROM games ORDER BY id DESC""").fetchall()
    keys = ["id", "date", "time", "location", "num_players", "num_teams",
            "players_per_team", "price", "extra_info", "created_by", "created_at", "status"]
    return [dict(zip(keys, r)) for r in rows]


def get_active_games():
    return [g for g in get_all_games() if g["status"] == "active"]


def get_game(game_id):
    with _lock, _conn() as c:
        row = c.execute("""SELECT id, game_date, game_time, location, num_players, num_teams,
                                   players_per_team, price, extra_info, created_by, created_at, status
                            FROM games WHERE id=?""", (game_id,)).fetchone()
    if not row:
        return None
    keys = ["id", "date", "time", "location", "num_players", "num_teams",
            "players_per_team", "price", "extra_info", "created_by", "created_at", "status"]
    return dict(zip(keys, row))


# ── Записи на игры ────────────────────────────────────────────────────────────

def signup_for_game(game_id, user_id, name, player, guests_count=0):
    user_id = str(user_id)
    guests_count = max(0, int(guests_count or 0))
    with _lock, _conn() as c:
        c.execute("""INSERT INTO game_signups(game_id, user_id, name, player, guests_count, status, created_at)
                     VALUES(?, ?, ?, ?, ?, 'pending', datetime('now'))
                     ON CONFLICT(game_id, user_id) DO UPDATE SET
                        name=excluded.name, player=excluded.player, guests_count=excluded.guests_count""",
                  (game_id, user_id, name, player, guests_count))


def get_signups(game_id):
    with _lock, _conn() as c:
        rows = c.execute("""SELECT user_id, name, player, guests_count, status, created_at
                             FROM game_signups WHERE game_id=? ORDER BY created_at""",
                          (game_id,)).fetchall()
    return [{"user_id": r[0], "name": r[1], "player": r[2], "guests_count": r[3] or 0,
              "status": r[4], "created_at": r[5]} for r in rows]


def get_my_signup(game_id, user_id):
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute("""SELECT status FROM game_signups WHERE game_id=? AND user_id=?""",
                         (game_id, user_id)).fetchone()
    return row[0] if row else None


def confirm_signup(game_id, user_id):
    user_id = str(user_id)
    with _lock, _conn() as c:
        c.execute("UPDATE game_signups SET status='confirmed' WHERE game_id=? AND user_id=?",
                  (game_id, user_id))


# ── Слоты игры ────────────────────────────────────────────────────────────────

def init_game_slots(game_id, num_players):
    """Создаёт num_players пустых слотов при создании игры."""
    if not num_players:
        return
    with _lock, _conn() as c:
        for i in range(1, int(num_players) + 1):
            c.execute("""INSERT OR IGNORE INTO game_slots(game_id, slot_index, status)
                         VALUES(?, ?, 'free')""", (game_id, i))


def get_slots(game_id):
    with _lock, _conn() as c:
        rows = c.execute("""SELECT slot_index, user_id, name, player, status, claimed_at
                             FROM game_slots WHERE game_id=? ORDER BY slot_index""",
                          (game_id,)).fetchall()
    return [{"slot_index": r[0], "user_id": r[1], "name": r[2], "player": r[3],
             "status": r[4], "claimed_at": r[5]} for r in rows]


def claim_slot(game_id, slot_index, user_id, name, player):
    """Занять свободный слот. Один и тот же user_id может занимать сколько угодно
    разных слотов — повторная регистрация не запрещена."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute("SELECT user_id FROM game_slots WHERE game_id=? AND slot_index=?",
                         (game_id, slot_index)).fetchone()
        if row is None:
            return "not_found"
        if row[0]:
            return "taken"
        c.execute("""UPDATE game_slots SET user_id=?, name=?, player=?, status='pending', claimed_at=datetime('now')
                     WHERE game_id=? AND slot_index=?""",
                  (user_id, name, player, game_id, slot_index))
    return None


def release_slot(game_id, slot_index, user_id=None):
    """user_id задан — самостоятельный выход (проверяем владение).
    user_id=None — админ освобождает слот принудительно."""
    with _lock, _conn() as c:
        if user_id is not None:
            row = c.execute("SELECT user_id FROM game_slots WHERE game_id=? AND slot_index=?",
                             (game_id, slot_index)).fetchone()
            if not row or row[0] != str(user_id):
                return "not_owner"
        c.execute("""UPDATE game_slots SET user_id=NULL, name=NULL, player=NULL,
                        status='free', claimed_at=NULL
                     WHERE game_id=? AND slot_index=?""", (game_id, slot_index))
    return None


def confirm_slot(game_id, slot_index):
    with _lock, _conn() as c:
        c.execute("UPDATE game_slots SET status='confirmed' WHERE game_id=? AND slot_index=?",
                  (game_id, slot_index))


def admin_move_slot(game_id, from_index, to_index):
    """Админ перемещает занявшего слот человека в другой свободный слот."""
    with _lock, _conn() as c:
        src = c.execute("SELECT user_id, name, player, status FROM game_slots WHERE game_id=? AND slot_index=?",
                         (game_id, from_index)).fetchone()
        if not src or not src[0]:
            return "empty_source"
        dst = c.execute("SELECT user_id FROM game_slots WHERE game_id=? AND slot_index=?",
                         (game_id, to_index)).fetchone()
        if dst is None:
            return "not_found"
        if dst[0]:
            return "taken"
        c.execute("""UPDATE game_slots SET user_id=?, name=?, player=?, status=?, claimed_at=datetime('now')
                     WHERE game_id=? AND slot_index=?""",
                  (src[0], src[1], src[2], src[3], game_id, to_index))
        c.execute("""UPDATE game_slots SET user_id=NULL, name=NULL, player=NULL,
                        status='free', claimed_at=NULL
                     WHERE game_id=? AND slot_index=?""", (game_id, from_index))
    return None
