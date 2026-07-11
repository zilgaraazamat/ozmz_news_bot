"""Распределение игроков по командам для конкретной игры."""
from ._db import _lock, _conn

def get_team_members(game_id):
    with _lock, _conn() as c:
        rows = c.execute("""SELECT id, user_id, name, player, team_index, is_guest
                             FROM game_teams WHERE game_id=? ORDER BY team_index, id""",
                          (game_id,)).fetchall()
    return [{"id": r[0], "user_id": r[1], "name": r[2], "player": r[3],
             "team_index": r[4], "is_guest": bool(r[5])} for r in rows]


def clear_game_teams(game_id):
    with _lock, _conn() as c:
        c.execute("DELETE FROM game_teams WHERE game_id=?", (game_id,))


def add_team_member(game_id, user_id, name, player, team_index, is_guest):
    with _lock, _conn() as c:
        c.execute("""INSERT INTO game_teams(game_id, user_id, name, player, team_index, is_guest)
                     VALUES(?, ?, ?, ?, ?, ?)""",
                  (game_id, str(user_id) if user_id else None, name, player, team_index, int(is_guest)))


def move_team_member(member_id, new_team_index):
    with _lock, _conn() as c:
        c.execute("UPDATE game_teams SET team_index=? WHERE id=?", (new_team_index, member_id))

