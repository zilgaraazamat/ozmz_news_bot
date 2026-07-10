import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from api import now_astana, tg_post, claude_vision
from config import PORT, PLAYER_CATEGORIES, ADMIN_IDS, CHAT_ID
from storage import (
    get_quiz_history, add_quiz_history, get_all_users, get_all_roles,
    get_profile, set_nickname, get_role, set_role, get_games_played_count,
    create_game, get_all_games, get_active_games, get_history_games, get_game, cancel_game, delete_game,
    signup_for_game, get_signups, get_my_signup, get_my_signups, confirm_signup, cancel_signup, mark_payment_claimed,
    is_registered_for_game, add_chat_message, get_chat_messages,
    get_username,
    get_team_members, clear_game_teams, add_team_member, move_team_member,
    create_announcement, get_active_announcements, get_all_announcements, delete_announcement,
)
from predict import get_stats as predict_stats, announce_result
from battle import create_battle, join_battle, get_state, submit_answer, list_open_battles
from teams import auto_assign_teams


def _display_name(user_id):
    profile = get_profile(user_id)
    if profile and profile.get("nickname"):
        return profile["nickname"]
    if profile and profile.get("name"):
        return profile["name"]
    return "Игрок"


def _recompute_teams(game_id):
    """Автоматически пересчитывает и сохраняет распределение по командам
    сразу при любой записи/отмене — без ручного запуска админом."""
    game = get_game(game_id)
    if not game:
        return
    signups = get_signups(game_id)
    teams = auto_assign_teams(game, signups)
    clear_game_teams(game_id)
    for team_idx, members in enumerate(teams):
        for m in members:
            add_team_member(game_id, m["user_id"], m["name"], m["player"], team_idx, m["is_guest"])


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "POST, GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_POST(self):
        from urllib.parse import urlparse
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        if path == "/api/quiz-result":
            try:
                data = json.loads(body)
                name = data.get("name", "Аноним")
                player = data.get("player", "Неизвестно")
                user_id = data.get("user_id") or None

                add_quiz_history(name, player, now_astana().strftime("%d.%m.%Y %H:%M"), user_id or "web")

                if user_id:
                    category = PLAYER_CATEGORIES.get(player, "Центр")
                    set_role(user_id, name, player, category)

                print(f"  [WEB QUIZ] {name} → {player} (uid={user_id})")
                self._json({"ok": True})
            except Exception as e:
                print(f"  [WARN] quiz-result: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/predict-result":
            # POST {"score": "2:1"} → объявить итоги конкурса
            try:
                data  = json.loads(body)
                score = data.get("score", "")
                if score:
                    announce_result(score)
                    self._json({"ok": True})
                else:
                    self._json({"ok": False, "error": "no score"})
            except Exception as e:
                self.send_response(400); self.end_headers()

        elif path == "/api/battle/create":
            try:
                data = json.loads(body)
                user_id = str(data.get("user_id", ""))
                title = (data.get("title") or "").strip()
                if not user_id:
                    self._json({"error": "no_uid"})
                    return
                name = _display_name(user_id)
                battle_id = create_battle(title, user_id, name)
                self._json({"battle_id": battle_id})
            except Exception as e:
                print(f"  [WARN] battle/create: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/battle/join":
            try:
                data = json.loads(body)
                user_id = str(data.get("user_id", ""))
                battle_id = str(data.get("battle_id", ""))
                if not user_id or not battle_id:
                    self._json({"error": "bad_request"})
                    return
                name = _display_name(user_id)
                error = join_battle(battle_id, user_id, name)
                self._json({"error": error} if error else {"ok": True})
            except Exception as e:
                print(f"  [WARN] battle/join: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/battle/answer":
            try:
                data      = json.loads(body)
                battle_id = str(data.get("battle_id", ""))
                user_id   = str(data.get("user_id", ""))
                answer    = data.get("answer", "")
                result = submit_answer(battle_id, user_id, answer)
                self._json(result if result else {"error": "invalid"})
            except Exception as e:
                print(f"  [WARN] battle/answer: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/profile":
            try:
                data     = json.loads(body)
                user_id  = str(data.get("user_id", ""))
                nickname = (data.get("nickname") or "").strip()[:24]
                if not user_id or not nickname:
                    self._json({"ok": False, "error": "bad_request"})
                else:
                    set_nickname(user_id, nickname)
                    self._json({"ok": True})
            except Exception as e:
                print(f"  [WARN] profile: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/admin/create-game":
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

        elif path == "/api/games/signup":
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
                name = (profile["nickname"] if profile and profile.get("nickname")
                        else (profile["name"] if profile else None)) or "Игрок"
                player = role["player"] if role else None

                signup_for_game(game_id, user_id, name, player, guests_count, None, is_addition)
                _recompute_teams(game_id)
                self._json({"ok": True})
            except Exception as e:
                print(f"  [WARN] games/signup: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/games/cancel-signup":
            try:
                data = json.loads(body)
                user_id = str(data.get("user_id", ""))
                entry_id = data.get("entry_id")
                game_id = data.get("game_id")
                if not user_id or not entry_id or not game_id:
                    self._json({"ok": False, "error": "bad_request"})
                    return
                cancel_signup(entry_id, user_id)
                _recompute_teams(game_id)
                self._json({"ok": True})
            except Exception as e:
                print(f"  [WARN] games/cancel-signup: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/games/claim-payment":
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

        elif path == "/api/scanner/analyze":
            try:
                data = json.loads(body)
                image_b64 = data.get("image") or ""
                if "," in image_b64 and image_b64.strip().startswith("data:"):
                    image_b64 = image_b64.split(",", 1)[1]
                if not image_b64:
                    self._json({"ok": False, "error": "Нет изображения"})
                    return

                prompt = (
                    "Ты — эксперт по футбольным мячам (Adidas, Nike, Puma, Select, Mikasa и другие). "
                    "Внимательно рассмотри фото и определи модель мяча.\n\n"
                    "Верни ТОЛЬКО валидный JSON, без markdown-обрамления, строго в такой структуре:\n"
                    '{"found": true, "confidence": 90, "name": "Adidas Teamgeist", '
                    '"model": "Teamgeist Berlin", "year": "2006", '
                    '"usage": "короткая фраза, 3-6 слов", '
                    '"tournaments": ["Турнир"], '
                    '"fun_fact": "одно короткое яркое предложение", '
                    '"design": "короткая фраза про дизайн, 3-8 слов"}\n\n'
                    "ВАЖНЫЕ правила:\n"
                    "- Пиши МАКСИМАЛЬНО кратко. Каждое поле — короткая фраза, не абзац. Без воды "
                    "и общих слов.\n"
                    "- НЕ утверждай, что мяч 'официальный' или 'оригинальный', если это не считывается "
                    "явно и однозначно с фото (чёткие официальные логотипы турнира на самом мяче). "
                    "Обычный реплика/сувенирный/любительский мяч — не выдавай за официальный. Если "
                    "сомневаешься в статусе — пиши мягко: 'дизайн в стиле...', 'похож на...', без "
                    "утвердительных заявлений о подлинности.\n"
                    "- tournaments заполняй, ТОЛЬКО если реально узнаёшь конкретный турнир по дизайну "
                    "мяча. Если не уверен — пустой массив [].\n"
                    "- usage — если не можешь определить точное использование, просто укажи тип мяча "
                    "(тренировочный / любительский / реплика / коллекционный и т.п.), без выдумок.\n"
                    "- Если на фото не похоже на футбольный мяч или совсем нечётко — верни "
                    '{"found": false, "confidence": null, "name": null, "model": null, "year": null, '
                    '"usage": null, "tournaments": [], "fun_fact": null, "design": null}.\n'
                    "- Если мяч виден, но не уверен в точной модели — всё равно дай лучшую догадку "
                    "(found: true) и честный процент уверенности confidence, не завышай.\n"
                    "- Пиши по-русски, без ссылок и markdown."
                )
                raw = claude_vision(image_b64, "image/jpeg", prompt, max_tokens=500)
                cleaned = raw.replace("```json", "").replace("```", "").strip()
                try:
                    result = json.loads(cleaned)
                except Exception:
                    result = {"found": False, "confidence": None}

                self._json({"ok": True, "result": result})
            except Exception as e:
                print(f"  [WARN] scanner/analyze: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/games/chat/send":
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
                name = (profile["nickname"] if profile and profile.get("nickname")
                        else (profile["name"] if profile else None)) or "Игрок"

                add_chat_message(game_id, user_id, name, text)
                self._json({"ok": True})
            except Exception as e:
                print(f"  [WARN] games/chat/send: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/admin/confirm-signup":
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

        elif path == "/api/admin/move-team-member":
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

        elif path == "/api/admin/cancel-game":
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

        elif path == "/api/admin/delete-game":
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

        elif path == "/api/admin/create-announcement":
            try:
                data = json.loads(body)
                admin_id = str(data.get("user_id", ""))
                if admin_id not in ADMIN_IDS:
                    self._json({"ok": False, "error": "Нет прав администратора"})
                    return
                title = (data.get("title") or "").strip()
                text = (data.get("text") or "").strip()
                category = (data.get("category") or "Анонс").strip()
                event_date = (data.get("event_date") or "").strip() or None
                image = data.get("image") or None
                if image and "," in image and image.strip().startswith("data:"):
                    image = image.split(",", 1)[1]
                if image and len(image) > 900_000:
                    self._json({"ok": False, "error": "Фото слишком большое, выбери другое"})
                    return
                if not title or not text:
                    self._json({"ok": False, "error": "Заполни заголовок и текст"})
                    return

                create_announcement(title, text, admin_id, image, category, event_date)

                group_text = f"📢 <b>{category}: {title}</b>\n\n{text}"
                tg_post(CHAT_ID, "sendMessage", text=group_text, parse_mode="HTML")

                self._json({"ok": True})
            except Exception as e:
                print(f"  [WARN] create-announcement: {e}")
                self.send_response(400); self.end_headers()

        elif path == "/api/admin/delete-announcement":
            try:
                data = json.loads(body)
                admin_id = str(data.get("user_id", ""))
                if admin_id not in ADMIN_IDS:
                    self._json({"ok": False, "error": "Нет прав администратора"})
                    return
                delete_announcement(data.get("id"))
                self._json({"ok": True})
            except Exception as e:
                print(f"  [WARN] delete-announcement: {e}")
                self.send_response(400); self.end_headers()

        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)

        if path == "/app":
            self._file("webapp/app.html", "text/html; charset=utf-8")
        elif path == "/quiz":
            self._file("webapp/index.html", "text/html; charset=utf-8")
        elif path == "/battle":
            self._file("webapp/battle.html", "text/html; charset=utf-8")
        elif path == "/admin":
            self._file("webapp/admin.html", "text/html; charset=utf-8")
        elif path == "/games":
            self._file("webapp/games.html", "text/html; charset=utf-8")
        elif path == "/scanner":
            self._file("webapp/scanner.html", "text/html; charset=utf-8")
        elif path == "/api/is-admin":
            user_id = (q.get("user_id") or [""])[0]
            self._json({"is_admin": user_id in ADMIN_IDS})
        elif path == "/api/announcements":
            self._json({"announcements": get_active_announcements(10)})
        elif path == "/api/admin/announcements":
            user_id = (q.get("user_id") or [""])[0]
            if user_id not in ADMIN_IDS:
                self._json({"error": "forbidden"})
            else:
                self._json({"announcements": get_all_announcements()})
        elif path == "/api/games":
            user_id = (q.get("user_id") or [""])[0]
            games = get_active_games()
            if user_id:
                games = games + get_history_games(user_id)
            for g in games:
                g["signups"] = get_signups(g["id"])
                g["my_status"] = get_my_signup(g["id"], user_id) if user_id else None
                g["my_signups"] = get_my_signups(g["id"], user_id) if user_id else []
                g["teams"] = get_team_members(g["id"])
            self._json({"games": games})
        elif path == "/api/games/chat":
            user_id = (q.get("user_id") or [""])[0]
            game_id = (q.get("game_id") or [""])[0]
            since_id = int((q.get("since_id") or ["0"])[0] or 0)
            if not is_registered_for_game(game_id, user_id) and user_id not in ADMIN_IDS:
                self._json({"error": "forbidden"})
            else:
                self._json({"messages": get_chat_messages(game_id, since_id)})
        elif path == "/api/admin/games":
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
        elif path == "/logo.jpg":
            self._file("webapp/logo.jpg", "image/jpeg")
        elif path == "/api/stats":
            stats = predict_stats()
            self._json(stats)
        elif path == "/api/battle/list":
            self._json({"battles": list_open_battles()})
        elif path == "/api/battle/state":
            battle_id = (q.get("battle_id") or [""])[0]
            user_id = (q.get("user_id") or [""])[0]
            state = get_state(battle_id, user_id)
            self._json(state if state else {"error": "not_found"})
        elif path == "/api/profile":
            user_id = (q.get("user_id") or [""])[0]
            profile = get_profile(user_id)
            role = get_role(user_id)
            games_played = get_games_played_count(user_id) if user_id else 0
            self._json({
                "name": profile["name"] if profile else None,
                "nickname": profile["nickname"] if profile else None,
                "role": role,
                "games_played": games_played,
            })
        elif path == "/":
            self._admin_html()
        else:
            self.send_response(404); self.end_headers()

    # ── helpers ───────────────────────────────────────────────────────────────

    def _json(self, data):
        body = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _file(self, rel_path, content_type):
        full = os.path.join(os.path.dirname(__file__), rel_path)
        try:
            with open(full, "rb") as f:
                data = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            if content_type.startswith("text/html"):
                self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
            else:
                self.send_header("Cache-Control", "public, max-age=86400")

            if content_type.startswith("text/") and "gzip" in self.headers.get("Accept-Encoding", ""):
                import gzip
                data = gzip.compress(data, compresslevel=6)
                self.send_header("Content-Encoding", "gzip")

            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()

    def _admin_html(self):
        quiz_history = get_quiz_history()
        total   = len(quiz_history)
        players = {}
        for h in quiz_history:
            players[h["player"]] = players.get(h["player"], 0) + 1
        top_player = max(players, key=players.get) if players else "—"

        users = get_all_users()
        roles = get_all_roles()

        def mask_phone(p):
            return f"•••{p[-4:]}" if p and len(p) >= 4 else (p or "—")

        ps = predict_stats()
        predict_block = ""
        if ps["active"] and ps["match"]:
            m = ps["match"]
            predict_block = f"""
<div class="section">
  <h2>🎯 Конкурс прогнозов — {m['home']} vs {m['away']} ({m['time']})</h2>
  <p style="color:#6b7c6e;margin:8px 0">Участников: <b style="color:#7ed957">{ps['total_predictions']}</b></p>
  <div style="display:flex;gap:8px;margin-top:12px">
    <input id="score-input" placeholder="2:1" style="padding:8px 12px;border-radius:8px;border:1px solid rgba(126,217,87,.3);background:#0e1a12;color:#f5f5f0;font-size:14px">
    <button onclick="announceResult()" style="padding:8px 16px;background:#7ed957;color:#0e1a12;border:none;border-radius:8px;font-weight:700;cursor:pointer">Объявить итог</button>
  </div>
</div>
<script>
function announceResult(){{
  const score = document.getElementById('score-input').value.trim();
  if(!score)return;
  fetch('/api/predict-result',{{method:'POST',headers:{{'Content-Type':'application/json'}},body:JSON.stringify({{score}})}})
    .then(r=>r.json()).then(d=>alert(d.ok?'✅ Итоги объявлены!':'❌ '+d.error));
}}
</script>"""

        rows = "".join(
            f"<tr><td>{i}</td><td>{h['name']}</td>"
            f"<td><span class='badge'>{h['player']}</span></td>"
            f"<td>{h['date']}</td></tr>"
            for i, h in enumerate(reversed(quiz_history), 1)
        ) or '<tr><td colspan="4" class="empty">Тестов ещё не было 🎮</td></tr>'

        users_rows = "".join(
            f"<tr><td>{i}</td><td>{u['name'] or '—'}</td>"
            f"<td>{('<span class=\"badge\">' + u['nickname'] + '</span>') if u.get('nickname') else '—'}</td>"
            f"<td>{('@' + u['username']) if u.get('username') else '—'}</td>"
            f"<td>{mask_phone(u['phone'])}</td><td>{u['joined_at']}</td></tr>"
            for i, u in enumerate(users, 1)
        ) or '<tr><td colspan="6" class="empty">Пока никто не заходил 👀</td></tr>'

        roles_rows = "".join(
            f"<tr><td>{i}</td><td>{r['name']}</td>"
            f"<td><span class='badge'>{r['player']}</span></td>"
            f"<td>{r['category']}</td></tr>"
            for i, r in enumerate(roles, 1)
        ) or '<tr><td colspan="4" class="empty">Ролей ещё нет 🎮</td></tr>'

        html = f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>⚽ Панель Админа — OZMZ</title>
<style>
*{{box-sizing:border-box;margin:0;padding:0}}
body{{font-family:-apple-system,sans-serif;background:#0e1a12;color:#f5f5f0;min-height:100vh;padding:24px}}
.header{{display:flex;align-items:center;gap:12px;margin-bottom:28px}}
.header h1{{font-size:22px;font-weight:700}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}}
.stat{{background:#1e3024;border:1px solid rgba(126,217,87,.15);border-radius:12px;padding:16px}}
.stat-num{{font-size:30px;font-weight:700;color:#7ed957}}
.stat-label{{font-size:13px;color:#6b7c6e;margin-top:4px}}
.section{{background:#1e3024;border:1px solid rgba(126,217,87,.15);border-radius:12px;padding:16px;margin-bottom:16px}}
.section h2{{font-size:15px;color:#7ed957;margin-bottom:4px}}
.table-wrap{{background:#1e3024;border:1px solid rgba(126,217,87,.15);border-radius:12px;overflow:hidden}}
table{{width:100%;border-collapse:collapse}}
th{{background:rgba(126,217,87,.1);padding:10px 14px;text-align:left;font-size:11px;color:#7ed957;letter-spacing:1px;text-transform:uppercase}}
td{{padding:10px 14px;border-top:1px solid rgba(255,255,255,.05);font-size:13px}}
tr:hover td{{background:rgba(255,255,255,.03)}}
.badge{{background:rgba(126,217,87,.15);color:#7ed957;padding:2px 7px;border-radius:5px;font-size:11px;font-weight:600}}
.empty{{text-align:center;padding:40px;color:#6b7c6e}}
.refresh{{margin-top:14px;text-align:center}}
.refresh a{{color:#7ed957;text-decoration:none;font-size:13px}}
</style>
</head>
<body>
<div class="header">
  <img src="/logo.jpg" style="width:44px;height:44px;border-radius:50%;object-fit:cover;border:2px solid #7ed957">
  <h1>Панель Админа — OZMZ Football</h1>
</div>
<div class="stats">
  <div class="stat"><div class="stat-num">{len(users)}</div><div class="stat-label">Пользователей</div></div>
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Тестов пройдено</div></div>
  <div class="stat"><div class="stat-num">{len(players)}</div><div class="stat-label">Разных футболистов</div></div>
  <div class="stat"><div class="stat-num">{now_astana().strftime('%H:%M')}</div><div class="stat-label">Время (AST)</div></div>
</div>
{predict_block}

<div class="section"><h2>📱 Пользователи (номера скрыты, кроме последних 4 цифр)</h2></div>
<div class="table-wrap" style="margin-bottom:16px">
  <table>
    <thead><tr><th>#</th><th>Имя</th><th>Ник</th><th>Username</th><th>Телефон</th><th>Дата регистрации</th></tr></thead>
    <tbody>{users_rows}</tbody>
  </table>
</div>

<div class="section"><h2>🏆 Роли игроков (для /teams)</h2></div>
<div class="table-wrap" style="margin-bottom:16px">
  <table>
    <thead><tr><th>#</th><th>Имя</th><th>Футболист</th><th>Категория</th></tr></thead>
    <tbody>{roles_rows}</tbody>
  </table>
</div>

<div class="section"><h2>🎮 История квизов</h2></div>
<div class="table-wrap">
  <table>
    <thead><tr><th>#</th><th>Игрок</th><th>Футболист</th><th>Дата и время</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</div>
<div class="refresh"><a href="/">↻ Обновить</a></div>
</body></html>"""

        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(html.encode("utf-8"))


def run():
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"  Admin panel: http://0.0.0.0:{PORT}")
    httpd.serve_forever()


def start_background():
    t = threading.Thread(target=run, daemon=True)
    t.start()
