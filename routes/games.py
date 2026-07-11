"""Игры глазами игрока: список, запись/отмена, оплата, чат игры, лидерборд."""
import json

from api import tg_post
from config import ADMIN_IDS
from storage import (
    get_profile, get_role, display_name_from_profile,
    get_active_games, get_history_games, get_game,
    signup_for_game, get_signups, get_my_signup, get_my_signups, cancel_signup, mark_payment_claimed,
    is_registered_for_game, add_chat_message, get_chat_messages,
    get_team_members, get_leaderboard, LEADERBOARD_CATEGORIES,
    get_player_stat_in_match,
)
from .helpers import _recompute_teams


class GamesRoutesMixin:
    def route_post_games_signup(self, body):
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            game_id = data.get("game_id")
            guests_count = int(data.get("guests_count") or 0)
            is_addition = bool(data.get("is_addition"))
            if not user_id or not game_id:
                self._json({"ok": False, "error": "bad_request"})
                return
            if guests_count < 0 or guests_count > 20:
                self._json({"ok": False, "error": "Некорректное число людей"})
                return
            if is_addition and guests_count < 1:
                self._json({"ok": False, "error": "Укажи хотя бы одного человека"})
                return

            game = get_game(game_id)
            new_people = guests_count if is_addition else 1 + guests_count
            if game and game.get("num_players"):
                existing = get_signups(game_id)
                current_total = sum(
                    (s["guests_count"] if s.get("is_addition") else 1 + (s.get("guests_count") or 0))
                    for s in existing
                )
                limit = int(game["num_players"])
                if current_total + new_people > limit:
                    free = max(0, limit - current_total)
                    self._json({"ok": False, "error": f"На игру заявлено {limit} мест, свободно: {free}"})
                    return

            profile = get_profile(user_id)
            role = get_role(user_id)
            name = display_name_from_profile(profile)
            player = role["player"] if role else None

            signup_for_game(game_id, user_id, name, player, guests_count, None, is_addition)
            _recompute_teams(game_id)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] games/signup: {e}")
            self.send_response(400); self.end_headers()


    def route_post_games_cancel_signup(self, body):
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            entry_id = data.get("entry_id")
            game_id = data.get("game_id")
            if not user_id or not entry_id or not game_id:
                self._json({"ok": False, "error": "bad_request"})
                return
            cancelled = cancel_signup(entry_id, user_id)
            if not cancelled:
                self._json({"ok": False, "error": "Матч уже завершён — отменить запись нельзя"})
                return
            _recompute_teams(game_id)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] games/cancel-signup: {e}")
            self.send_response(400); self.end_headers()


    def route_post_games_claim_payment(self, body):
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            game_id = data.get("game_id")
            entry_id = data.get("entry_id")
            if not user_id or not game_id or not entry_id:
                self._json({"ok": False, "error": "bad_request"})
                return

            signups = get_signups(game_id)
            mine = next((s for s in signups if s["id"] == entry_id and s["user_id"] == user_id), None)
            if not mine:
                self._json({"ok": False, "error": "Запись не найдена"})
                return

            mark_payment_claimed(entry_id)

            game = get_game(game_id)
            name = mine["name"]
            total_people = mine["guests_count"] if mine.get("is_addition") else 1 + (mine.get("guests_count") or 0)
            when = f"{game['date']} {game['time']}" if game else ""
            admin_text = (
                f"💰 <b>Заявка на оплату!</b>\n\n"
                f"👤 {name} ({total_people} чел.) отметил(а), что оплатил(а) за игру\n"
                f"📅 {when} | 📍 {game['location'] if game else ''}\n\n"
                f"Проверь перевод и подтверди в панели /admin"
            )
            for admin_id in ADMIN_IDS:
                tg_post(admin_id, "sendMessage", text=admin_text, parse_mode="HTML")

            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] games/claim-payment: {e}")
            self.send_response(400); self.end_headers()


    def route_post_games_chat_send(self, body):
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            game_id = data.get("game_id")
            text = (data.get("text") or "").strip()
            if not user_id or not game_id or not text:
                self._json({"ok": False, "error": "bad_request"})
                return
            if not is_registered_for_game(game_id, user_id) and user_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Чат доступен только записавшимся на игру"})
                return

            profile = get_profile(user_id)
            name = display_name_from_profile(profile)

            add_chat_message(game_id, user_id, name, text)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] games/chat/send: {e}")
            self.send_response(400); self.end_headers()


    def route_get_games(self, q):
        user_id = (q.get("user_id") or [""])[0]
        games = get_active_games()
        if user_id:
            games = games + get_history_games(user_id)
        for g in games:
            g["signups"] = get_signups(g["id"])
            g["my_status"] = get_my_signup(g["id"], user_id) if user_id else None
            g["my_signups"] = get_my_signups(g["id"], user_id) if user_id else []
            g["teams"] = get_team_members(g["id"])
            # Статистика игрока конкретно в этом матче (голы/MVP) — для карточки
            # завершённой игры, состояние «Матч завершён» (см. games.html).
            # None, если по этому матчу статистика ещё не заводилась.
            g["my_match_stats"] = get_player_stat_in_match(g["id"], user_id) if user_id else None
        self._json({"games": games})

    def route_get_games_chat(self, q):
        user_id = (q.get("user_id") or [""])[0]
        game_id = (q.get("game_id") or [""])[0]
        since_id = int((q.get("since_id") or ["0"])[0] or 0)
        if not is_registered_for_game(game_id, user_id) and user_id not in ADMIN_IDS:
            self._json({"error": "forbidden"})
        else:
            self._json({"messages": get_chat_messages(game_id, since_id)})

    def route_get_leaderboard(self, q):
        category = (q.get("type") or ["games"])[0]
        try:
            limit = max(1, min(50, int((q.get("limit") or ["10"])[0])))
        except (TypeError, ValueError):
            limit = 10

        if category not in LEADERBOARD_CATEGORIES:
            self._json({"leaderboard": [], "implemented": False})
            return

        meta = LEADERBOARD_CATEGORIES[category]
        self._json({
            "leaderboard": get_leaderboard(category, limit),
            "implemented": True,
            "label": meta["label"],
            "icon": meta["icon"],
        })
