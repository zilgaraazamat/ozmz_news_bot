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


def normalize_player_stats(player_stats):
    """Приводит список {"user_id": ..., "goals": ..., "is_mvp": ...} (как
    угодно присланный клиентом) к безопасному виду:
      - числовые поля не могут быть отрицательными (не число/мусор → 0);
      - ровно один MVP на матч — если is_mvp=True пришёл у нескольких
        игроков, оставляем первого, у остальных сбрасываем.
    Общая точка входа и для complete_match() (storage/match_completion.py),
    и для record_match_stats_bulk() ниже — оба флоу подчиняются одним и тем
    же правилам, а не двум чуть разным копиям одной и той же проверки."""
    normalized = []
    seen_mvp = False
    for p in player_stats:
        entry = {"user_id": str(p["user_id"])}
        for f in STAT_FIELDS:
            if f not in p:
                continue
            if f in _BOOL_FIELDS:
                entry[f] = bool(p[f])
            else:
                try:
                    entry[f] = max(0, int(p[f] or 0))
                except (TypeError, ValueError):
                    entry[f] = 0
        if entry.get("is_mvp"):
            if seen_mvp:
                entry["is_mvp"] = False
            else:
                seen_mvp = True
        normalized.append(entry)
    return normalized


def record_match_stats_bulk(game_id, player_stats):
    """Сохраняет голы/MVP сразу нескольких игроков — БЕЗ завершения матча
    (в отличие от complete_match(), storage/match_completion.py). Для
    случая, когда админ отмечает голы прямо по ходу игры, ещё до того как
    она официально завершена: можно звать сколько угодно раз, каждый вызов
    просто обновляет то, что уже есть (через record_match_stat — upsert по
    UNIQUE(game_id, user_id)), никого не дублируя и не трогая games.status.
    Когда матч реально закончится, обычный "Завершить матч" подхватит уже
    сохранённые голы — их не нужно вводить заново."""
    normalized = normalize_player_stats(player_stats)
    for p in normalized:
        fields = {k: v for k, v in p.items() if k in STAT_FIELDS}
        if fields:
            record_match_stat(game_id, p["user_id"], **fields)
    return normalized


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


def get_career_totals(user_id):
    """Карьерная статистика игрока — total_goals и mvp_count намеренно НЕ
    хранятся отдельными счётчиками нигде: они вычисляются прямо из
    match_player_stats (единственного источника правды), поэтому физически
    не могут разойтись с данными по отдельным матчам. Один раз сохранил
    статистику матча (record_match_stat / complete_match) — эти цифры сразу
    актуальны, обновлять их отдельно не нужно."""
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT COUNT(*), COALESCE(SUM(goals), 0), COALESCE(SUM(is_mvp), 0) "
            "FROM match_player_stats WHERE user_id=?",
            (str(user_id),)
        ).fetchone()
    matches, total_goals, mvp_count = row
    return {"matches_recorded": matches, "total_goals": total_goals, "mvp_count": mvp_count}


def _row_to_dict(row):
    keys = ["id", "game_id", "user_id", *STAT_FIELDS, "created_at"]
    d = dict(zip(keys, row))
    for k in _BOOL_FIELDS:
        if k in d:
            d[k] = bool(d[k])
    return d
