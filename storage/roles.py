"""Роли игроков — результат теста «Кто ты из футболистов?» (используется /teams)."""
from ._db import _lock, _conn

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

def get_all_roles():
    with _lock, _conn() as c:
        rows = c.execute(
            "SELECT user_id, name, player, category, updated_at FROM user_roles ORDER BY updated_at DESC"
        ).fetchall()
    return [{"user_id": r[0], "name": r[1], "player": r[2], "category": r[3], "updated_at": r[4]} for r in rows]

