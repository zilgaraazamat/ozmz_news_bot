"""Отчёт о завершённом матче — эндпоинт только для чтения.

Не трогает ничего из существующего флоу игры/регистрации/команд — просто
отдаёт то, что уже посчитал storage.match_report.get_match_report()."""
from storage import get_match_report


class MatchReportRoutesMixin:
    def route_get_match_report_page(self, q):
        self._file("webapp/match-report.html", "text/html; charset=utf-8")

    def route_get_match_report(self, q):
        game_id = (q.get("game_id") or [""])[0]
        user_id = (q.get("user_id") or [""])[0]
        if not game_id:
            self._json({"error": "game_id required"})
            return
        try:
            game_id = int(game_id)
        except (TypeError, ValueError):
            self._json({"error": "invalid game_id"})
            return

        report = get_match_report(game_id, viewer_user_id=user_id or None)
        if report is None:
            self._json({"error": "not_found_or_not_completed"})
        else:
            self._json(report)
