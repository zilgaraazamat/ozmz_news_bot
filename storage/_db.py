"""Общее подключение к SQLite и создание/миграция схемы БД.

Все остальные модули storage/* используют `_lock` и `_conn()` отсюда для
доступа к базе — единая точка правды о том, как открывается соединение.
`init_db()` создаёт/мигрирует ВСЕ таблицы за один вызов (как и раньше, до
разбиения storage.py на модули) — порядок и содержимое SQL не менялись.
"""
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
        try:
            c.execute("ALTER TABLE users ADD COLUMN jersey_number INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            # Прогрессия игрока — уровень/опыт/рейтинг. Новые игроки стартуют с
            # Level 1 / XP 0 / OVR 60 (см. DEFAULT_LEVEL/DEFAULT_XP/DEFAULT_OVR ниже).
            c.execute("ALTER TABLE users ADD COLUMN level INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN xp INTEGER")
        except sqlite3.OperationalError:
            pass
        try:
            c.execute("ALTER TABLE users ADD COLUMN ovr INTEGER")
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

        c.execute("""CREATE TABLE IF NOT EXISTS game_templates(
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            name         TEXT,
            field        TEXT,
            address      TEXT,
            default_time TEXT,
            price        TEXT,
            max_players  INTEGER,
            duration     INTEGER,
            description  TEXT,
            payment_link TEXT,
            image        TEXT,
            created_by   TEXT,
            created_at   TEXT,
            updated_at   TEXT
        )""")
        # Примеры шаблонов при самом первом запуске — чтобы раздел не выглядел
        # пустым и админ сразу видел, как это работает. Только если шаблонов
        # ещё вообще не было (не подставляем повторно, если админ их удалил).
        if c.execute("SELECT COUNT(*) FROM game_templates").fetchone()[0] == 0:
            c.executemany("""INSERT INTO game_templates(
                    name, field, address, default_time, price, max_players, duration,
                    description, payment_link, image, created_by, created_at, updated_at
                ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), datetime('now'))""", [
                ("Monday Football 21:00",    None, None, "21:00", None, None, None, None, None, None, "system"),
                ("Wednesday Football 20:00", None, None, "20:00", None, None, None, None, None, None, "system"),
                ("Friday Football 22:00",    None, None, "22:00", None, None, None, None, None, None, "system"),
            ])

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
        try:
            # Флаг: опыт за эту запись (завершённую подтверждённую игру) уже начислен —
            # чтобы settle_completed_games_xp() не начисляла его повторно при каждом вызове.
            c.execute("ALTER TABLE game_signups ADD COLUMN xp_awarded INTEGER DEFAULT 0")
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

