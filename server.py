import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from api import now_astana, tg_post
from config import PORT
from storage import (
    get_quiz_history, add_quiz_history, get_all_users, get_all_roles,
    get_profile, set_nickname, get_role,
)
from predict import get_stats as predict_stats, announce_result
from battle import create_battle, join_battle, get_state, submit_answer


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
        length = int(self.headers.get("Content-Length", 0))
        body   = self.rfile.read(length)

        if self.path == "/api/quiz-result":
            try:
                data = json.loads(body)
                add_quiz_history(
                    data.get("name", "Аноним"),
                    data.get("player", "Неизвестно"),
                    now_astana().strftime("%d.%m.%Y %H:%M"),
                    "web",
                )
                print(f"  [WEB QUIZ] {data.get('name')} → {data.get('player')}")
                self._json({"ok": True})
            except Exception as e:
                print(f"  [WARN] quiz-result: {e}")
                self.send_response(400); self.end_headers()

        elif self.path == "/api/predict-result":
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

        elif self.path == "/api/battle/create":
            try:
                data = json.loads(body)
                name = (data.get("name") or "Игрок")[:20]
                code, player_id = create_battle(name)
                self._json({"code": code, "player_id": player_id})
            except Exception as e:
                print(f"  [WARN] battle/create: {e}")
                self.send_response(400); self.end_headers()

        elif self.path == "/api/battle/join":
            try:
                data = json.loads(body)
                code = (data.get("code") or "")[:8]
                name = (data.get("name") or "Игрок")[:20]
                player_id, error = join_battle(code, name)
                if error:
                    self._json({"error": error})
                else:
                    self._json({"player_id": player_id})
            except Exception as e:
                print(f"  [WARN] battle/join: {e}")
                self.send_response(400); self.end_headers()

        elif self.path == "/api/battle/answer":
            try:
                data      = json.loads(body)
                code      = data.get("code", "")
                player_id = data.get("player_id", "")
                answer    = data.get("answer", "")
                result = submit_answer(code, player_id, answer)
                self._json(result if result else {"error": "invalid"})
            except Exception as e:
                print(f"  [WARN] battle/answer: {e}")
                self.send_response(400); self.end_headers()

        elif self.path == "/api/profile":
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

        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        if self.path == "/app":
            self._file("webapp/app.html", "text/html; charset=utf-8")
        elif self.path == "/quiz":
            self._file("webapp/index.html", "text/html; charset=utf-8")
        elif self.path == "/battle":
            self._file("webapp/battle.html", "text/html; charset=utf-8")
        elif self.path == "/profile":
            self._file("webapp/profile.html", "text/html; charset=utf-8")
        elif self.path == "/logo.jpg":
            self._file("webapp/logo.jpg", "image/jpeg")
        elif self.path == "/api/stats":
            stats = predict_stats()
            self._json(stats)
        elif self.path.startswith("/api/battle/state"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            code = (q.get("code") or [""])[0]
            player_id = (q.get("player_id") or [""])[0]
            state = get_state(code, player_id)
            self._json(state if state else {"error": "not_found"})
        elif self.path.startswith("/api/profile"):
            from urllib.parse import urlparse, parse_qs
            q = parse_qs(urlparse(self.path).query)
            user_id = (q.get("user_id") or [""])[0]
            profile = get_profile(user_id)
            role = get_role(user_id)
            self._json({
                "name": profile["name"] if profile else None,
                "nickname": profile["nickname"] if profile else None,
                "role": role,
            })
        elif self.path == "/":
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
            f"<tr><td>{i}</td><td>{u['name']}</td><td>{mask_phone(u['phone'])}</td><td>{u['joined_at']}</td></tr>"
            for i, u in enumerate(users, 1)
        ) or '<tr><td colspan="4" class="empty">Пока никто не заходил 👀</td></tr>'

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
    <thead><tr><th>#</th><th>Имя</th><th>Телефон</th><th>Дата регистрации</th></tr></thead>
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
