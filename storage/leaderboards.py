"""Лидерборды — топ игроков по категориям.

Единственный источник данных — Player Statistics service
(get_players_stats_bulk(), storage/player_stats.py). Здесь нет своей
агрегирующей SQL: лидерборд — это сортировка уже готовых чисел
(games_played/goals/mvp_count/ovr), которые сервис статистики и так
собирает для профиля, публичной страницы игрока и админки. Цифра «10
голов» в лидерборде и в профиле физически не может разойтись — она берётся
из одного и того же места.

Как добавить новую категорию лидерборда в будущем (например, по ассистам,
когда они появятся в Player Statistics service): дописать одну запись в
CATEGORIES ниже — с ключом статистики, который уже отдаёт get_player_stats().
Ни сортировку, ни загрузку данных трогать не придётся.
"""
from .users import get_all_users, display_name_from_profile
from .player_stats import get_players_stats_bulk

# Категории лидерборда: URL/API-ключ → как называется, какой значок, и какое
# поле из ответа get_player_stats() по нему сортируем.
CATEGORIES = {
    "games": {"label": "Больше всех игр",   "icon": "🏟", "stat_key": "games_played"},
    "goals": {"label": "Лучшие бомбардиры", "icon": "⚽", "stat_key": "goals"},
    "mvp":   {"label": "Лидеры по MVP",     "icon": "👑", "stat_key": "mvp_count"},
    "ovr":   {"label": "Самый высокий OVR", "icon": "⭐", "stat_key": "ovr"},
}


def get_leaderboard(category, limit=10):
    """Топ `limit` игроков по одной из CATEGORIES, отсортированных по
    убыванию значения. Показывает только реально играющих игроков (у кого
    games_played > 0) — иначе, например, лидерборд по OVR был бы забит
    людьми, которые просто открывали бота, но никогда не играли (у них
    тоже есть «базовый» OVR 60).

    Все цифры получены из ОДНОГО вызова get_players_stats_bulk() —
    единственного источника, который использует эта функция."""
    if category not in CATEGORIES:
        return []
    stat_key = CATEGORIES[category]["stat_key"]

    users = get_all_users()
    stats_by_id = get_players_stats_bulk([u["user_id"] for u in users])

    board = []
    for u in users:
        stats = stats_by_id.get(str(u["user_id"]))
        if not stats or stats["games_played"] <= 0:
            continue
        board.append({
            "user_id": u["user_id"],
            "name": display_name_from_profile(u),
            "value": stats[stat_key],
        })

    board.sort(key=lambda x: -x["value"])
    return board[:limit]
