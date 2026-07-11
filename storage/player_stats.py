"""Единый сервис статистики игрока — сыгранные игры, голы, MVP, OVR.

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
    — единственного источника правды по статистике матчей.
  - ovr считается тут же из этих трёх чисел через calculate_ovr()
    (storage/ovr.py) — чистая функция, ничего не хранит.
Ни одна из этих цифр не хранится отдельно и не пересчитывается заново в
других местах — этот модуль просто сводит их в одну структуру с понятными
именами.

Как добавить новую цифру в сервис в будущем (например, assists_total, если
в match_stats.py появится поле assists): дописать её в get_player_stats()
и, если нужно, в get_players_stats_bulk() — это единственное место, которое
понадобится тронуть. Экраны продолжат просто читать словарь.
"""
from .games import get_games_played_count
from .match_stats import get_career_totals
from .ovr import calculate_ovr


def get_player_stats(user_id):
    """Статистика одного игрока — единая точка входа для любого экрана,
    которому нужны games_played / goals / mvp_count / ovr.

        {"games_played": 12, "goals": 7, "mvp_count": 2, "ovr": 63}

    OVR здесь же, а не отдельным вызовом — он чистая функция ровно от этих
    трёх чисел (см. storage/ovr.py), пересчитывается заново на каждый вызов
    и никогда не хранится, так что не может разойтись с ними."""
    career = get_career_totals(user_id)
    games_played = get_games_played_count(user_id)
    goals = career["total_goals"]
    mvp_count = career["mvp_count"]
    return {
        "games_played": games_played,
        "goals": goals,
        "mvp_count": mvp_count,
        "ovr": calculate_ovr(games_played, goals, mvp_count),
    }


def get_players_stats_bulk(user_ids):
    """То же самое сразу для нескольких игроков — {user_id: stats}.
    Использует ту же get_player_stats() для каждого, чтобы бизнес-логика
    жила ровно в одном месте — это про то, ГДЕ считается статистика, а не
    про то, сколько запросов к БД для этого нужно."""
    return {str(uid): get_player_stats(uid) for uid in user_ids}
