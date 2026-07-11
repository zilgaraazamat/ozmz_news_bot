"""Логика «матч реально завершился?» — общий низкоуровневый модуль без
зависимостей от остальных storage/*, чтобы его могли использовать и games.py
(get_games_played_count, leaderboard, get_history_games), и progression.py
(settle_completed_games_xp), и signups.py (cancel_signup), не создавая
циклических импортов друг с другом."""
from config import ASTANA_TZ

MATCH_DURATION_HOURS = 2  # стандартная продолжительность матча, если админ не отметил игру завершённой вручную


def _match_end_datetime(game):
    """Расчётное время окончания матча = дата+время начала + стандартная длительность.
    None, если дату/время не удаётся разобрать — тогда матч не считается завершённым автоматически."""
    import re
    from datetime import datetime, timedelta
    d = (game.get("date") or "").strip()
    t = (game.get("time") or "").strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", d):
        return None
    m = re.match(r"^(\d{1,2}):(\d{2})$", t)
    hh, mm = (int(m.group(1)), int(m.group(2))) if m else (23, 59)  # время не указано — считаем на конец дня
    try:
        start = datetime.strptime(d, "%Y-%m-%d").replace(hour=hh, minute=mm)
    except Exception:
        return None
    return start + timedelta(hours=MATCH_DURATION_HOURS)


def is_match_completed(game):
    """Матч считается завершённым, только если:
    — админ явно отметил его завершённым (status='completed'), ИЛИ
    — расчётное время окончания (начало + стандартная длительность) уже наступило.
    Отменённые игры никогда не засчитываются. Игра НЕ считается завершённой сразу
    после регистрации/подтверждения игрока — только когда матч реально прошёл."""
    from datetime import datetime
    if game.get("status") == "completed":
        return True
    if game.get("status") != "active":
        return False
    end_dt = _match_end_datetime(game)
    if end_dt is None:
        return False
    now = datetime.now(ASTANA_TZ).replace(tzinfo=None)
    return now >= end_dt

