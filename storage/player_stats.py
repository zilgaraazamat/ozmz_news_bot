"""Единый сервис статистики игрока — сыгранные игры, голы, MVP, OVR, серия.

Это ЕДИНСТВЕННОЕ место в приложении, где эти числа собираются вместе.
Ни один экран/эндпоинт не должен считать их самостоятельно — только звать
get_player_stats() / get_players_stats_bulk() отсюда. Так статистика везде
(свой профиль, публичная страница игрока, список игроков в админке, что
угодно ещё в будущем) гарантированно согласована и меняется в одном месте.

Это модуль-композиция, а не пересчёт с нуля:
  - games_played по-прежнему считается через get_games_played_count()
    (storage/games.py) — по подтверждённым записям и факту завершения
    матча. Это верно даже для игр, завершённых старым флоу без детальной
    статистики (mark_game_completed без complete_match) — там нет строк в
    match_player_stats, но игра всё равно засчитана игроку.
  - goals и mvp_count берутся из get_career_totals() (storage/match_stats.py)
    — единственного источника правды по статистике матчей. goals в OVR не
    входит — это отдельная статистика (лидерборд, достижения).
  - tournament_wins берётся из get_tournament_win_counts() (storage/tournaments.py)
    — засчитывается капитану команды-чемпиона (см. докстринг там про то,
    почему только капитану).
  - ovr считается тут же из games_played/mvp_count/tournament_wins через
    calculate_ovr() (storage/ovr.py) — чистая функция, ничего не хранит.
  - weekly_streak считается из дат завершившихся матчей через
    get_weekly_streak() (storage/streak.py) — тоже не хранится, пересчитывается
    из тех же дат на каждый вызов.
Ни одна из этих цифр не хранится отдельно и не пересчитывается заново в
других местах — этот модуль просто сводит их в одну структуру с понятными
именами.

Как добавить новую цифру в сервис в будущем (например, assists_total, если
в match_stats.py появится поле assists): дописать её в get_player_stats()
и, если нужно, в get_players_stats_bulk() — это единственное место, которое
понадобится тронуть. Экраны продолжат просто читать словарь.
"""
from .games import get_games_played_count, get_games_played_and_dates_bulk
from .match_stats import get_career_totals, get_career_totals_bulk
from .ovr import calculate_ovr
from .streak import get_weekly_streak, calculate_weekly_streak
from .tournaments import get_tournament_win_counts


def get_player_stats(user_id):
    """Статистика одного игрока — единая точка входа для любого экрана,
    которому нужны games_played / goals / mvp_count / tournament_wins / ovr /
    weekly_streak.

        {"games_played": 12, "goals": 7, "mvp_count": 2, "tournament_wins": 1,
         "ovr": 16, "weekly_streak": 3}

    OVR и weekly_streak считаются здесь же, а не отдельными вызовами — оба
    чистые функции от данных об играх (см. storage/ovr.py, storage/streak.py),
    пересчитываются заново на каждый вызов и никогда не хранятся, так что не
    могут разойтись с реальной статистикой."""
    career = get_career_totals(user_id)
    games_played = get_games_played_count(user_id)
    goals = career["total_goals"]
    mvp_count = career["mvp_count"]
    tournament_wins = get_tournament_win_counts().get(str(user_id), 0)
    return {
        "games_played": games_played,
        "goals": goals,
        "mvp_count": mvp_count,
        "tournament_wins": tournament_wins,
        "ovr": calculate_ovr(games_played, mvp_count, tournament_wins),
        "weekly_streak": get_weekly_streak(user_id),
    }


def get_players_stats_bulk(user_ids):
    """То же самое сразу для нескольких игроков — {user_id: stats}.

    Формулы ровно те же, что и в get_player_stats() (calculate_ovr /
    calculate_weekly_streak — те же чистые функции), поэтому статистика
    считается по-прежнему в одном месте. Разница только в том, ОТКУДА
    берутся сырые числа: наивный цикл по get_player_stats() делал бы
    несколько отдельных запросов к БД на каждого игрока, а /api/games
    (главный вызывающий) опрашивается каждые несколько секунд с каждого
    открытого приложения — при десятках игроков в списке игр это превращалось
    в десятки лишних SQLite-соединений на каждый такой запрос и ощутимо
    подтормаживало приложение. Тут те же данные достаются batched-запросами
    (get_career_totals_bulk / get_games_played_and_dates_bulk) на всех
    игроков сразу, а победы в турнирах — одним общим get_tournament_win_counts()
    вместо отдельного обхода турниров на каждого игрока."""
    user_ids = [str(uid) for uid in user_ids if uid]
    if not user_ids:
        return {}
    careers = get_career_totals_bulk(user_ids)
    games = get_games_played_and_dates_bulk(user_ids)
    win_counts = get_tournament_win_counts()
    out = {}
    for uid in user_ids:
        career = careers.get(uid) or {"total_goals": 0, "mvp_count": 0}
        g = games.get(uid) or {"count": 0, "dates": []}
        tournament_wins = win_counts.get(uid, 0)
        out[uid] = {
            "games_played": g["count"],
            "goals": career["total_goals"],
            "mvp_count": career["mvp_count"],
            "tournament_wins": tournament_wins,
            "ovr": calculate_ovr(g["count"], career["mvp_count"], tournament_wins),
            "weekly_streak": calculate_weekly_streak(g["dates"]),
        }
    return out
