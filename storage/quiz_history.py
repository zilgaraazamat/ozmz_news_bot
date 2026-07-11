"""История прохождений квиза «Кто ты из футболистов?»."""
from ._db import _lock, _conn

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

