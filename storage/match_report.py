"""Отчёт о завершённом матче — ТОЛЬКО ЧТЕНИЕ, никакой новой бизнес-логики.

Ничего не хранит и ничего не пересчитывает "заново": просто комбинирует уже
существующие данные из трёх мест, которые прекрасно работают сами по себе
и не были и не должны быть тронуты этим модулем:
  - storage/games.py       — когда и где проходил матч (get_game)
  - storage/teams_slots.py — кто в какой команде (get_team_members),
                              заполняется автоматически при записи/отмене
                              (см. routes/helpers.py:_recompute_teams) —
                              этот модуль состав команд НЕ меняет и не
                              пересчитывает — ростер каждой команды в отчёте
                              ровно тот, с которым матч реально был сыгран
  - storage/match_stats.py — голы и MVP каждого игрока (get_match_stats),
                              заполняется через "Завершить матч"
                              (storage/match_completion.py) — этот модуль
                              статистику не меняет

Командный счёт — производная величина (сумма голов игроков команды), а НЕ
отдельно хранимое число: в схеме нет и не появляется никакого "team_score".
"""
from .games import get_game
from .game_status import is_match_completed, MATCH_DURATION_HOURS
from .teams_slots import get_team_members
from .match_stats import get_match_stats

# Циклический набор значков для команд — совпадает по духу с примером из
# ТЗ (🔵 Команда 1, ⚫ Команда 2, 🟢 Команда 3, ...). Чисто оформление,
# никак не влияет на расчёт счёта.
TEAM_DOTS = ["🔵", "⚫", "🟢", "🟡", "🟣", "🟠", "🔴", "⚪"]


def get_match_report(game_id, viewer_user_id=None):
    """Полный отчёт по завершённому матчу, либо None если:
      - матча с таким id нет, или
      - матч ещё не завершён (см. is_match_completed, storage/game_status.py)
        — отчёт по незавершённому матчу не имеет смысла показывать.

    viewer_user_id — необязательный user_id того, кто смотрит отчёт;
    используется чтобы посчитать его личный результат
    (victory/defeat/draw/None) и отметить его самого в ростере каждой
    команды (is_viewer) — больше ни на что не влияет.

    Состав команд ("teams" → "players") — ровно тот же, что уже хранится в
    game_teams (см. get_team_members выше), просто сгруппированный по
    командам и обогащённый голами/MVP. Никакая команда здесь заново не
    формируется и не меняется."""
    game = get_game(game_id)
    if not game or not is_match_completed(game):
        return None

    members = get_team_members(game_id)
    stats_rows = get_match_stats(game_id)
    goals_by_user = {s["user_id"]: s["goals"] for s in stats_rows}
    mvp_user_ids = {s["user_id"] for s in stats_rows if s["is_mvp"]}

    viewer_user_id = str(viewer_user_id) if viewer_user_id else None

    # Группируем состав "как он реально играл" по team_index — тот же набор
    # строк game_teams, что уже был бы виден в /api/admin/games, просто
    # собранный по командам, а не одним плоским списком.
    teams_by_index = {}
    for m in members:
        idx = m["team_index"]
        team = teams_by_index.setdefault(idx, {
            "team_index": idx,
            "goals": 0,
            "player_count": 0,
            "_user_ids": set(),
            "_players": [],
        })
        goals = goals_by_user.get(m["user_id"], 0) if m["user_id"] else 0
        is_mvp = bool(m["user_id"]) and m["user_id"] in mvp_user_ids

        team["player_count"] += 1
        team["_players"].append({
            "user_id": m["user_id"],
            "name": m["name"],
            "goals": goals,
            "is_mvp": is_mvp,
            "is_guest": m["is_guest"],
            "is_viewer": bool(viewer_user_id) and m["user_id"] == viewer_user_id,
        })
        if m["user_id"]:
            team["_user_ids"].add(m["user_id"])
            team["goals"] += goals

    teams = sorted(teams_by_index.values(), key=lambda t: (-t["goals"], t["team_index"]))

    max_goals = teams[0]["goals"] if teams else 0
    winners = [t for t in teams if t["goals"] == max_goals]
    is_tie = len(teams) > 0 and len(winners) != 1
    winning_team_index = winners[0]["team_index"] if (teams and not is_tie) else None

    viewer_result = None
    if viewer_user_id:
        viewer_team = next((t for t in teams if viewer_user_id in t["_user_ids"]), None)
        if viewer_team is not None:
            if is_tie:
                viewer_result = "draw"
            else:
                viewer_result = "victory" if viewer_team["team_index"] == winning_team_index else "defeat"

    teams_out = []
    for t in teams:
        # Сортировка ростера: сначала по голам (по убыванию), затем по
        # имени (по алфавиту) — ровно как в ТЗ.
        players_sorted = sorted(t["_players"], key=lambda p: (-p["goals"], (p["name"] or "").lower()))
        teams_out.append({
            "team_index": t["team_index"],
            "label": f"Команда {t['team_index'] + 1}",
            "dot": TEAM_DOTS[t["team_index"] % len(TEAM_DOTS)],
            "goals": t["goals"],
            "player_count": t["player_count"],
            "is_winner": (not is_tie) and t["team_index"] == winning_team_index,
            "players": [
                {
                    "user_id": p["user_id"],
                    "name": p["name"],
                    "goals": p["goals"],
                    "is_mvp": p["is_mvp"],
                    "is_guest": p["is_guest"],
                    "is_viewer": p["is_viewer"],
                }
                for p in players_sorted
            ],
        })

    return {
        "game_id": game["id"],
        "date": game["date"],
        "time": game["time"],
        "location": game["location"],
        "duration_hours": MATCH_DURATION_HOURS,
        "player_count": len(members),
        "teams": teams_out,
        "total_goals": sum(t["goals"] for t in teams_out),
        "is_tie": is_tie,
        "winning_team_index": winning_team_index,
        "viewer_result": viewer_result,
    }
