"""Мелкие хелперы, общие для нескольких route-модулей (не завязаны на конкретный
эндпоинт, поэтому живут отдельно, а не внутри одного из миксинов)."""
from storage import get_profile, get_game, get_signups, clear_game_teams, add_team_member
from teams import auto_assign_teams


def _display_name(user_id):
    profile = get_profile(user_id)
    if profile and profile.get("nickname"):
        return profile["nickname"]
    if profile and profile.get("name"):
        return profile["name"]
    return "Игрок"


def _recompute_teams(game_id):
    """Автоматически пересчитывает и сохраняет распределение по командам
    сразу при любой записи/отмене — без ручного запуска админом."""
    game = get_game(game_id)
    if not game:
        return
    signups = get_signups(game_id)
    teams = auto_assign_teams(game, signups)
    clear_game_teams(game_id)
    for team_idx, members in enumerate(teams):
        for m in members:
            add_team_member(game_id, m["user_id"], m["name"], m["player"], team_idx, m["is_guest"])
