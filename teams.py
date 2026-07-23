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


def _build_members(s):
    if s.get("is_addition"):
        # это партия "добавить ещё игроков" к уже существующей записи — сам регистрант
        # уже учтён в основной партии, здесь все — новые люди, без дублирования "себя"
        n = max(1, int(s.get("guests_count") or 1))
        return [
            {"user_id": None, "name": f"{s['name']} (доп. игрок {i + 1})", "player": None, "is_guest": True}
            for i in range(n)
        ]

    size = 1 + (s.get("guests_count") or 0)
    # Занятые по приглашению места (slot_index -> {"user_id","name"}) —
    # подставляем реального игрока вместо плейсхолдера «(гость N)».
    # slot_index нумеруется с 2 (организатор = слот 1); i здесь 0-based,
    # поэтому место i соответствует slot_index = i + 1.
    claimed = s.get("claimed_slots") or {}
    members = []
    for i in range(size):
        if i == 0:
            members.append({"user_id": s["user_id"], "name": s["name"],
                            "player": s["player"], "is_guest": False})
            continue
        slot = i + 1
        c = claimed.get(slot)
        if c:
            members.append({"user_id": c.get("user_id"), "name": c.get("name") or f"{s['name']} (гость {i})",
                            "player": None, "is_guest": False})
        else:
            members.append({"user_id": None, "name": f"{s['name']} (гость {i})",
                            "player": None, "is_guest": True})
    return members


def _place_best_fit(members, teams, capacity, num_teams):
    """Кладёт группу целиком туда, где влезает с наименьшим остатком.
    Если целиком никуда не влезает — раскидывает по кусочкам, никого не теряя."""
    size = len(members)
    best = None
    for i in range(num_teams):
        if capacity[i] >= size and (best is None or capacity[i] < capacity[best]):
            best = i

    if best is not None:
        teams[best].extend(members)
        capacity[best] -= size
        return

    order = sorted(range(num_teams), key=lambda i: -capacity[i])
    idx = 0
    for i in order:
        while capacity[i] > 0 and idx < len(members):
            teams[i].append(members[idx])
            capacity[i] -= 1
            idx += 1
        if idx >= len(members):
            break
    while idx < len(members):
        smallest = min(range(num_teams), key=lambda i: len(teams[i]))
        teams[smallest].append(members[idx])
        idx += 1


def auto_assign_teams(game, signups):
    """Подтверждённые регистрации (с гостями) -> список команд, автоматически.

    В состав попадают ТОЛЬКО оплаченные и подтверждённые админом записи
    (status == 'confirmed'). Это касается и основных записей, и партий
    «добавить игроков»: пока оплата не подтверждена, люди в ростере не
    показываются — иначе состав наполнялся бы теми, кто ещё не заплатил.

    Группа (тот, кто регистрировался + его гости) держится вместе и кладётся
    целиком туда, где помещается с наименьшим остатком места (best-fit).
    Если группа целиком нигде не влезает — раскидываем только лишних по
    остальным местам. Никто не теряется, даже если мест физически не хватает.

    Возвращает список списков member-словарей:
    {"user_id", "name", "player", "is_guest"} — индекс в списке teams и есть номер команды.
    """
    num_teams = game.get("num_teams") or 2
    per_team = game.get("players_per_team") or 10 ** 9

    confirmed = [s for s in signups if s.get("status") == "confirmed"]
    groups = sorted(confirmed, key=lambda s: -(1 + (s.get("guests_count") or 0)))

    teams = [[] for _ in range(num_teams)]
    capacity = [per_team] * num_teams

    for s in groups:
        _place_best_fit(_build_members(s), teams, capacity, num_teams)

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
