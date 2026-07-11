"""Приём результата веб-квиза «Кто ты из футболистов?»."""
import json

from api import now_astana
from config import PLAYER_CATEGORIES
from storage import add_quiz_history, set_role


class QuizRoutesMixin:
    def route_post_quiz_result(self, body):
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

