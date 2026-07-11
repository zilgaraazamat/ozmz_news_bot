"""Шаблоны игр — сохраняют повторяющиеся настройки игры (поле, адрес, цена,
состав, оплата, описание, фото), чтобы админ не вводил их заново каждый раз —
при создании игры выбирается шаблон, и остаётся проверить только дату/время."""
from ._db import _lock, _conn

_TEMPLATE_KEYS = ["id", "name", "field", "address", "default_time", "price", "max_players",
                  "duration", "description", "payment_link", "image", "created_by", "created_at", "updated_at"]
_TEMPLATE_SELECT = """SELECT id, name, field, address, default_time, price, max_players,
                              duration, description, payment_link, image, created_by, created_at, updated_at
                       FROM game_templates"""


def create_game_template(name, field, address, default_time, price, max_players,
                          duration, description, payment_link, image, created_by):
    with _lock, _conn() as c:
        cur = c.execute("""INSERT INTO game_templates(
                name, field, address, default_time, price, max_players, duration,
                description, payment_link, image, created_by, created_at, updated_at
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""",
            (name, field, address, default_time, price, max_players, duration,
             description, payment_link, image, str(created_by)))
        return cur.lastrowid


def get_game_templates():
    with _lock, _conn() as c:
        rows = c.execute(f"{_TEMPLATE_SELECT} ORDER BY id DESC").fetchall()
    return [dict(zip(_TEMPLATE_KEYS, r)) for r in rows]


def get_game_template(template_id):
    with _lock, _conn() as c:
        row = c.execute(f"{_TEMPLATE_SELECT} WHERE id=?", (template_id,)).fetchone()
    if not row:
        return None
    return dict(zip(_TEMPLATE_KEYS, row))


def update_game_template(template_id, name, field, address, default_time, price,
                          max_players, duration, description, payment_link, image):
    with _lock, _conn() as c:
        c.execute("""UPDATE game_templates SET
                name=?, field=?, address=?, default_time=?, price=?, max_players=?, duration=?,
                description=?, payment_link=?, image=?, updated_at=datetime('now')
            WHERE id=?""",
            (name, field, address, default_time, price, max_players, duration,
             description, payment_link, image, template_id))


def delete_game_template(template_id):
    with _lock, _conn() as c:
        c.execute("DELETE FROM game_templates WHERE id=?", (template_id,))

