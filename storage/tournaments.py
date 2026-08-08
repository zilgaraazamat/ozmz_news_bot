"""Турниры: групповой этап + плей-офф.

Модель:
  tournaments             — сам турнир (привязан к новости через announcement_id)
  tournament_teams        — команды-участники (регистрирует капитан)
  tournament_team_players — состав команды
  tournament_matches      — матчи: stage='group' (с group_index) или 'playoff'
                            (с round_name: «1/4 финала», «Полуфинал», «Финал»)

Принципы те же, что и в остальном проекте:
  • оплата проходит цикл «оплатил → админ подтвердил»; в группы и таблицу
    попадают ТОЛЬКО подтверждённые команды (status='confirmed');
  • турнирная таблица нигде не хранится — она всегда вычисляется из
    сыгранных матчей (см. group_standings), поэтому не может разойтись
    с реальными результатами;
  • сумма взноса считается на бэкенде из entry_fee турнира (storage/pricing.py).
"""
from ._db import _lock, _conn
from .pricing import price_per_player

# Очки за результат в групповом этапе
_WIN, _DRAW, _LOSS = 3, 1, 0

_T_KEYS = ["id", "announcement_id", "name", "description", "location", "start_date",
           "end_date", "entry_fee", "payment_link", "max_teams", "team_size",
           "num_groups", "tournament_type", "image", "status", "created_by", "created_at"]
_T_SELECT = f"SELECT {', '.join(_T_KEYS)} FROM tournaments"

_TEAM_KEYS = ["id", "tournament_id", "captain_id", "captain_name", "name", "amount",
              "payment_claimed", "status", "group_index", "created_at"]
_TEAM_SELECT = f"SELECT {', '.join(_TEAM_KEYS)} FROM tournament_teams"

_M_KEYS = ["id", "tournament_id", "stage", "group_index", "round_name", "team_a_id",
           "team_b_id", "score_a", "score_b", "match_date", "match_time", "location",
           "status", "sort_order", "created_at"]
_M_SELECT = f"SELECT {', '.join(_M_KEYS)} FROM tournament_matches"


def entry_fee_amount(tournament):
    """Взнос за участие команды в тенге (или None, если не задан/бесплатно).
    entry_fee — свободный текст («15000 ₸»), парсится тем же способом, что и
    цена игры, чтобы формат ввода для админа был одинаковый везде."""
    return price_per_player(
        {"price": (tournament or {}).get("entry_fee")}
    )


# ── Турнир ──────────────────────────────────────────────────────────────────

def _normalize_format(tournament_type, max_teams, num_groups):
    """Формат жёстко привязан к типу турнира — не отдаём его на откуп
    произвольному вводу админа:
      - 'cup'    — ровно 2 группы по 4 команды (см. модульный докстринг);
      - 'league' — один общий круговой этап, группы не нужны, лимит команд
                   свободный («не важно сколько команд»).
    Возвращает (tournament_type, max_teams, num_groups) уже нормализованными."""
    tournament_type = tournament_type if tournament_type in ("cup", "league") else "cup"
    if tournament_type == "league":
        return tournament_type, max_teams, 1
    return tournament_type, 8, 2


def create_tournament(name, description, location, start_date, end_date, entry_fee,
                       payment_link, max_teams, team_size, num_groups, image,
                       created_by, announcement_id=None, tournament_type="cup"):
    tournament_type, max_teams, num_groups = _normalize_format(tournament_type, max_teams, num_groups)
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO tournaments(announcement_id, name, description, location,
                    start_date, end_date, entry_fee, payment_link, max_teams, team_size,
                    num_groups, tournament_type, image, status, created_by, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,'active',?,datetime('now'))""",
            (announcement_id, name, description, location, start_date, end_date,
             entry_fee, payment_link, max_teams, team_size, num_groups,
             tournament_type, image, str(created_by)))
        return cur.lastrowid


def update_tournament(tournament_id, name, description, location, start_date, end_date,
                       entry_fee, payment_link, max_teams, team_size, num_groups, image,
                       tournament_type="cup"):
    tournament_type, max_teams, num_groups = _normalize_format(tournament_type, max_teams, num_groups)
    with _lock, _conn() as c:
        c.execute(
            """UPDATE tournaments SET name=?, description=?, location=?, start_date=?,
                    end_date=?, entry_fee=?, payment_link=?, max_teams=?, team_size=?,
                    num_groups=?, tournament_type=?, image=COALESCE(?, image)
               WHERE id=?""",
            (name, description, location, start_date, end_date, entry_fee, payment_link,
             max_teams, team_size, num_groups, tournament_type, image, tournament_id))


def get_tournaments(only_active=False):
    q = _T_SELECT + (" WHERE status='active'" if only_active else "") + " ORDER BY id DESC"
    with _lock, _conn() as c:
        rows = c.execute(q).fetchall()
    return [dict(zip(_T_KEYS, r)) for r in rows]


def get_tournament(tournament_id):
    with _lock, _conn() as c:
        row = c.execute(f"{_T_SELECT} WHERE id=?", (tournament_id,)).fetchone()
    return dict(zip(_T_KEYS, row)) if row else None


def delete_tournament(tournament_id):
    """Удаляет турнир вместе со всем содержимым — иначе остались бы висячие
    команды и матчи, на которые уже никто не ссылается."""
    with _lock, _conn() as c:
        team_ids = [r[0] for r in c.execute(
            "SELECT id FROM tournament_teams WHERE tournament_id=?", (tournament_id,)).fetchall()]
        for tid in team_ids:
            c.execute("DELETE FROM tournament_team_players WHERE team_id=?", (tid,))
        c.execute("DELETE FROM tournament_teams WHERE tournament_id=?", (tournament_id,))
        c.execute("DELETE FROM tournament_matches WHERE tournament_id=?", (tournament_id,))
        c.execute("DELETE FROM tournaments WHERE id=?", (tournament_id,))
        c.execute("UPDATE announcements SET tournament_id=NULL WHERE tournament_id=?",
                  (tournament_id,))


def link_announcement(tournament_id, announcement_id):
    """Связывает новость и турнир в обе стороны: из новости открывается турнир,
    а по турниру видно, из какого анонса он вырос."""
    with _lock, _conn() as c:
        c.execute("UPDATE tournaments SET announcement_id=? WHERE id=?",
                  (announcement_id, tournament_id))
        c.execute("UPDATE announcements SET tournament_id=? WHERE id=?",
                  (tournament_id, announcement_id))


# ── Команды ─────────────────────────────────────────────────────────────────

def register_team(tournament_id, captain_id, captain_name, team_name, players, amount=None):
    """Регистрирует команду с составом. Возвращает id команды.
    players — список имён игроков (строк); пустые отбрасываются."""
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO tournament_teams(tournament_id, captain_id, captain_name, name,
                    amount, payment_claimed, status, created_at)
               VALUES(?,?,?,?,?,0,'pending',datetime('now'))""",
            (tournament_id, str(captain_id) if captain_id else None, captain_name,
             team_name, amount))
        team_id = cur.lastrowid
        for i, p in enumerate([p for p in (players or []) if (p or "").strip()]):
            c.execute(
                "INSERT INTO tournament_team_players(team_id, name, position) VALUES(?,?,?)",
                (team_id, p.strip(), i))
        return team_id


def get_teams(tournament_id, only_confirmed=False):
    q = f"{_TEAM_SELECT} WHERE tournament_id=?"
    if only_confirmed:
        q += " AND status='confirmed'"
    q += " ORDER BY id"
    with _lock, _conn() as c:
        rows = c.execute(q, (tournament_id,)).fetchall()
        teams = [dict(zip(_TEAM_KEYS, r)) for r in rows]
        for t in teams:
            t["players"] = [
                {"id": p[0], "name": p[1], "user_id": p[2]}
                for p in c.execute(
                    "SELECT id, name, user_id FROM tournament_team_players "
                    "WHERE team_id=? ORDER BY position, id", (t["id"],)).fetchall()
            ]
    return teams


def get_team(team_id):
    with _lock, _conn() as c:
        row = c.execute(f"{_TEAM_SELECT} WHERE id=?", (team_id,)).fetchone()
        if not row:
            return None
        t = dict(zip(_TEAM_KEYS, row))
        t["players"] = [
            {"id": p[0], "name": p[1], "user_id": p[2]}
            for p in c.execute(
                "SELECT id, name, user_id FROM tournament_team_players "
                "WHERE team_id=? ORDER BY position, id", (team_id,)).fetchall()
        ]
    return t


def get_my_teams(tournament_id, user_id):
    """Команды, которые зарегистрировал этот пользователь (он капитан)."""
    return [t for t in get_teams(tournament_id) if t["captain_id"] == str(user_id)]


def claim_team_payment(team_id):
    with _lock, _conn() as c:
        c.execute("UPDATE tournament_teams SET payment_claimed=1 WHERE id=?", (team_id,))


def confirm_team(team_id):
    with _lock, _conn() as c:
        c.execute("UPDATE tournament_teams SET status='confirmed', payment_claimed=1 "
                  "WHERE id=?", (team_id,))


def cancel_team(team_id):
    """Снимает команду с турнира вместе с составом. Матчи с её участием
    обнуляются по этой команде, чтобы не осталось ссылок в никуда."""
    with _lock, _conn() as c:
        c.execute("DELETE FROM tournament_team_players WHERE team_id=?", (team_id,))
        c.execute("UPDATE tournament_matches SET team_a_id=NULL WHERE team_a_id=?", (team_id,))
        c.execute("UPDATE tournament_matches SET team_b_id=NULL WHERE team_b_id=?", (team_id,))
        c.execute("DELETE FROM tournament_teams WHERE id=?", (team_id,))


def set_team_group(team_id, group_index):
    with _lock, _conn() as c:
        c.execute("UPDATE tournament_teams SET group_index=? WHERE id=?",
                  (group_index, team_id))


def autodistribute_groups(tournament_id):
    """Равномерно раскидывает подтверждённые команды по группам, сохраняя
    уже расставленные вручную. Новые команды идут в самую пустую группу."""
    t = get_tournament(tournament_id)
    if not t:
        return
    num_groups = max(1, int(t.get("num_groups") or 2))
    teams = get_teams(tournament_id, only_confirmed=True)

    counts = [0] * num_groups
    unassigned = []
    for team in teams:
        g = team.get("group_index")
        if g is not None and 0 <= g < num_groups:
            counts[g] += 1
        else:
            unassigned.append(team)

    for team in unassigned:
        g = min(range(num_groups), key=lambda i: counts[i])
        set_team_group(team["id"], g)
        counts[g] += 1


# ── Матчи ───────────────────────────────────────────────────────────────────

def create_match(tournament_id, stage, group_index, round_name, team_a_id, team_b_id,
                  match_date, match_time, location, sort_order=0):
    with _lock, _conn() as c:
        cur = c.execute(
            """INSERT INTO tournament_matches(tournament_id, stage, group_index, round_name,
                    team_a_id, team_b_id, match_date, match_time, location, status,
                    sort_order, created_at)
               VALUES(?,?,?,?,?,?,?,?,?,'scheduled',?,datetime('now'))""",
            (tournament_id, stage or "group", group_index, round_name, team_a_id,
             team_b_id, match_date, match_time, location, sort_order))
        return cur.lastrowid


def update_match(match_id, stage, group_index, round_name, team_a_id, team_b_id,
                  match_date, match_time, location):
    with _lock, _conn() as c:
        c.execute(
            """UPDATE tournament_matches SET stage=?, group_index=?, round_name=?,
                    team_a_id=?, team_b_id=?, match_date=?, match_time=?, location=?
               WHERE id=?""",
            (stage, group_index, round_name, team_a_id, team_b_id, match_date,
             match_time, location, match_id))


def set_match_result(match_id, score_a, score_b):
    """Проставляет счёт и закрывает матч. Турнирная таблица пересчитается сама
    при следующем чтении — она нигде не хранится."""
    with _lock, _conn() as c:
        c.execute(
            "UPDATE tournament_matches SET score_a=?, score_b=?, status='finished' WHERE id=?",
            (int(score_a), int(score_b), match_id))


def delete_match(match_id):
    with _lock, _conn() as c:
        c.execute("DELETE FROM tournament_matches WHERE id=?", (match_id,))


def get_matches(tournament_id):
    """Все матчи турнира с подставленными названиями команд."""
    with _lock, _conn() as c:
        rows = c.execute(
            f"{_M_SELECT} WHERE tournament_id=? ORDER BY stage DESC, group_index, "
            f"sort_order, match_date, match_time, id", (tournament_id,)).fetchall()
        matches = [dict(zip(_M_KEYS, r)) for r in rows]
        names = dict(c.execute(
            "SELECT id, name FROM tournament_teams WHERE tournament_id=?",
            (tournament_id,)).fetchall())
    for m in matches:
        m["team_a_name"] = names.get(m["team_a_id"])
        m["team_b_name"] = names.get(m["team_b_id"])
    return matches


# ── Турнирная таблица ───────────────────────────────────────────────────────

def get_champion(tournament_id):
    """Чемпион турнира — определяется по типу турнира (tournament_type):
      - 'cup'    — победитель сыгранного финала плей-офф (см. _cup_champion);
      - 'league' — лидер общей таблицы после того, как организатор закрыл
                   турнир (см. _league_champion) — в лиге нет отдельного
                   финального матча, поэтому момент завершения фиксирует админ.
    Как и раньше, ничего не хранится — считается заново на каждый вызов."""
    t = get_tournament(tournament_id)
    if not t:
        return None
    if (t.get("tournament_type") or "cup") == "league":
        return _league_champion(tournament_id, t)
    return _cup_champion(tournament_id)


def _league_champion(tournament_id, t):
    """Лига без плей-офф: чемпион — первая строка общей таблицы (группа 0),
    но только после того, как админ перевёл турнир в статус 'finished' —
    формат «каждый с каждым» не даёт автоматического признака «всё сыграно»."""
    if t.get("status") != "finished":
        return None
    standings = group_standings(tournament_id)
    rows = standings.get(0) or (next(iter(standings.values()), None))
    if not rows:
        return None
    winner = rows[0]
    runner_up = rows[1] if len(rows) > 1 else None
    return {
        "team_id": winner["team_id"],
        "name": winner["name"],
        "runner_up_id": runner_up["team_id"] if runner_up else None,
        "runner_up_name": runner_up["name"] if runner_up else None,
        "score": None,
        "final_date": None,
    }


def _cup_champion(tournament_id):
    """Чемпион кубка — победитель сыгранного финала.

    Ничего не хранится: смотрим матч плей-офф, у которого в названии раунда
    есть «Финал» (но не «3-е место» — это матч за бронзу), и берём команду
    с большим счётом. None, пока финал не сыгран или закончился вничью
    (в этом случае организатор доигрывает/правит счёт).
    """
    matches = get_matches(tournament_id)
    finals = [m for m in matches
              if m["stage"] == "playoff"
              # именно финал, а не «1/4 финала» и не «Матч за 3-е место»
              and str(m.get("round_name") or "").strip().lower() == "финал"
              and m["status"] == "finished"
              and m["score_a"] is not None and m["score_b"] is not None]
    if not finals:
        return None
    f = finals[-1]
    if f["score_a"] == f["score_b"]:
        return None
    win_id = f["team_a_id"] if f["score_a"] > f["score_b"] else f["team_b_id"]
    lose_id = f["team_b_id"] if f["score_a"] > f["score_b"] else f["team_a_id"]
    names = {m["team_a_id"]: m["team_a_name"] for m in matches}
    names.update({m["team_b_id"]: m["team_b_name"] for m in matches})
    return {
        "team_id": win_id,
        "name": names.get(win_id),
        "runner_up_id": lose_id,
        "runner_up_name": names.get(lose_id),
        "score": f"{max(f['score_a'], f['score_b'])}:{min(f['score_a'], f['score_b'])}",
        "final_date": f.get("match_date"),
    }


def get_tournaments_overview():
    """Список всех турниров для меню: с числом команд, чемпионом и признаком
    завершённости. Завершённым считается турнир, у которого сыгран финал
    (есть чемпион) либо админ вручную перевёл его в архив (status='finished').
    """
    out = []
    for t in get_tournaments():
        champion = get_champion(t["id"])
        teams = get_teams(t["id"], only_confirmed=True)
        matches = get_matches(t["id"])
        played = [m for m in matches if m["status"] == "finished"]
        t = dict(t)
        t["champion"] = champion
        t["teams_count"] = len(teams)
        t["matches_total"] = len(matches)
        t["matches_played"] = len(played)
        t["is_finished"] = bool(champion) or t.get("status") == "finished"
        out.append(t)
    return out


def get_tournament_win_counts():
    """Сколько турниров выиграл каждый капитан — {captain_id: число побед}.

    Победа засчитывается только капитану команды-чемпиона: состав команды
    (tournament_team_players) — это просто вписанные капитаном имена, без
    привязки к реальным аккаунтам, и только у капитана (captain_id) есть
    гарантированно настоящий user_id. Используется рейтингом игрока
    (storage/ovr.py: +3 OVR за победу) — считается один раз для ВСЕХ
    игроков разом (не по турниру на каждого игрока), потому что вызывается
    из get_players_stats_bulk() на каждый опрос списка игр."""
    counts = {}
    for t in get_tournaments_overview():
        champion = t.get("champion")
        if not champion or not champion.get("team_id"):
            continue
        team = get_team(champion["team_id"])
        captain_id = team.get("captain_id") if team else None
        if captain_id:
            counts[captain_id] = counts.get(captain_id, 0) + 1
    return counts


def set_tournament_status(tournament_id, status):
    """Архивирование/возврат турнира в активные ('finished' | 'active')."""
    with _lock, _conn() as c:
        c.execute("UPDATE tournaments SET status=? WHERE id=?", (status, tournament_id))


def group_standings(tournament_id):
    """Таблицы групп, посчитанные из сыгранных матчей группового этапа.

    Ничего не хранит — считает каждый раз заново, поэтому таблица не может
    разойтись с результатами. Сортировка: очки → разница мячей → забитые →
    название команды.

    Возвращает {group_index: [ {team_id, name, played, win, draw, loss,
                                goals_for, goals_against, diff, points}, ... ]}
    """
    teams = get_teams(tournament_id, only_confirmed=True)
    matches = [m for m in get_matches(tournament_id)
               if m["stage"] == "group" and m["status"] == "finished"
               and m["score_a"] is not None and m["score_b"] is not None]

    table = {}
    for t in teams:
        g = t.get("group_index")
        if g is None:
            continue
        table.setdefault(g, {})[t["id"]] = {
            "team_id": t["id"], "name": t["name"], "played": 0, "win": 0, "draw": 0,
            "loss": 0, "goals_for": 0, "goals_against": 0, "diff": 0, "points": 0,
        }

    for m in matches:
        g = m.get("group_index")
        rows = table.get(g)
        if not rows:
            continue
        a, b = rows.get(m["team_a_id"]), rows.get(m["team_b_id"])
        if not a or not b:
            continue
        sa, sb = int(m["score_a"]), int(m["score_b"])
        a["played"] += 1; b["played"] += 1
        a["goals_for"] += sa; a["goals_against"] += sb
        b["goals_for"] += sb; b["goals_against"] += sa
        if sa > sb:
            a["win"] += 1; a["points"] += _WIN
            b["loss"] += 1; b["points"] += _LOSS
        elif sa < sb:
            b["win"] += 1; b["points"] += _WIN
            a["loss"] += 1; a["points"] += _LOSS
        else:
            a["draw"] += 1; a["points"] += _DRAW
            b["draw"] += 1; b["points"] += _DRAW

    out = {}
    for g, rows in table.items():
        lst = list(rows.values())
        for r in lst:
            r["diff"] = r["goals_for"] - r["goals_against"]
        lst.sort(key=lambda r: (-r["points"], -r["diff"], -r["goals_for"], r["name"]))
        out[g] = lst
    return out


def generate_cup_semifinals(tournament_id):
    """Кубок: из таблиц двух групп строит перекрёстные полуфиналы —
    1-е место группы А против 2-го места группы Б, и наоборот. Финал
    админ создаёт вручную (как обычный матч плей-офф) после того, как
    оба полуфинала сыграны — победители заранее не известны.

    Создаёт полуфиналы один раз: если в плей-офф уже есть матчи, просит
    сперва удалить их вручную, чтобы не наплодить дублей."""
    t = get_tournament(tournament_id)
    if not t or (t.get("tournament_type") or "cup") != "cup":
        return {"ok": False, "error": "Доступно только для турниров типа «Кубок»"}

    if any(m["stage"] == "playoff" for m in get_matches(tournament_id)):
        return {"ok": False, "error": "Плей-офф уже сформирован — удали старые матчи, чтобы пересоздать"}

    standings = group_standings(tournament_id)
    group_a, group_b = standings.get(0) or [], standings.get(1) or []
    if len(group_a) < 2 or len(group_b) < 2:
        return {"ok": False, "error": "Нужно 2 группы минимум по 2 подтверждённые команды в каждой"}
    if not any(r["played"] for r in group_a) or not any(r["played"] for r in group_b):
        return {"ok": False, "error": "Групповой этап ещё не сыгран — сначала внеси результаты матчей"}

    a1, a2 = group_a[0], group_a[1]
    b1, b2 = group_b[0], group_b[1]
    create_match(tournament_id, "playoff", None, "Полуфинал", a1["team_id"], b2["team_id"],
                 None, None, t.get("location"), sort_order=0)
    create_match(tournament_id, "playoff", None, "Полуфинал", a2["team_id"], b1["team_id"],
                 None, None, t.get("location"), sort_order=1)
    return {"ok": True}
