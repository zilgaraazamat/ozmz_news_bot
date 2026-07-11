"""Достижения игрока.

Используют исключительно данные Player Statistics service
(get_player_stats(), storage/player_stats.py) — здесь нет отдельного счёта
игр/голов/MVP/серии. Достижение — это просто порог над одним из полей,
которые сервис статистики и так считает; сам факт разблокировки не хранится
нигде отдельно и пересчитывается заново на каждый запрос из текущей
статистики — как и OVR (storage/ovr.py), и недельная серия (storage/streak.py).

Из этого следует один осознанный нюанс: достижение «Серия 5 недель»
показывает разблокировку, пока у игрока СЕЙЧАС серия ≥5 недель — пропустит
неделю, серия (а вместе с ней и это достижение) сбросится, как и сам
показатель. Постоянные «однажды заработанные и навсегда сохранённые» бейджи
— это уже другая модель данных (нужно было бы отдельно хранить факт и дату
разблокировки), которая дублировала бы уже существующую статистику. Раз
задача — не дублировать логику статистики, разблокировка здесь всегда
отражает текущее состояние, а не историю.

Как добавить новое достижение в будущем: дописать одну запись в ACHIEVEMENTS
ниже — id, название, иконка, поле из get_player_stats() и порог. Больше
ничего менять не нужно — и полный список, и сводка (разблокировано/всего)
подхватят его сами.
"""
from .player_stats import get_player_stats

ACHIEVEMENTS = [
    {"id": "first_match", "label": "Первый матч",    "icon": "⚽", "stat_key": "games_played",  "threshold": 1},
    {"id": "matches_10",  "label": "10 матчей",       "icon": "🏟", "stat_key": "games_played",  "threshold": 10},
    {"id": "matches_50",  "label": "50 матчей",       "icon": "🏟", "stat_key": "games_played",  "threshold": 50},
    {"id": "first_goal",  "label": "Первый гол",      "icon": "🥅", "stat_key": "goals",         "threshold": 1},
    {"id": "goals_25",    "label": "25 голов",        "icon": "⚽", "stat_key": "goals",         "threshold": 25},
    {"id": "first_mvp",   "label": "Первый MVP",      "icon": "👑", "stat_key": "mvp_count",     "threshold": 1},
    {"id": "mvp_10",      "label": "10 наград MVP",   "icon": "👑", "stat_key": "mvp_count",     "threshold": 10},
    {"id": "streak_5",    "label": "Серия 5 недель",  "icon": "🔥", "stat_key": "weekly_streak", "threshold": 5},
]


def calculate_achievements(stats):
    """Чистая функция: словарь статистики (в форме get_player_stats()) →
    список достижений с прогрессом. Не обращается к БД — легко тестировать
    и переиспользовать в любом месте, где статистика уже под рукой."""
    result = []
    for a in ACHIEVEMENTS:
        threshold = a["threshold"]
        value = stats.get(a["stat_key"]) or 0
        unlocked = value >= threshold
        progress_pct = 100 if unlocked else (min(100, round(value / threshold * 100)) if threshold else 100)
        result.append({
            "id": a["id"],
            "label": a["label"],
            "icon": a["icon"],
            "stat_key": a["stat_key"],
            "threshold": threshold,
            "current_value": value,
            "unlocked": unlocked,
            "progress_pct": progress_pct,
        })
    return result


def get_player_achievements(user_id):
    """Достижения игрока — тонкая обёртка: берёт статистику из
    get_player_stats() (единственный источник) и отдаёт её в чистую
    calculate_achievements()."""
    return calculate_achievements(get_player_stats(user_id))


def get_achievements_summary(user_id):
    """Короткая сводка — сколько достижений разблокировано из скольких
    всего. Для бейджа/счётчика в UI без обхода полного списка на фронтенде."""
    achievements = get_player_achievements(user_id)
    unlocked = sum(1 for a in achievements if a["unlocked"])
    return {"unlocked": unlocked, "total": len(achievements)}
