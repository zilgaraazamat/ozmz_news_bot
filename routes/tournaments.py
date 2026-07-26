"""Эндпоинты турниров: публичная часть (просмотр, регистрация команды,
заявка об оплате) и админская (создание турнира и матчей, подтверждение
команд, результаты, разведение по группам)."""
import json

from api import tg_post
from config import ADMIN_IDS
from storage import (
    get_tournament, get_tournaments, create_tournament, update_tournament,
    delete_tournament, link_announcement, entry_fee_amount,
    register_team, get_teams, get_team, get_my_teams, claim_team_payment,
    confirm_team, cancel_team, set_team_group, autodistribute_groups,
    create_match, update_match, set_match_result, delete_match, get_matches,
    group_standings, get_profile, display_name_from_profile,
)

_MAX_PLAYERS_PER_TEAM = 30


class TournamentRoutesMixin:
    # ── Публичное ───────────────────────────────────────────────────────────
    def route_get_tournaments(self, q):
        self._json({"tournaments": get_tournaments(only_active=True)})

    def route_get_tournament(self, q):
        """Полная выдача по турниру: сам турнир, команды, матчи, таблицы групп.
        Одним запросом, чтобы страница турнира не дёргала API пять раз."""
        try:
            tid = int((q.get("id") or [0])[0])
        except (TypeError, ValueError):
            self._json({"error": "bad_request"})
            return
        t = get_tournament(tid)
        if not t:
            self._json({"error": "not_found"})
            return

        user_id = (q.get("user_id") or [""])[0]
        teams = get_teams(tid)
        standings = group_standings(tid)
        self._json({
            "tournament": t,
            "entry_amount": entry_fee_amount(t),
            "teams": teams,
            "matches": get_matches(tid),
            # ключи групп в JSON становятся строками — на фронте это учтено
            "standings": {str(g): rows for g, rows in standings.items()},
            "my_teams": get_my_teams(tid, user_id) if user_id else [],
            "is_admin": str(user_id) in ADMIN_IDS,
        })

    def route_post_tournament_register(self, body):
        """Капитан регистрирует команду: название + состав игроков.
        Оплата подтверждается отдельно (как в играх)."""
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            tid = data.get("tournament_id")
            team_name = (data.get("team_name") or "").strip()
            players = data.get("players") or []
            if not user_id or not tid or not team_name:
                self._json({"ok": False, "error": "Укажи название команды"})
                return

            t = get_tournament(tid)
            if not t:
                self._json({"ok": False, "error": "Турнир не найден"})
                return

            # Лимит команд: считаем все заявки, а не только оплаченные —
            # заявка держит место, пока админ её не отклонил.
            if t.get("max_teams"):
                if len(get_teams(tid)) >= int(t["max_teams"]):
                    self._json({"ok": False, "error": "Все места заняты — набран максимум команд"})
                    return

            # Одна команда от капитана: иначе он мог бы забить весь турнир.
            if get_my_teams(tid, user_id):
                self._json({"ok": False, "error": "Ты уже зарегистрировал команду на этот турнир"})
                return

            players = [str(p).strip() for p in players if str(p or "").strip()]
            if len(players) > _MAX_PLAYERS_PER_TEAM:
                players = players[:_MAX_PLAYERS_PER_TEAM]

            profile = get_profile(user_id)
            captain_name = display_name_from_profile(profile) if profile else "Капитан"
            amount = entry_fee_amount(t)

            team_id = register_team(tid, user_id, captain_name, team_name, players, amount)
            self._json({"ok": True, "team_id": team_id, "amount": amount})
        except Exception as e:
            print(f"  [WARN] tournament/register: {e}")
            self.send_response(400); self.end_headers()

    def route_post_tournament_claim_payment(self, body):
        """Капитан отметил, что оплатил взнос — уведомляем админов."""
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            team_id = data.get("team_id")
            if not user_id or not team_id:
                self._json({"ok": False, "error": "bad_request"})
                return
            team = get_team(team_id)
            if not team or team["captain_id"] != user_id:
                self._json({"ok": False, "error": "Команда не найдена"})
                return

            claim_team_payment(team_id)
            t = get_tournament(team["tournament_id"])
            amount = team.get("amount") or (entry_fee_amount(t) if t else None)
            text = (f"🏆 <b>Заявка на оплату турнира!</b>\n\n"
                    f"👥 Команда «{team['name']}» ({team['captain_name']})\n"
                    f"🏟 Турнир: {t['name'] if t else ''}\n"
                    + (f"💵 Взнос: <b>{amount} ₸</b>\n" if amount else "")
                    + "\nПроверь перевод и подтверди в панели /admin")
            for admin_id in ADMIN_IDS:
                try:
                    tg_post(admin_id, "sendMessage", text=text, parse_mode="HTML")
                except Exception:
                    pass
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] tournament/claim-payment: {e}")
            self.send_response(400); self.end_headers()

    def route_post_tournament_cancel_team(self, body):
        """Снять свою команду с турнира (капитан) или любую (админ)."""
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            team_id = data.get("team_id")
            team = get_team(team_id) if team_id else None
            if not team:
                self._json({"ok": False, "error": "Команда не найдена"})
                return
            if team["captain_id"] != user_id and user_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав"})
                return
            cancel_team(team_id)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] tournament/cancel-team: {e}")
            self.send_response(400); self.end_headers()

    # ── Админское ───────────────────────────────────────────────────────────
    def _require_admin(self, data):
        admin_id = str(data.get("user_id", ""))
        if admin_id not in ADMIN_IDS:
            self._json({"ok": False, "error": "Нет прав администратора"})
            return None
        return admin_id

    def route_get_admin_tournaments(self, q):
        user_id = (q.get("user_id") or [""])[0]
        if str(user_id) not in ADMIN_IDS:
            self._json({"tournaments": []})
            return
        self._json({"tournaments": get_tournaments()})

    def route_post_admin_save_tournament(self, body):
        """Создаёт или обновляет турнир. Если передан announcement_id —
        связывает с новостью, чтобы из ленты открывалась страница турнира."""
        try:
            data = json.loads(body)
            admin_id = self._require_admin(data)
            if not admin_id:
                return

            name = (data.get("name") or "").strip()
            if not name:
                self._json({"ok": False, "error": "Укажи название турнира"})
                return

            fields = dict(
                description=(data.get("description") or "").strip() or None,
                location=(data.get("location") or "").strip() or None,
                start_date=(data.get("start_date") or "").strip() or None,
                end_date=(data.get("end_date") or "").strip() or None,
                entry_fee=(data.get("entry_fee") or "").strip() or None,
                payment_link=(data.get("payment_link") or "").strip() or None,
                max_teams=data.get("max_teams") or None,
                team_size=data.get("team_size") or None,
                num_groups=data.get("num_groups") or 2,
            )

            image = data.get("image") or None
            if image and "," in image and image.strip().startswith("data:"):
                image = image.split(",", 1)[1]
            if image and len(image) > 900_000:
                self._json({"ok": False, "error": "Фото слишком большое"})
                return

            tid = data.get("id")
            if tid:
                update_tournament(tid, name, fields["description"], fields["location"],
                                   fields["start_date"], fields["end_date"], fields["entry_fee"],
                                   fields["payment_link"], fields["max_teams"],
                                   fields["team_size"], fields["num_groups"], image)
            else:
                tid = create_tournament(name, fields["description"], fields["location"],
                                         fields["start_date"], fields["end_date"],
                                         fields["entry_fee"], fields["payment_link"],
                                         fields["max_teams"], fields["team_size"],
                                         fields["num_groups"], image, admin_id)

            ann_id = data.get("announcement_id")
            if ann_id:
                link_announcement(tid, ann_id)

            self._json({"ok": True, "id": tid})
        except Exception as e:
            print(f"  [WARN] admin/save-tournament: {e}")
            self.send_response(400); self.end_headers()

    def route_post_admin_delete_tournament(self, body):
        try:
            data = json.loads(body)
            if not self._require_admin(data):
                return
            delete_tournament(data.get("id"))
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] admin/delete-tournament: {e}")
            self.send_response(400); self.end_headers()

    def route_post_admin_confirm_team(self, body):
        """Подтверждение взноса: команда попадает в группы и таблицу."""
        try:
            data = json.loads(body)
            if not self._require_admin(data):
                return
            team_id = data.get("team_id")
            confirm_team(team_id)
            team = get_team(team_id)
            if team:
                autodistribute_groups(team["tournament_id"])
                try:
                    t = get_tournament(team["tournament_id"])
                    tg_post(team["captain_id"], "sendMessage",
                            text=(f"✅ Команда «{team['name']}» подтверждена!\n\n"
                                  f"🏆 {t['name'] if t else ''}\n"
                                  f"Следи за расписанием матчей в приложении."),
                            parse_mode="HTML")
                except Exception:
                    pass
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] admin/confirm-team: {e}")
            self.send_response(400); self.end_headers()

    def route_post_admin_set_team_group(self, body):
        try:
            data = json.loads(body)
            if not self._require_admin(data):
                return
            set_team_group(data.get("team_id"), data.get("group_index"))
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] admin/set-team-group: {e}")
            self.send_response(400); self.end_headers()

    def route_post_admin_distribute_groups(self, body):
        try:
            data = json.loads(body)
            if not self._require_admin(data):
                return
            autodistribute_groups(data.get("tournament_id"))
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] admin/distribute-groups: {e}")
            self.send_response(400); self.end_headers()

    def route_post_admin_save_tournament_match(self, body):
        """Создаёт или обновляет матч турнира (групповой или плей-офф)."""
        try:
            data = json.loads(body)
            if not self._require_admin(data):
                return
            mid = data.get("id")
            args = (
                (data.get("stage") or "group"),
                data.get("group_index"),
                (data.get("round_name") or "").strip() or None,
                data.get("team_a_id") or None,
                data.get("team_b_id") or None,
                (data.get("match_date") or "").strip() or None,
                (data.get("match_time") or "").strip() or None,
                (data.get("location") or "").strip() or None,
            )
            if mid:
                update_match(mid, *args)
            else:
                mid = create_match(data.get("tournament_id"), *args,
                                    sort_order=data.get("sort_order") or 0)
            self._json({"ok": True, "id": mid})
        except Exception as e:
            print(f"  [WARN] admin/save-tournament-match: {e}")
            self.send_response(400); self.end_headers()

    def route_post_admin_tournament_match_result(self, body):
        try:
            data = json.loads(body)
            if not self._require_admin(data):
                return
            set_match_result(data.get("match_id"), data.get("score_a") or 0,
                              data.get("score_b") or 0)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] admin/tournament-match-result: {e}")
            self.send_response(400); self.end_headers()

    def route_post_admin_delete_tournament_match(self, body):
        try:
            data = json.loads(body)
            if not self._require_admin(data):
                return
            delete_match(data.get("match_id"))
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] admin/delete-tournament-match: {e}")
            self.send_response(400); self.end_headers()
