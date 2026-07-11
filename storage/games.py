"""CRUD и запросы по играм: создание, список, история, статистика посещаемости,
завершение матчей."""
from ._db import _lock, _conn
from .game_status import is_match_completed
from .progression import settle_completed_games_xp

def mark_game_completed(game_id):
    """Админ вручную отмечает матч завершённым — сразу засчитывает игру всем
    подтверждённым игрокам, не дожидаясь расчётного времени окончания.
    Заодно сразу начисляет им +100 XP за игру (settle_completed_games_xp
    и так сработала бы лениво при следующем открытии профиля — но так
    игрок получает прогресс сразу, а не при следующем визите)."""
    with _lock, _conn() as c:
        c.execute("UPDATE games SET status='completed' WHERE id=?", (game_id,))
        user_ids = [r[0] for r in c.execute(
            """SELECT DISTINCT user_id FROM game_signups
               WHERE game_id=? AND status='confirmed' AND user_id IS NOT NULL AND user_id != ''""",
            (game_id,)
        ).fetchall()]
    for uid in user_ids:
        settle_completed_games_xp(uid)


def _get_completed_confirmed_games(user_id):
    """Общий helper: подтверждённые записи пользователя на РЕАЛЬНО завершившиеся
    матчи (см. is_match_completed), без дублей на один и тот же матч (даже если
    у игрока несколько записей на него — основная + доп. игроки). Используется
    и для подсчёта количества игр, и для расчёта дат (см. get_completed_match_dates,
    storage/streak.py) — чтобы фильтр «что считается сыгранной игрой» жил
    в одном месте и не разошёлся между двумя похожими подсчётами."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        rows = c.execute("""
            SELECT DISTINCT g.id, g.game_date, g.game_time, g.status FROM game_signups s
            JOIN games g ON g.id = s.game_id
            WHERE s.user_id=? AND s.status='confirmed'
        """, (user_id,)).fetchall()

    completed = []
    for game_id, d, t, status in rows:
        game = {"id": game_id, "date": d, "time": t, "status": status}
        if is_match_completed(game):
            completed.append(game)
    return completed


def get_games_played_count(user_id):
    """Считает матчи, которые реально завершились (см. is_match_completed) и в которых
    у игрока была подтверждённая регистрация, не отменённая им до начала игры.
    Один матч — максимум +1, даже если у игрока несколько записей на него (напр. основная + доп. игроки)."""
    return len(_get_completed_confirmed_games(user_id))


def get_completed_match_dates(user_id):
    """Даты (строки "YYYY-MM-DD") реально завершившихся подтверждённых матчей
    игрока — сырые данные для любых расчётов по календарным периодам
    (сейчас: недельная серия, storage/streak.py). Тот же набор игр, что
    считает get_games_played_count — просто отдаёт даты, а не количество."""
    return [g["date"] for g in _get_completed_confirmed_games(user_id) if g["date"]]


def create_game(game_date, game_time, location, num_players, num_teams,
                 players_per_team, price, extra_info, created_by, payment_link=None, image=None):
    with _lock, _conn() as c:
        cur = c.execute("""INSERT INTO games(
                game_date, game_time, location, num_players, num_teams,
                players_per_team, price, extra_info, payment_link, image, created_by, created_at, status
            ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'), 'active')""",
            (game_date, game_time, location, num_players, num_teams,
             players_per_team, price, extra_info, payment_link, image, str(created_by)))
        return cur.lastrowid


def get_all_games():
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, game_date, game_time, location, num_players, num_teams,
                                    players_per_team, price, extra_info, payment_link, image,
                                    created_by, created_at, status
                             FROM games ORDER BY id DESC""").fetchall()
    keys = ["id", "date", "time", "location", "num_players", "num_teams",
            "players_per_team", "price", "extra_info", "payment_link", "image", "created_by", "created_at", "status"]
    return [dict(zip(keys, r)) for r in rows]


def cancel_game(game_id):
    """Помечает игру отменённой — исчезает из активных списков, но остаётся в истории."""
    with _lock, _conn() as c:
        c.execute("UPDATE games SET status='cancelled' WHERE id=?", (game_id,))


def delete_game(game_id):
    """Полностью удаляет игру и все связанные записи (регистрации, команды, чат, слоты)."""
    with _lock, _conn() as c:
        c.execute("DELETE FROM games WHERE id=?", (game_id,))
        c.execute("DELETE FROM game_signups WHERE game_id=?", (game_id,))
        c.execute("DELETE FROM game_teams WHERE game_id=?", (game_id,))
        c.execute("DELETE FROM game_chat WHERE game_id=?", (game_id,))
        c.execute("DELETE FROM game_slots WHERE game_id=?", (game_id,))


def get_active_games():
    """Только будущие активные игры, отсортированные по ближайшей дате/времени."""
    import re
    from datetime import datetime
    try:
        now_key = datetime.now().strftime("%Y-%m-%d %H:%M")
    except Exception:
        now_key = ""

    games = [g for g in get_all_games() if g["status"] == "active"]
    iso_date_re = re.compile(r"^\d{4}-\d{2}-\d{2}$")

    def sort_key(g):
        d = (g["date"] or "9999-99-99").strip()
        t = (g["time"] or "99:99").strip()
        return f"{d} {t}"

    def is_upcoming(g):
        d = (g["date"] or "").strip()
        if not iso_date_re.match(d):
            return True  # старый формат даты (не ISO) — не фильтруем, чтобы не потерять игру
        return sort_key(g) >= now_key

    upcoming = [g for g in games if is_upcoming(g)]
    upcoming.sort(key=sort_key)
    return upcoming


def get_history_games(user_id):
    """Прошедшие игры, реально завершившиеся (см. is_match_completed), в которых
    пользователь был зарегистрирован — для вкладки «История»."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        rows = c.execute("SELECT DISTINCT game_id FROM game_signups WHERE user_id=?", (user_id,)).fetchall()
    my_game_ids = {r[0] for r in rows}
    if not my_game_ids:
        return []

    games = [g for g in get_all_games() if g["id"] in my_game_ids and g["status"] in ("active", "completed")]

    def sort_key(g):
        d = (g["date"] or "0000-00-00").strip()
        t = (g["time"] or "00:00").strip()
        return f"{d} {t}"

    past = [g for g in games if is_match_completed(g)]
    past.sort(key=sort_key, reverse=True)
    return past


def get_game(game_id):
    with _lock, _conn() as c:
        row = c.execute("""SELECT id, game_date, game_time, location, num_players, num_teams,
                                   players_per_team, price, extra_info, payment_link, image,
                                   created_by, created_at, status
                            FROM games WHERE id=?""", (game_id,)).fetchone()
    if not row:
        return None
    keys = ["id", "date", "time", "location", "num_players", "num_teams",
            "players_per_team", "price", "extra_info", "payment_link", "image", "created_by", "created_at", "status"]
    return dict(zip(keys, row))

