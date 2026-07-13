"""Игры глазами администратора: создание игр и шаблонов, управление записями
и командами, статистика по всем играм/пользователям."""
import json

from api import tg_post
from config import ADMIN_IDS, CHAT_ID
from storage import (
    get_profile, get_all_users, get_username,
    create_game, get_all_games, get_game, cancel_game, delete_game, mark_game_completed,
    create_game_template, get_game_templates, update_game_template, delete_game_template,
    get_signups, confirm_signup, move_team_member, get_team_members,
    complete_match, settle_completed_games_xp, get_player_stats, get_games_awaiting_results,
)


class AdminGamesRoutesMixin:
    def route_post_admin_create_game(self, body):
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            if user_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return

            game_date = (data.get("date") or "").strip()
            game_time = (data.get("time") or "").strip()
            location  = (data.get("location") or "").strip()
            num_players = data.get("num_players") or None
            if not game_date or not game_time or not location:
                self._json({"ok": False, "error": "Заполни дату, время и место"})
                return

            num_teams        = data.get("num_teams") or None
            players_per_team = data.get("players_per_team") or None
            price            = (data.get("price") or "").strip()
            extra_info       = (data.get("extra_info") or "").strip()
            payment_link     = (data.get("payment_link") or "").strip() or None

            image = data.get("image") or None
            if image and "," in image and image.strip().startswith("data:"):
                image = image.split(",", 1)[1]
            if image and len(image) > 900_000:
                self._json({"ok": False, "error": "Фото слишком большое, выбери другое"})
                return

            game_id = create_game(game_date, game_time, location, num_players, num_teams,
                                   players_per_team, price, extra_info, user_id, payment_link, image)

            lines = [
                "⚽ <b>НОВАЯ ИГРА!</b>",
                "",
                f"📅 {game_date} | 🕐 {game_time}",
                f"📍 {location}",
            ]
            if num_players:
                lines.append(f"👥 Игроков: {num_players}" + (f" ({num_teams} команды по {players_per_team})" if num_teams and players_per_team else ""))
            if price:
                lines.append(f"💰 {price}")
            if extra_info:
                lines.append(f"\nℹ️ {extra_info}")
            lines.append("\n👉 Приходи и играй с нами! @football_igraem_astana")

            tg_post(CHAT_ID, "sendMessage", text="\n".join(lines), parse_mode="HTML")
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] create-game: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_create_game_template(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return

            name  = (data.get("name") or "").strip()
            field = (data.get("field") or "").strip()
            if not name or not field:
                self._json({"ok": False, "error": "Заполни минимум название и поле"})
                return

            address      = (data.get("address") or "").strip() or None
            default_time = (data.get("default_time") or "").strip() or None
            price        = (data.get("price") or "").strip() or None
            max_players  = data.get("max_players") or None
            duration     = data.get("duration") or None
            description  = (data.get("description") or "").strip() or None
            payment_link = (data.get("payment_link") or "").strip() or None

            image = data.get("image") or None
            if image and "," in image and image.strip().startswith("data:"):
                image = image.split(",", 1)[1]
            if image and len(image) > 900_000:
                self._json({"ok": False, "error": "Фото слишком большое, выбери другое"})
                return

            template_id = create_game_template(name, field, address, default_time, price,
                                                 max_players, duration, description, payment_link,
                                                 image, admin_id)
            self._json({"ok": True, "id": template_id})
        except Exception as e:
            print(f"  [WARN] create-game-template: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_update_game_template(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return

            template_id = data.get("id")
            name  = (data.get("name") or "").strip()
            field = (data.get("field") or "").strip()
            if not template_id or not name or not field:
                self._json({"ok": False, "error": "Заполни минимум название и поле"})
                return

            address      = (data.get("address") or "").strip() or None
            default_time = (data.get("default_time") or "").strip() or None
            price        = (data.get("price") or "").strip() or None
            max_players  = data.get("max_players") or None
            duration     = data.get("duration") or None
            description  = (data.get("description") or "").strip() or None
            payment_link = (data.get("payment_link") or "").strip() or None

            image = data.get("image") or None
            if image and "," in image and image.strip().startswith("data:"):
                image = image.split(",", 1)[1]
            if image and len(image) > 900_000:
                self._json({"ok": False, "error": "Фото слишком большое, выбери другое"})
                return

            update_game_template(template_id, name, field, address, default_time, price,
                                  max_players, duration, description, payment_link, image)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] update-game-template: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_delete_game_template(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            delete_game_template(data.get("id"))
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] delete-game-template: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_confirm_signup(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            entry_id = data.get("entry_id")
            confirm_signup(entry_id)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] confirm-signup: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_move_team_member(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            member_id = int(data.get("member_id"))
            new_team_index = int(data.get("team_index"))
            move_team_member(member_id, new_team_index)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] move-team-member: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_cancel_game(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            game_id = data.get("game_id")
            game = get_game(game_id)
            if not game:
                self._json({"ok": False, "error": "Игра не найдена"})
                return

            cancel_game(game_id)

            text = (
                f"❌ <b>ИГРА ОТМЕНЕНА</b>\n\n"
                f"📅 {game['date']} | 🕐 {game['time']}\n"
                f"📍 {game['location']}\n\n"
                f"Приносим извинения за неудобства 🙏"
            )
            tg_post(CHAT_ID, "sendMessage", text=text, parse_mode="HTML")

            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] cancel-game: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_complete_game(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            game_id = data.get("game_id")
            game = get_game(game_id)
            if not game:
                self._json({"ok": False, "error": "Игра не найдена"})
                return

            mark_game_completed(game_id)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] complete-game: {e}")
            self.send_response(400); self.end_headers()

    def route_post_admin_complete_match(self, body):
        """Единый флоу «Завершить матч»: статус игры, статистика каждого
        игрока (голы + MVP) и прогрессия — одним действием админа, вместо
        разрозненных кнопок/шагов. См. storage/match_completion.py."""
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            game_id = data.get("game_id")
            game = get_game(game_id)
            if not game:
                self._json({"ok": False, "error": "Игра не найдена"})
                return

            # доверяем только реально подтверждённым участникам этой игры —
            # что бы ни пришло в теле запроса, чужой/произвольный user_id
            # статистику получить не может
            confirmed_ids = {str(s["user_id"]) for s in get_signups(game_id) if s.get("status") == "confirmed"}
            submitted = data.get("players") or []
            clean_players = [p for p in submitted if str(p.get("user_id")) in confirmed_ids]

            complete_match(game_id, clean_players)

            # Прогрессия (XP/уровень/OVR) — отдельная, уже реализованная и
            # протестированная забота (progression.py); settle идемпотентен,
            # поэтому его безопасно звать сразу для всех подтверждённых
            # участников, а не только тех, кому вписали статистику.
            for uid in confirmed_ids:
                settle_completed_games_xp(uid)

            self._json({"ok": True, "players": clean_players})
        except Exception as e:
            print(f"  [WARN] complete-match: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_delete_game(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            game_id = data.get("game_id")
            delete_game(game_id)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] delete-game: {e}")
            self.send_response(400); self.end_headers()


    def route_get_admin_game_templates(self, q):
        user_id = (q.get("user_id") or [""])[0]
        if user_id not in ADMIN_IDS:
            self._json({"error": "forbidden"})
        else:
            self._json({"templates": get_game_templates()})

    def route_get_admin_games(self, q):
        user_id = (q.get("user_id") or [""])[0]
        if user_id not in ADMIN_IDS:
            self._json({"error": "forbidden"})
        else:
            games = get_all_games()
            for g in games:
                signups = get_signups(g["id"])
                for s in signups:
                    s["username"] = get_username(s["user_id"])
                    profile = get_profile(s["user_id"])
                    s["phone"] = profile["phone"] if profile else None
                g["signups"] = signups
                g["teams"] = get_team_members(g["id"])
            self._json({"games": games})

    def route_get_admin_users(self, q):
        user_id = (q.get("user_id") or [""])[0]
        if user_id not in ADMIN_IDS:
            self._json({"error": "forbidden"})
        else:
            users = get_all_users()
            for u in users:
                stats = get_player_stats(u["user_id"])
                u["games_played"] = stats["games_played"]
                u["goals"] = stats["goals"]
                u["mvp_count"] = stats["mvp_count"]
                u["ovr"] = stats["ovr"]
            self._json({"users": users})

    def route_get_admin_awaiting_results(self, q):
        """Игры, чьё расчётное время окончания уже прошло, но матч ещё не
        отмечен завершённым — очередь для раздела «Ожидают результата»,
        не затрагивает никакую другую логику (см. is_awaiting_results,
        storage/game_status.py)."""
        user_id = (q.get("user_id") or [""])[0]
        if user_id not in ADMIN_IDS:
            self._json({"error": "forbidden"})
        else:
            games = get_games_awaiting_results()
            for g in games:
                g["signups"] = get_signups(g["id"])
            self._json({"games": games})
