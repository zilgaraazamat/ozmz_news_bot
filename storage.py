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
