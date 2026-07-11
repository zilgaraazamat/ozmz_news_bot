"""Статистика игроков по завершённым матчам — единый источник правды для
футбольной статистики (голы, MVP и всё, что добавится позже: передачи,
жёлтые/красные карточки и т.д.).

Одна строка в match_player_stats = один игрок в одном матче:
    user_id, game_id, goals, is_mvp, created_at

Это только хранилище — модуль не вызывается ни из одного существующего
эндпоинта или экрана. UI и бизнес-логика (например, автоматическая запись
статистики при завершении матча) сюда сознательно не подключены — это
следующий шаг, отдельный от создания самого модуля.

Как добавить новый тип статистики (например, assists) в будущем:
    1. Добавить колонку в CREATE TABLE match_player_stats (storage/_db.py):
       ALTER TABLE match_player_stats ADD COLUMN assists INTEGER DEFAULT 0
    2. Дописать "assists" в STAT_FIELDS ниже.
Всё остальное — record_match_stat/get_match_stats/... — начнёт понимать
новое поле автоматически, менять их не нужно.
"""
from ._db import _lock, _conn

# Единственное место, которое нужно трогать, чтобы научить этот модуль новому
# типу статистики (после того как для него добавлена колонка в БД — см.
# инструкцию в докстринге выше). Порядок влияет только на порядок колонок
# в SELECT ниже, значения не важны.
STAT_FIELDS = ("goals", "is_mvp")

# Поля, которые по смыслу булевы (0/1 в SQLite) и должны отдаваться как bool.
_BOOL_FIELDS = {"is_mvp"}


def record_match_stat(game_id, user_id, **stats):
    """Создаёт или обновляет статистику игрока в конкретном матче.

    Принимает любое подмножество полей из STAT_FIELDS как именованные
    аргументы, например:
        record_match_stat(game_id, user_id, goals=2)
        record_match_stat(game_id, user_id, is_mvp=True)
        record_match_stat(game_id, user_id, goals=1, is_mvp=True)

    Не переданные поля не трогаются при обновлении уже существующей строки —
    можно вызывать по одному событию за раз (гол за голом), не перезаписывая
    уже сохранённые данные. При первом вызове для пары (game_id, user_id)
    создаёт строку; непереданные поля получают дефолт из схемы (0 / NULL).

    Любые ключи вне STAT_FIELDS молча игнорируются — опечатка в вызывающем
    коде не уронит вызов и не попадёт в базу в непредусмотренную колонку."""
    game_id = int(game_id)
    user_id = str(user_id)
    fields = {k: v for k, v in stats.items() if k in STAT_FIELDS}
    for k in _BOOL_FIELDS & fields.keys():
        fields[k] = int(bool(fields[k]))

    with _lock, _conn() as c:
        row = c.execute(
            "SELECT id FROM match_player_stats WHERE game_id=? AND user_id=?",
            (game_id, user_id)
        ).fetchone()

        if row:
            if fields:
                set_clause = ", ".join(f"{k}=?" for k in fields)
                c.execute(
                    f"UPDATE match_player_stats SET {set_clause} WHERE id=?",
                    (*fields.values(), row[0])
                )
            return row[0]

        columns = ["game_id", "user_id", "created_at"] + list(fields.keys())
        placeholders = ["?", "?", "datetime('now')"] + ["?"] * len(fields)
        cur = c.execute(
            f"INSERT INTO match_player_stats({', '.join(columns)}) VALUES({', '.join(placeholders)})",
            (game_id, user_id, *fields.values())
        )
        return cur.lastrowid


def get_match_stats(game_id):
    """Статистика всех игроков конкретного матча, отсортированная по
    порядку добавления."""
    with _lock, _conn() as c:
        rows = c.execute(
            f"SELECT id, game_id, user_id, {', '.join(STAT_FIELDS)}, created_at "
            f"FROM match_player_stats WHERE game_id=? ORDER BY id",
            (int(game_id),)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_player_match_stats(user_id):
    """Статистика конкретного игрока по всем матчам, в которых она есть."""
    with _lock, _conn() as c:
        rows = c.execute(
            f"SELECT id, game_id, user_id, {', '.join(STAT_FIELDS)}, created_at "
            f"FROM match_player_stats WHERE user_id=? ORDER BY id",
            (str(user_id),)
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_player_stat_in_match(game_id, user_id):
    """Статистика одного игрока в одном матче, либо None, если для него
    ещё не было ни одной записи."""
    with _lock, _conn() as c:
        row = c.execute(
            f"SELECT id, game_id, user_id, {', '.join(STAT_FIELDS)}, created_at "
            f"FROM match_player_stats WHERE game_id=? AND user_id=?",
            (int(game_id), str(user_id))
        ).fetchone()
    return _row_to_dict(row) if row else None


def delete_match_stats(game_id):
    """Удаляет всю статистику матча. Не вызывается автоматически из
    delete_game() — оставлено на будущее подключение, чтобы не менять
    существующую бизнес-логику в рамках этой задачи."""
    with _lock, _conn() as c:
        c.execute("DELETE FROM match_player_stats WHERE game_id=?", (int(game_id),))


def _row_to_dict(row):
    keys = ["id", "game_id", "user_id", *STAT_FIELDS, "created_at"]
    d = dict(zip(keys, row))
    for k in _BOOL_FIELDS:
        if k in d:
            d[k] = bool(d[k])
    return d
