"""Отдача статических страниц webapp/* и лёгкой служебной HTML-панели на "/"
(таблицы пользователей/квизов/ролей — не путать с полноценным /admin)."""
from api import now_astana
from predict import get_stats as predict_stats
from storage import get_quiz_history, get_all_users, get_all_roles, get_profile, display_name_from_profile


class StaticRoutesMixin:
    def route_get_app_page(self, q):
        self._file("webapp/app.html", "text/html; charset=utf-8")

    def route_get_quiz_page(self, q):
        self._file("webapp/index.html", "text/html; charset=utf-8")

    def route_get_battle_page(self, q):
        self._file("webapp/battle.html", "text/html; charset=utf-8")

    def route_get_admin_page(self, q):
        self._file("webapp/admin.html", "text/html; charset=utf-8")

    def route_get_games_page(self, q):
        self._file("webapp/games.html", "text/html; charset=utf-8")

    def route_get_scanner_page(self, q):
        self._file("webapp/scanner.html", "text/html; charset=utf-8")

    def route_get_player_page(self, q):
        self._file("webapp/player.html", "text/html; charset=utf-8")

    def route_get_logo(self, q):
        self._file("webapp/logo.jpg", "image/jpeg")

    def route_get_root_admin_html(self, q):
        self._admin_html()

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
  <p style="color:#9BA1AC;margin:8px 0">Участников: <b style="color:#8B93F5">{ps['total_predictions']}</b></p>
  <div style="display:flex;gap:8px;margin-top:12px">
    <input id="score-input" placeholder="2:1" style="padding:8px 12px;border-radius:10px;border:1px solid rgba(255,255,255,.08);background:#23262D;color:#F5F6F7;font-size:14px">
    <button onclick="announceResult()" style="padding:8px 16px;background:#5E6AD2;color:#fff;border:none;border-radius:10px;font-weight:700;cursor:pointer">Объявить итог</button>
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
            f"<tr><td>{i}</td><td>{display_name_from_profile(get_profile(h['user_id'])) if h.get('user_id') else (h['name'] or 'Игрок')}</td>"
            f"<td><span class='badge'>{h['player']}</span></td>"
            f"<td>{h['date']}</td></tr>"
            for i, h in enumerate(reversed(quiz_history), 1)
        ) or '<tr><td colspan="4" class="empty">Тестов ещё не было 🎮</td></tr>'

        users_rows = "".join(
            f"<tr><td>{i}</td><td>{display_name_from_profile(u)}</td>"
            f"<td>{('@' + u['username']) if u.get('username') else '—'}</td>"
            f"<td>{mask_phone(u['phone'])}</td><td>{u['joined_at']}</td></tr>"
            for i, u in enumerate(users, 1)
        ) or '<tr><td colspan="5" class="empty">Пока никто не заходил 👀</td></tr>'

        roles_rows = "".join(
            f"<tr><td>{i}</td><td>{display_name_from_profile(get_profile(r['user_id'])) if r.get('user_id') else (r['name'] or 'Игрок')}</td>"
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
body{{font-family:-apple-system,sans-serif;background:#0B0D10;color:#F5F6F7;min-height:100vh;padding:24px}}
.header{{display:flex;align-items:center;gap:12px;margin-bottom:28px}}
.header h1{{font-size:22px;font-weight:700}}
.stats{{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:20px}}
.stat{{background:#181A1F;border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:16px}}
.stat-num{{font-size:30px;font-weight:700;color:#8B93F5}}
.stat-label{{font-size:13px;color:#9BA1AC;margin-top:4px}}
.section{{background:#181A1F;border:1px solid rgba(255,255,255,.06);border-radius:16px;padding:16px;margin-bottom:16px}}
.section h2{{font-size:15px;color:#8B93F5;margin-bottom:4px}}
.table-wrap{{background:#181A1F;border:1px solid rgba(255,255,255,.06);border-radius:16px;overflow:hidden}}
table{{width:100%;border-collapse:collapse}}
th{{background:rgba(94,106,210,.1);padding:10px 14px;text-align:left;font-size:11px;color:#8B93F5;letter-spacing:1px;text-transform:uppercase}}
td{{padding:10px 14px;border-top:1px solid rgba(255,255,255,.05);font-size:13px;color:#D7D9DC}}
tr:hover td{{background:rgba(255,255,255,.03)}}
.badge{{background:rgba(94,106,210,.15);color:#8B93F5;padding:2px 7px;border-radius:5px;font-size:11px;font-weight:600}}
.empty{{text-align:center;padding:40px;color:#6B7280}}
.refresh{{margin-top:14px;text-align:center}}
.refresh a{{color:#8B93F5;text-decoration:none;font-size:13px}}
</style>
</head>
<body>
<div class="header">
  <img src="/logo.jpg" style="width:44px;height:44px;border-radius:50%;object-fit:cover;border:2px solid #5E6AD2">
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
    <thead><tr><th>#</th><th>Игрок</th><th>Username</th><th>Телефон</th><th>Дата регистрации</th></tr></thead>
    <tbody>{users_rows}</tbody>
  </table>
</div>

<div class="section"><h2>🏆 Роли игроков (для /teams)</h2></div>
<div class="table-wrap" style="margin-bottom:16px">
  <table>
    <thead><tr><th>#</th><th>Игрок</th><th>Футболист</th><th>Категория</th></tr></thead>
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
