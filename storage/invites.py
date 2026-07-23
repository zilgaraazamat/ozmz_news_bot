"""Приглашения на зарезервированные места при регистрации компании.

Когда организатор оплачивает компанию из N человек, он занимает 1 место сам,
а на остальные (N-1) мест здесь создаётся по одному приглашению с уникальным
token'ом. Ссылка t.me/<bot>?start=inv_<token> открывает Mini App и занимает
конкретное место за тем, кто её открыл (claim_invite).

Слоты нумеруются 2..N («Player 2»…«Player N»): организатор — это слот 1, на
него приглашения нет. Одно приглашение = одно место = один token; повторно
занять уже занятое место нельзя.

Занятие места НЕ создаёт новую партию в game_signups и не трогает лимит игры —
место уже оплачено и учтено в исходной партии компании (guests_count). Claim
лишь привязывает реального игрока (claimed_by) к этому месту и обновляет имя
участника в составе (game_teams), заменяя плейсхолдер «(гость N)» на игрока.
"""
import secrets
from ._db import _lock, _conn


def _now():
    return __import__("datetime").datetime.utcnow().isoformat()


def create_invites_for_signup(game_id, signup_id, inviter_id, players_count):
    """Создаёт приглашения на все НЕ-организаторские места партии компании.
    players_count — всего людей в компании (включая организатора). На места
    2..players_count заводится по приглашению. Идемпотентно: если для этой
    партии приглашения уже есть, повторно не создаёт. Возвращает список
    приглашений (см. get_invites_for_signup)."""
    players_count = int(players_count or 0)
    if players_count < 2:
        return []
    with _lock, _conn() as c:
        existing = c.execute(
            "SELECT COUNT(*) FROM game_invites WHERE signup_id=?", (signup_id,)
        ).fetchone()[0]
        if existing:
            return get_invites_for_signup(signup_id)
        for slot in range(2, players_count + 1):
            token = secrets.token_urlsafe(9)
            c.execute(
                """INSERT INTO game_invites(token, game_id, signup_id, inviter_id,
                        slot_index, claimed_by, claimed_at, created_at)
                   VALUES(?, ?, ?, ?, ?, NULL, NULL, ?)""",
                (token, game_id, signup_id, str(inviter_id) if inviter_id else None,
                 slot, _now()),
            )
    return get_invites_for_signup(signup_id)


def get_invites_for_signup(signup_id):
    """Приглашения одной партии компании, по порядку слотов."""
    with _lock, _conn() as c:
        rows = c.execute(
            """SELECT token, game_id, signup_id, inviter_id, slot_index,
                      claimed_by, claimed_at, created_at
               FROM game_invites WHERE signup_id=? ORDER BY slot_index""",
            (signup_id,),
        ).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_invite(token):
    with _lock, _conn() as c:
        row = c.execute(
            """SELECT token, game_id, signup_id, inviter_id, slot_index,
                      claimed_by, claimed_name, claimed_at, created_at
               FROM game_invites WHERE token=?""",
            (token,),
        ).fetchone()
    return _row_to_dict(row) if row else None


def claim_invite(token, user_id, display_name=None):
    """Занять место по приглашению за игроком user_id.

    display_name — как показывать игрока в составе (вместо плейсхолдера
    «(гость N)»). Может обновляться при повторном заходе того же игрока
    (например, когда имя стало известно после регистрации).

    Возвращает (ok, invite_or_reason):
      (True, invite)            — место успешно занято (или уже было занято
                                  этим же игроком — идемпотентно, имя обновится);
      (False, "not_found")      — токен не существует;
      (False, "already_claimed")— место уже занято другим игроком.
    """
    user_id = str(user_id)
    with _lock, _conn() as c:
        row = c.execute(
            "SELECT claimed_by FROM game_invites WHERE token=?", (token,)
        ).fetchone()
        if not row:
            return False, "not_found"
        claimed_by = row[0]
        if claimed_by and claimed_by != user_id:
            return False, "already_claimed"
        if not claimed_by:
            c.execute(
                """UPDATE game_invites
                   SET claimed_by=?, claimed_name=?, claimed_at=? WHERE token=?""",
                (user_id, display_name, _now(), token),
            )
        elif display_name:
            # тот же игрок зашёл повторно — обновляем только имя, если появилось
            c.execute(
                "UPDATE game_invites SET claimed_name=? WHERE token=?",
                (display_name, token),
            )
    return True, get_invite(token)


def get_claimed_slots(signup_id):
    """Занятые места партии компании: {slot_index: {"user_id","name"}} —
    для подстановки реальных игроков в состав вместо гостей-плейсхолдеров."""
    with _lock, _conn() as c:
        rows = c.execute(
            """SELECT slot_index, claimed_by, claimed_name
               FROM game_invites WHERE signup_id=? AND claimed_by IS NOT NULL""",
            (signup_id,),
        ).fetchall()
    return {r[0]: {"user_id": r[1], "name": r[2]} for r in rows}


def _row_to_dict(r):
    return {
        "token": r[0], "game_id": r[1], "signup_id": r[2], "inviter_id": r[3],
        "slot_index": r[4], "claimed_by": r[5], "claimed_name": r[6],
        "claimed_at": r[7], "created_at": r[8],
    }
