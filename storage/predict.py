"""Конкурс прогнозов на счёт матча."""
from ._db import _lock, _conn

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

