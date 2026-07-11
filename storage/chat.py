"""Чат участников игры (виден только записавшимся на неё + админам)."""
from ._db import _lock, _conn

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

