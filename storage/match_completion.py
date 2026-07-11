"""«Завершить матч» — единый флоу для админа, вместо разрозненных действий
в разных местах (отдельная кнопка «Завершить», отдельное сохранение голов,
отдельный учёт MVP). complete_match() — единственная точка входа: одним
вызовом помечает игру завершённой и сохраняет статистику каждого игрока
атомарно, одной SQLite-транзакцией.

Что происходит атомарно (внутри одной транзакции, всё или ничего):
  1. games.status = 'completed'
  2. upsert строки в match_player_stats на каждого участника (голы + MVP)

"Общее число голов" и "счётчик MVP" нигде не хранятся отдельно и поэтому
не нужно отдельно "обновлять" — это агрегаты прямо над match_player_stats
(см. get_career_totals() в match_stats.py), которые становятся верными
автоматически в тот момент, когда закоммитилась статистика по матчу.

"Игры сыграно" аналогично не хранится отдельным счётчиком — как только
матч помечен completed, get_games_played_count() (storage/games.py) сам
начинает считать его сыгранным для всех подтверждённых участников.

Прогрессия игрока (XP/уровень/OVR, storage/progression.py) — отдельная,
уже реализованная забота. Она намеренно НЕ включена в ту же SQL-транзакцию:
settle_completed_games_xp() сама использует общую блокировку (_lock) для
записи, а блокировка в этом проекте нереентерабельна — попытка захватить её
второй раз изнутри уже открытой транзакции приведёт к дедлоку. Поэтому
прогрессия начисляется сразу после коммита основной транзакции, отдельным
идемпотентным вызовом (его безопасно повторить и он не задвоит XP — см.
settle_completed_games_xp). На практике это остаётся одним пользовательским
действием «Завершить матч» и одним API-вызовом — просто под капотом это два
маленьких шага вместо одного гигантского, чтобы не рисковать дедлоком.
"""
from ._db import _lock, _conn
from .match_stats import STAT_FIELDS, _BOOL_FIELDS


def complete_match(game_id, player_stats):
    """player_stats — список {"user_id": ..., "goals": ..., "is_mvp": ...}
    (обычно один элемент на каждого подтверждённого участника матча).
    Понимает любое подмножество полей из STAT_FIELDS — так же, как
    record_match_stat() в match_stats.py; добавление новой статистики
    (assists, yellow_cards, ...) не требует правок этой функции.

    Гарантии:
      - Ровно один MVP на матч: если во входных данных is_mvp=True встретился
        у нескольких игроков, оставляем первого, у остальных сбрасываем —
        так в БД физически не может оказаться двух MVP одного матча, даже
        если что-то пошло не так на фронтенде. Это единственное поле с таким
        правилом эксклюзивности — специально прописано здесь как бизнес-логика
        задачи ("только один MVP"), а не как общее свойство всех булевых полей.
      - Числовые поля не могут быть отрицательными (не число/мусор → 0).
      - Повторный вызов для того же матча безопасен: строки апдейтятся
        (по UNIQUE(game_id, user_id)), а не дублируются.

    Возвращает нормализованный список сохранённых записей."""
    game_id = int(game_id)

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
        # "только один MVP на матч" — намеренно специфичное для is_mvp правило,
        # не распространяется автоматически на другие/будущие булевы поля.
        if entry.get("is_mvp"):
            if seen_mvp:
                entry["is_mvp"] = False
            else:
                seen_mvp = True
        normalized.append(entry)

    with _lock, _conn() as c:
        c.execute("UPDATE games SET status='completed' WHERE id=?", (game_id,))

        for p in normalized:
            fields = {k: v for k, v in p.items() if k in STAT_FIELDS}
            row = c.execute(
                "SELECT id FROM match_player_stats WHERE game_id=? AND user_id=?",
                (game_id, p["user_id"])
            ).fetchone()
            db_values = {k: (int(v) if k in _BOOL_FIELDS else v) for k, v in fields.items()}
            if row:
                if db_values:
                    set_clause = ", ".join(f"{k}=?" for k in db_values)
                    c.execute(
                        f"UPDATE match_player_stats SET {set_clause} WHERE id=?",
                        (*db_values.values(), row[0])
                    )
            else:
                columns = ["game_id", "user_id", "created_at"] + list(db_values.keys())
                placeholders = ["?", "?", "datetime('now')"] + ["?"] * len(db_values)
                c.execute(
                    f"INSERT INTO match_player_stats({', '.join(columns)}) VALUES({', '.join(placeholders)})",
                    (game_id, p["user_id"], *db_values.values())
                )

    return normalized
