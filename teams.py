import random
from storage import get_roles_bulk
from api import send_msg, from_config, tg_post

CATEGORIES = ["Атака", "Центр", "Оборона"]


def split_teams(player_ids):
    """player_ids: list[str|int] -> (team_a, team_b)
    Каждая команда — список (user_id, player, name)."""
    player_ids = [str(p) for p in player_ids]
    roles = get_roles_bulk(player_ids)

    by_cat = {c: [] for c in CATEGORIES}
    unknown = []
    for pid in player_ids:
        r = roles.get(pid)
        if not r:
            unknown.append(pid)
            continue
        by_cat.setdefault(r["category"], []).append((pid, r["player"], r["name"]))

    team_a, team_b = [], []
    for cat in by_cat:
        players = by_cat[cat]
        random.shuffle(players)
        for i, p in enumerate(players):
            (team_a if i % 2 == 0 else team_b).append(p)

    random.shuffle(unknown)
    for pid in unknown:
        target = team_a if len(team_a) <= len(team_b) else team_b
        target.append((pid, "Роль неизвестна", "Игрок"))

    return team_a, team_b


def assign_game_teams(game, signups):
    """confirmed signups (с учётом гостей) -> список команд.
    Заполняем команду до players_per_team, излишек перетекает в следующую."""
    num_teams = game.get("num_teams") or 2
    per_team = game.get("players_per_team") or 10 ** 6
    teams = [[] for _ in range(num_teams)]

    confirmed = [s for s in signups if s["status"] == "confirmed"]
    current = 0
    for s in confirmed:
        total_people = 1 + (s.get("guests_count") or 0)
        for i in range(total_people):
            while len(teams[current]) >= per_team and current < num_teams - 1:
                current += 1
            teams[current].append({
                "name": s["name"] if i == 0 else f"{s['name']} (гость {i})",
                "player": s["player"] if i == 0 else None,
                "is_guest": i > 0,
            })
    return teams


def handle_teams_command(user_id, text):
    """Формат: /teams id1 id2 id3 ..."""
    ids = [p for p in text.split()[1:] if p.isdigit()]
    if len(ids) < 2:
        send_msg(user_id, "Формат: <code>/teams id1 id2 id3 ...</code>\n"
                           "ID участников — их Telegram user_id.")
        return

    team_a, team_b = split_teams(ids)

    def fmt(team):
        return "\n".join(f"• {name} — <i>{player}</i>" for _, player, name in team) or "—"

    text_out = (
        f"⚽ <b>СОСТАВЫ КОМАНД</b>\n\n"
        f"🔴 <b>Команда А</b> ({len(team_a)})\n{fmt(team_a)}\n\n"
        f"🔵 <b>Команда Б</b> ({len(team_b)})\n{fmt(team_b)}"
    )

    chat_id = from_config("CHAT_ID")
    result = tg_post(chat_id, "sendMessage", text=text_out, parse_mode="HTML")
    if not result:
        send_msg(user_id, text_out)
