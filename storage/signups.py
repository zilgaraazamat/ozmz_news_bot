"""Записи игроков на игры: регистрация, отмена, подтверждение оплаты."""
from ._db import _lock, _conn
from .game_status import is_match_completed
from .games import get_game

def signup_for_game(game_id, user_id, name, player, guests_count=0, team_pref=None, is_addition=False, amount=None):
    """Каждый вызов создаёт НОВУЮ партию регистрации — можно регистрироваться
    повторно на одну и ту же игру, и каждая партия проходит оплату/подтверждение отдельно.
    amount — сумма оплаты партии, посчитанная бэкендом (storage/pricing.py);
    None, если у игры нет распознаваемой цены."""
    user_id = str(user_id)
    guests_count = max(0, int(guests_count or 0))
    with _lock, _conn() as c:
        c.execute("""INSERT INTO game_signups(game_id, user_id, name, player, guests_count,
                        is_addition, team_pref, amount, payment_claimed, status, created_at)
                     VALUES(?, ?, ?, ?, ?, ?, ?, ?, 0, 'pending', datetime('now'))""",
                  (game_id, user_id, name, player, guests_count, int(is_addition), team_pref, amount))


def get_signups(game_id):
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, user_id, name, player, guests_count, is_addition, team_pref,
                                    amount, payment_claimed, status, created_at
                             FROM game_signups WHERE game_id=? ORDER BY created_at""",
                          (game_id,)).fetchall()
    return [{"id": r[0], "user_id": r[1], "name": r[2], "player": r[3], "guests_count": r[4] or 0,
              "is_addition": bool(r[5]), "team_pref": r[6], "amount": r[7],
              "payment_claimed": bool(r[8]), "status": r[9], "created_at": r[10]} for r in rows]


def get_my_signups(game_id, user_id):
    """Все партии регистрации конкретного игрока на эту игру (может быть несколько)."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, guests_count, is_addition, amount, payment_claimed, status, created_at
                             FROM game_signups WHERE game_id=? AND user_id=? ORDER BY created_at""",
                          (game_id, user_id)).fetchall()
    return [{"id": r[0], "guests_count": r[1] or 0, "is_addition": bool(r[2]), "amount": r[3],
             "payment_claimed": bool(r[4]), "status": r[5], "created_at": r[6]} for r in rows]


def mark_payment_claimed(entry_id):
    with _lock, _conn() as c:
        c.execute("UPDATE game_signups SET payment_claimed=1 WHERE id=?", (entry_id,))


def get_my_signup(game_id, user_id):
    """Обратная совместимость: агрегированный статус (confirmed, если есть хоть одна
    подтверждённая партия; иначе pending, если есть хоть одна; иначе None)."""
    my = get_my_signups(game_id, user_id)
    if any(s["status"] == "confirmed" for s in my):
        return "confirmed"
    if my:
        return "pending"
    return None


def cancel_signup(entry_id, user_id):
    """Игрок сам отменяет конкретную партию — можно и после подтверждения
    (предупреждение о невозврате денег — на фронте), НО только пока матч ещё не завершился.
    После завершения матча регистрация становится частью истории/статистики — отмена
    задним числом больше не должна её стирать. Возвращает True при успешной отмене,
    False если отменять уже нельзя (запись не найдена или матч уже завершён)."""
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT game_id FROM game_signups WHERE id=? AND user_id=?", (entry_id, user_id)
        ).fetchone()
    if not row:
        return False

    game = get_game(row[0])
    if game and is_match_completed(game):
        return False  # матч уже завершён — запись зафиксирована, отмена не выполняется

    with _lock, _conn() as c:
        c.execute("DELETE FROM game_signups WHERE id=? AND user_id=?", (entry_id, user_id))
    return True


def confirm_signup(entry_id):
    with _lock, _conn() as c:
        c.execute("UPDATE game_signups SET status='confirmed' WHERE id=?", (entry_id,))

