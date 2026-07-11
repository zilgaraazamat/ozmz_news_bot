"""Анонсы/новости, публикуемые админом — в группу и в приложение."""
from ._db import _lock, _conn

def create_announcement(title, text, created_by, image=None, category=None, event_date=None, published=True):
    status = "active" if published else "draft"
    with _lock, _conn() as c:
        cur = c.execute("""INSERT INTO announcements(title, text, image, category, event_date,
                               created_by, created_at, status)
                           VALUES(?, ?, ?, ?, ?, ?, datetime('now'), ?)""",
                        (title, text, image, category or "Анонс", event_date, str(created_by), status))
        return cur.lastrowid


def publish_announcement(announcement_id):
    """Публикует черновик — переводит его в статус 'active', и он сразу становится
    виден в приложении (см. get_active_announcements)."""
    with _lock, _conn() as c:
        c.execute("UPDATE announcements SET status='active' WHERE id=?", (announcement_id,))


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

