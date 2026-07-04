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


def auto_assign_teams(game, signups):
    """confirmed signups (с гостями) -> список команд.

    Приоритет — держать группу (регистрацию + гостей) целиком в одной команде.
    Группа целиком кладётся туда, где помещается (best-fit — куда влезает
    с наименьшим остатком места). Если группа целиком нигде не влезает —
    раскидываем только лишних по остальным местам, начиная с самых свободных команд.

    Возвращает список списков member-словарей:
    {"user_id", "name", "player", "is_guest"} — индекс в списке teams и есть номер команды.
    """
    num_teams = game.get("num_teams") or 2
    per_team = game.get("players_per_team") or 10 ** 9

    confirmed = [s for s in signups if s["status"] == "confirmed"]
    # сначала большие группы — так они с большей вероятностью попадут в одну команду целиком
    groups = sorted(confirmed, key=lambda s: -(1 + (s.get("guests_count") or 0)))

    teams = [[] for _ in range(num_teams)]
    capacity = [per_team] * num_teams

    for s in groups:
        size = 1 + (s.get("guests_count") or 0)
        members = [
            {
                "user_id": s["user_id"] if i == 0 else None,
                "name": s["name"] if i == 0 else f"{s['name']} (гость {i})",
                "player": s["player"] if i == 0 else None,
                "is_guest": i > 0,
            }
            for i in range(size)
        ]

        # ищем команду, куда группа влезает ЦЕЛИКОМ, с наименьшим остатком после (best-fit)
        best = None
        for i in range(num_teams):
            if capacity[i] >= size and (best is None or capacity[i] < capacity[best]):
                best = i

        if best is not None:
            teams[best].extend(members)
            capacity[best] -= size
        else:
            # группа целиком никуда не влезает — раскидываем по кусочкам,
            # начиная с команды с наибольшим свободным местом
            order = sorted(range(num_teams), key=lambda i: -capacity[i])
            idx = 0
            for i in order:
                while capacity[i] > 0 and idx < len(members):
                    teams[i].append(members[idx])
                    capacity[i] -= 1
                    idx += 1
                if idx >= len(members):
                    break

            # если мест всё равно не хватило на всех (общий перебор игроков) —
            # никого не теряем: остаток уходит в команду с наименьшим текущим составом
            while idx < len(members):
                smallest = min(range(num_teams), key=lambda i: len(teams[i]))
                teams[smallest].append(members[idx])
                capacity[smallest] -= 1
                idx += 1
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
