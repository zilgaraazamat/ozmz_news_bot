"""Викторина-баттл 1x1 между игроками."""
import json

from battle import create_battle, join_battle, get_state, submit_answer, list_open_battles
from .helpers import _display_name


class BattleRoutesMixin:
    def route_post_battle_create(self, body):
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


    def route_post_battle_join(self, body):
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


    def route_post_battle_answer(self, body):
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


    def route_get_battle_list(self, q):
        self._json({"battles": list_open_battles()})

    def route_get_battle_state(self, q):
        battle_id = (q.get("battle_id") or [""])[0]
        user_id = (q.get("user_id") or [""])[0]
        state = get_state(battle_id, user_id)
        self._json(state if state else {"error": "not_found"})
