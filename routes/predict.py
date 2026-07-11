"""Конкурс прогнозов на счёт матча — приём итогового счёта и статистика."""
import json

from predict import get_stats as predict_stats, announce_result


class PredictRoutesMixin:
    def route_post_predict_result(self, body):
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


    def route_get_stats(self, q):
        stats = predict_stats()
        self._json(stats)
