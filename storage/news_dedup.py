"""Дедупликация уже отправленных новостей (чтобы не постить одно и то же дважды)."""
from ._db import _lock, _conn

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

