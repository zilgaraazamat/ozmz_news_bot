"""Недельная серия (Weekly Streak) — сколько календарных недель подряд игрок
сыграл хотя бы один реально завершившийся матч.

Как и OVR (storage/ovr.py), серия НИКОГДА не хранится и не редактируется
вручную — она целиком вычисляется из дат завершившихся подтверждённых
матчей игрока (get_completed_match_dates(), storage/games.py) на каждый
запрос. Поэтому ей не нужна фоновая задача, которая бы «сбрасывала» её по
расписанию в понедельник в 00:00 — она всегда актуальна, потому что
считается заново из сырых дат каждый раз.

Неделя — понедельник-воскресенье (ISO).

Правила (как в задаче):
  - Сыграл хотя бы один завершённый матч на этой календарной неделе → серия
    за эту неделю засчитана.
  - Пропустил всю неделю целиком (ни одного завершённого матча) → серия
    сбрасывается в 0.

calculate_weekly_streak() — чистая функция (список дат → число), без
обращений к БД, поэтому её легко тестировать саму по себе. get_weekly_streak()
— тонкая обёртка, которая берёт даты из БД и передаёт их в чистую функцию.
"""
from datetime import date, timedelta

from .games import get_completed_match_dates


def _week_start(d):
    """Понедельник той недели, в которую попадает дата d (date)."""
    return d - timedelta(days=d.weekday())


def _parse_date(s):
    try:
        y, m, d = map(int, s.split("-"))
        return date(y, m, d)
    except (ValueError, AttributeError, TypeError):
        return None


def calculate_weekly_streak(match_dates, today=None):
    """Чистая функция: список дат завершившихся матчей ("YYYY-MM-DD") →
    текущая серия календарных недель подряд с хотя бы одним матчем.

    `today` — необязательный параметр для тестируемости (по умолчанию —
    реальная сегодняшняя дата).

    Логика: берём последнюю неделю, в которую был сыгран матч. Если между
    ней и текущей неделей есть хотя бы одна полностью пропущенная неделя —
    серия уже прервана, результат 0. Иначе идём назад от последней сыгранной
    недели, пока недели идут подряд без пропусков, и считаем их."""
    today = today or date.today()

    weeks_played = set()
    for s in match_dates:
        d = _parse_date(s)
        if d:
            weeks_played.add(_week_start(d))

    if not weeks_played:
        return 0

    current_week = _week_start(today)
    last_played_week = max(weeks_played)

    # Последняя неделя с игрой раньше прошлой недели → минимум одна целая
    # неделя пропущена (не считая текущую, которая ещё не закончилась) —
    # серия сброшена.
    if last_played_week < current_week - timedelta(weeks=1):
        return 0

    streak = 0
    week = last_played_week
    while week in weeks_played:
        streak += 1
        week -= timedelta(weeks=1)
    return streak


def get_weekly_streak(user_id):
    """Текущая недельная серия игрока — обёртка над calculate_weekly_streak(),
    которая сама достаёт даты завершившихся матчей из БД."""
    if not user_id:
        return 0
    return calculate_weekly_streak(get_completed_match_dates(user_id))
