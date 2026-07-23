"""Игры глазами игрока: список, запись/отмена, оплата, чат игры, лидерборд."""
import json

from api import tg_post
from config import ADMIN_IDS, bot_share_link, get_bot_username
from teams import game_capacity
from storage import (
    get_profile, get_role, display_name_from_profile,
    get_active_games, get_history_games, get_game,
    signup_for_game, get_signups, get_my_signup, get_my_signups, cancel_signup, mark_payment_claimed,
    is_registered_for_game, add_chat_message, get_chat_messages,
    get_team_members, get_leaderboard, LEADERBOARD_CATEGORIES,
    get_player_stat_in_match, get_players_stats_bulk,
    price_per_player, entry_amount,
    create_invites_for_signup, get_invites_for_signup, get_invite,
    claim_invite, has_phone,
)
from .helpers import _recompute_teams


class GamesRoutesMixin:
    def _invite_public(self, inv):
        """Приглашение в виде, готовом для клиента: ссылка на бота с deep-link
        параметром start=inv_<token>. Открытие ссылки запускает бота, тот
        открывает Mini App, а приложение занимает место по токену."""
        token = inv["token"]
        username = get_bot_username()
        link = f"https://t.me/{username}?start=inv_{token}" if username else None
        return {
            "token": token,
            "slot_index": inv["slot_index"],
            "claimed": bool(inv.get("claimed_by")),
            "claimed_name": inv.get("claimed_name"),
            "link": link,
        }

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

            # Лимит = число команд × игроков в команде (см. teams.game_capacity).
            # Считаем ВСЕ записи, включая неоплаченные: бронь держит место,
            # иначе на одно место записалось бы несколько человек, пока админ
            # не подтвердил оплату.
            capacity = game_capacity(game)
            if capacity:
                existing = get_signups(game_id)
                current_total = sum(
                    (s["guests_count"] if s.get("is_addition") else 1 + (s.get("guests_count") or 0))
                    for s in existing
                )
                if current_total + new_people > capacity:
                    free = max(0, capacity - current_total)
                    if free == 0:
                        msg = f"Все места заняты ({capacity} из {capacity})"
                    else:
                        msg = f"Осталось мест: {free} из {capacity}"
                    self._json({"ok": False, "error": msg})
                    return

            profile = get_profile(user_id)
            role = get_role(user_id)
            name = display_name_from_profile(profile)
            player = role["player"] if role else None

            # Сумма оплаты партии считается ТОЛЬКО здесь, из цены игры на
            # бэкенде: «сам» — за одного, «компания» — цена × число людей.
            # Клиент сумму не присылает — подделать её из приложения нельзя.
            amount = entry_amount(game, new_people)

            signup_id = signup_for_game(game_id, user_id, name, player, guests_count, None, is_addition, amount)
            _recompute_teams(game_id)

            # Регистрация компании (не «добавление», людей больше одного) —
            # автоматически заводим приглашения на все места, кроме места
            # организатора: Player 2 … Player N. Возвращаем ссылки клиенту,
            # чтобы экран подтверждения сразу показал их для копирования.
            invites = []
            if not is_addition and new_people >= 2:
                created = create_invites_for_signup(game_id, signup_id, user_id, new_people)
                invites = [self._invite_public(inv) for inv in created]

            self._json({"ok": True, "amount": amount, "signup_id": signup_id, "invites": invites})
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
            # Сумма партии: сохранённая при записи; для старых записей без
            # amount — пересчёт из цены игры тем же способом (storage/pricing.py).
            amount = mine.get("amount")
            if amount is None:
                amount = entry_amount(game, total_people)
            amount_line = f"💵 Сумма к оплате: <b>{amount} ₸</b>\n" if amount is not None else ""
            when = f"{game['date']} {game['time']}" if game else ""
            admin_text = (
                f"💰 <b>Заявка на оплату!</b>\n\n"
                f"👤 {name} ({total_people} чел.) отметил(а), что оплатил(а) за игру\n"
                f"{amount_line}"
                f"📅 {when} | 📍 {game['location'] if game else ''}\n\n"
                f"Проверь перевод и подтверди в панели /admin"
            )
            for admin_id in ADMIN_IDS:
                tg_post(admin_id, "sendMessage", text=admin_text, parse_mode="HTML")

            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] games/claim-payment: {e}")
            self.send_response(400); self.end_headers()


    def route_post_games_claim_invite(self, body):
        """Игрок открыл приглашение (start=inv_<token>) и приложение занимает
        за ним конкретное оплаченное место компании. Новую запись/оплату не
        создаёт и лимит игры не трогает — место уже оплачено организатором.
        Требует, чтобы у игрока был телефон (аккаунт): иначе просим сперва
        завершить регистрацию в боте."""
        try:
            data = json.loads(body)
            user_id = str(data.get("user_id", ""))
            token = (data.get("token") or "").strip()
            if not user_id or not token:
                self._json({"ok": False, "error": "bad_request"})
                return

            inv = get_invite(token)
            if not inv:
                self._json({"ok": False, "error": "Приглашение не найдено или устарело"})
                return

            # Нет аккаунта (не поделился телефоном) — регистрация сначала.
            if not has_phone(user_id):
                self._json({"ok": False, "error": "need_registration",
                            "game_id": inv["game_id"]})
                return

            profile = get_profile(user_id)
            name = display_name_from_profile(profile) if profile else "Игрок"
            ok, result = claim_invite(token, user_id, name)
            if not ok:
                msg = ("Это место уже занято другим игроком"
                       if result == "already_claimed"
                       else "Приглашение не найдено или устарело")
                self._json({"ok": False, "error": msg})
                return

            # Место занято — пересчитываем состав, чтобы игрок появился в нём
            # вместо плейсхолдера «(гость N)».
            _recompute_teams(inv["game_id"])
            self._json({"ok": True, "game_id": inv["game_id"]})
        except Exception as e:
            print(f"  [WARN] games/claim-invite: {e}")
            self.send_response(400); self.end_headers()

    def route_get_games_invites(self, q):
        """Ссылки-приглашения партии компании (для экрана подтверждения и
        карточки игры) — только владелец партии может их получить."""
        user_id = (q.get("user_id") or [""])[0]
        signup_id = (q.get("signup_id") or [""])[0]
        if not user_id or not signup_id:
            self._json({"invites": []})
            return
        try:
            signup_id = int(signup_id)
        except (TypeError, ValueError):
            self._json({"invites": []})
            return
        invites = [self._invite_public(inv) for inv in get_invites_for_signup(signup_id)]
        self._json({"invites": invites})

    def route_post_games_chat_send(self, body):
        try:
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
            # Числовая цена за игрока — единственный источник для всех денежных
            # сумм на фронтенде (шит записи, кнопки оплаты). Парсится из
            # свободного текста games.price только тут, на бэкенде.
            g["price_per_player"] = price_per_player(g)
            # Реальная вместимость = команды × игроков в команде. Фронтенд
            # использует ЭТО число для индикатора мест и статуса «мест нет»,
            # чтобы не расходиться с проверкой лимита на бэкенде.
            g["capacity"] = game_capacity(g)
            # Ссылка на бота для кнопки «Пригласить игроков» (экран
            # подтверждения регистрации компании). None — если недоступна.
            g["share_link"] = bot_share_link()
            g["signups"] = get_signups(g["id"])
            g["my_status"] = get_my_signup(g["id"], user_id) if user_id else None
            g["my_signups"] = get_my_signups(g["id"], user_id) if user_id else []
            g["teams"] = get_team_members(g["id"])
            # Статистика игрока конкретно в этом матче (голы/MVP) — для карточки
            # завершённой игры, состояние «Матч завершён» (см. games.html).
            # None, если по этому матчу статистика ещё не заводилась.
            g["my_match_stats"] = get_player_stat_in_match(g["id"], user_id) if user_id else None

        # Карточки игроков в списке "Участники" и в составах команд показывают
        # OVR/игры/голы — берём их одним общим вызовом Player Statistics service
        # на все игры разом (не по одному запросу на игрока), чтобы не
        # дублировать расчёт статистики и не заваливать БД повторными запросами.
        all_ids = {s["user_id"] for g in games for s in g["signups"] if s.get("user_id")}
        all_ids |= {m["user_id"] for g in games for m in g["teams"] if m.get("user_id")}
        stats_by_id = get_players_stats_bulk(all_ids) if all_ids else {}
        for g in games:
            for s in g["signups"]:
                stats = stats_by_id.get(str(s.get("user_id")))
                if stats:
                    s["ovr"] = stats["ovr"]
                    s["games_played"] = stats["games_played"]
                    s["goals"] = stats["goals"]
            for m in g["teams"]:
                stats = stats_by_id.get(str(m.get("user_id")))
                if stats:
                    m["ovr"] = stats["ovr"]
                    m["games_played"] = stats["games_played"]
                    m["goals"] = stats["goals"]

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
