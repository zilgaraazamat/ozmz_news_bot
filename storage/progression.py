"""Прогрессия игрока: Level / XP / OVR.

Единая переиспользуемая система для всех будущих механик, которые должны
влиять на уровень игрока (сейчас — завершённые игры, позже — что угодно
ещё: квизы, баттлы, достижения и т.д.). Всё, что нужно новой механике —
вызвать award_xp(user_id, amount, reason). Всё остальное (левел-апы,
рост OVR, хранение) обрабатывается здесь в одном месте.

Новый игрок стартует с Level 1 / XP 0 / OVR 60.
Каждый следующий уровень требует больше опыта, чем предыдущий.
При левел-апе OVR растёт на +1 за каждый пройденный уровень.
"""
from ._db import _lock, _conn
from .game_status import is_match_completed

DEFAULT_LEVEL = 1
DEFAULT_XP = 0
DEFAULT_OVR = 60
XP_PER_COMPLETED_GAME = 100


def xp_required_for_level(level):
    """Сколько опыта нужно набрать, чтобы перейти с `level` на `level + 1`.
    Растущая кривая — каждый следующий уровень требует больше опыта, чем
    предыдущий (100, 150, 200, 250, ...). Меняется только эта функция, если
    понадобится другая кривая прогрессии — вся остальная система не тронется."""
    level = max(1, int(level or 1))
    return 100 + (level - 1) * 50


def _progression_row(c, user_id):
    row = c.execute("SELECT level, xp, ovr FROM users WHERE user_id=?", (str(user_id),)).fetchone()
    if not row:
        return DEFAULT_LEVEL, DEFAULT_XP, DEFAULT_OVR
    level = row[0] if row[0] is not None else DEFAULT_LEVEL
    xp    = row[1] if row[1] is not None else DEFAULT_XP
    ovr   = row[2] if row[2] is not None else DEFAULT_OVR
    return level, xp, ovr


def get_progression(user_id):
    """Текущие Level/XP/OVR игрока + прогресс до следующего уровня. Всегда
    возвращает валидные данные — даже для игрока, которого ещё нет в базе
    (новый игрок = дефолты Level 1 / XP 0 / OVR 60), и даже если user_id
    не передан (гость без Telegram ID)."""
    if not user_id:
        needed = xp_required_for_level(DEFAULT_LEVEL)
        return {
            "level": DEFAULT_LEVEL, "xp": DEFAULT_XP, "ovr": DEFAULT_OVR,
            "xp_for_next_level": needed, "xp_progress_pct": 0,
        }
    with _lock, _conn() as c:
        level, xp, ovr = _progression_row(c, user_id)
    needed = xp_required_for_level(level)
    return {
        "level": level,
        "xp": xp,
        "ovr": ovr,
        "xp_for_next_level": needed,
        "xp_progress_pct": min(100, round(xp / needed * 100)) if needed else 100,
    }


def award_xp(user_id, amount, reason=None):
    """Единая точка начисления опыта — переиспользуется любой механикой,
    которая должна давать XP (сейчас: завершённые игры). Пересчитывает
    уровень и увеличивает OVR на +1 за каждый пройденный уровень.
    Возвращает итоговое состояние и сколько уровней игрок прошёл за этот
    вызов — вызывающий код может использовать это, например, для
    уведомления «Новый уровень!»."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        c.execute("""INSERT INTO users(user_id, level, xp, ovr, joined_at)
                     VALUES(?, ?, ?, ?, datetime('now'))
                     ON CONFLICT(user_id) DO NOTHING""",
                  (user_id, DEFAULT_LEVEL, DEFAULT_XP, DEFAULT_OVR))

        level, xp, ovr = _progression_row(c, user_id)
        xp += max(0, int(amount or 0))

        levels_gained = 0
        needed = xp_required_for_level(level)
        while xp >= needed:
            xp -= needed
            level += 1
            ovr += 1
            levels_gained += 1
            needed = xp_required_for_level(level)

        c.execute("UPDATE users SET level=?, xp=?, ovr=? WHERE user_id=?", (level, xp, ovr, user_id))

    return {
        "level": level,
        "xp": xp,
        "ovr": ovr,
        "leveled_up": levels_gained > 0,
        "levels_gained": levels_gained,
        "xp_for_next_level": xp_required_for_level(level),
        "reason": reason,
    }


def settle_completed_games_xp(user_id):
    """Идемпотентно начисляет +100 XP за каждую завершённую подтверждённую
    игру этого игрока, за которую опыт ещё не был начислен — ровно один раз
    за игру, даже если у игрока несколько записей на неё (основная запись +
    доп. игроки). Безопасно вызывать многократно (например, при каждом
    открытии профиля) — уже засчитанные игры не начисляются повторно.
    Возвращает результат последнего начисления (для показа левел-апа) или
    None, если начислять было нечего."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        rows = c.execute("""
            SELECT s.id, s.xp_awarded, g.id, g.game_date, g.game_time, g.status
            FROM game_signups s JOIN games g ON g.id = s.game_id
            WHERE s.user_id=? AND s.status='confirmed'
        """, (user_id,)).fetchall()

    by_game = {}
    for signup_id, xp_awarded, game_id, d, t, status in rows:
        info = by_game.setdefault(game_id, {"signup_ids": [], "awarded": False, "date": d, "time": t, "status": status})
        info["signup_ids"].append(signup_id)
        if xp_awarded:
            info["awarded"] = True

    last_result = None
    for game_id, info in by_game.items():
        if info["awarded"]:
            continue
        if not is_match_completed({"date": info["date"], "time": info["time"], "status": info["status"]}):
            continue
        last_result = award_xp(user_id, XP_PER_COMPLETED_GAME, reason="game_completed")
        with _lock, _conn() as c:
            c.executemany("UPDATE game_signups SET xp_awarded=1 WHERE id=?",
                           [(sid,) for sid in info["signup_ids"]])
    return last_result

