import os
import json
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from api import now_astana, tg_post
from config import PORT
from quiz import quiz_history
from predict import get_stats as predict_stats, announce_result


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
                quiz_history.append({
                    "name":    data.get("name", "Аноним"),
                    "player":  data.get("player", "Неизвестно"),
                    "date":    now_astana().strftime("%d.%m.%Y %H:%M"),
                    "user_id": "web",
                })
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
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        if self.path == "/quiz":
            self._file("webapp/index.html", "text/html; charset=utf-8")
        elif self.path == "/logo.jpg":
            self._file("webapp/logo.jpg", "image/jpeg")
        elif self.path == "/api/stats":
            stats = predict_stats()
            self._json(stats)
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
            self.end_headers()
            self.wfile.write(data)
        except FileNotFoundError:
            self.send_response(404); self.end_headers()

    def _admin_html(self):
        total   = len(quiz_history)
        players = {}
        for h in quiz_history:
            players[h["player"]] = players.get(h["player"], 0) + 1
        top_player = max(players, key=players.get) if players else "—"

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
  <div class="stat"><div class="stat-num">{total}</div><div class="stat-label">Тестов пройдено</div></div>
  <div class="stat"><div class="stat-num">{len(players)}</div><div class="stat-label">Разных футболистов</div></div>
  <div class="stat"><div class="stat-num" style="font-size:16px">{top_player}</div><div class="stat-label">Самый популярный</div></div>
  <div class="stat"><div class="stat-num">{now_astana().strftime('%H:%M')}</div><div class="stat-label">Время (AST)</div></div>
</div>
{predict_block}
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
