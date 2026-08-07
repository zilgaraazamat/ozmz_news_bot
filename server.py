"""HTTP-сервер приложения: собирает Handler из route-миксинов (routes/*) и
диспетчеризует запросы по словарям путь → имя метода. Сама бизнес-логика
эндпоинтов живёт в routes/* — этот файл только связывает всё воедино и
поднимает сервер (см. run()/start_background(), которые вызывает bot.py)."""
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

from config import PORT
from routes.base import BaseRoutesMixin
from routes.quiz import QuizRoutesMixin
from routes.predict import PredictRoutesMixin
from routes.battle import BattleRoutesMixin
from routes.profile import ProfileRoutesMixin
from routes.games import GamesRoutesMixin
from routes.admin_games import AdminGamesRoutesMixin
from routes.announcements import AnnouncementsRoutesMixin
from routes.scanner import ScannerRoutesMixin
from routes.static_pages import StaticRoutesMixin
from routes.match_report import MatchReportRoutesMixin
from routes.tournaments import TournamentRoutesMixin


# путь → имя метода на Handler'е. Смысл и поведение каждого эндпоинта не
# менялись при разбиении server.py на модули — только расположение кода.
POST_ROUTES = {
    "/api/quiz-result":                 "route_post_quiz_result",
    "/api/predict-result":              "route_post_predict_result",
    "/api/battle/create":               "route_post_battle_create",
    "/api/battle/join":                 "route_post_battle_join",
    "/api/battle/answer":               "route_post_battle_answer",
    "/api/profile":                     "route_post_profile",
    "/api/admin/create-game":           "route_post_admin_create_game",
    "/api/admin/create-game-template":  "route_post_admin_create_game_template",
    "/api/admin/update-game-template":  "route_post_admin_update_game_template",
    "/api/admin/delete-game-template":  "route_post_admin_delete_game_template",
    "/api/games/signup":                "route_post_games_signup",
    "/api/games/cancel-signup":         "route_post_games_cancel_signup",
    "/api/games/claim-payment":         "route_post_games_claim_payment",
    "/api/games/claim-invite":          "route_post_games_claim_invite",
    "/api/tournament/register":         "route_post_tournament_register",
    "/api/tournament/claim-payment":    "route_post_tournament_claim_payment",
    "/api/tournament/cancel-team":      "route_post_tournament_cancel_team",
    "/api/admin/save-tournament":       "route_post_admin_save_tournament",
    "/api/admin/delete-tournament":     "route_post_admin_delete_tournament",
    "/api/admin/confirm-team":          "route_post_admin_confirm_team",
    "/api/admin/set-tournament-status": "route_post_admin_set_tournament_status",
    "/api/admin/set-team-group":        "route_post_admin_set_team_group",
    "/api/admin/distribute-groups":     "route_post_admin_distribute_groups",
    "/api/admin/generate-cup-semifinals": "route_post_admin_generate_cup_semifinals",
    "/api/admin/save-tournament-match": "route_post_admin_save_tournament_match",
    "/api/admin/tournament-match-result": "route_post_admin_tournament_match_result",
    "/api/admin/delete-tournament-match": "route_post_admin_delete_tournament_match",
    "/api/scanner/analyze":             "route_post_scanner_analyze",
    "/api/games/chat/send":             "route_post_games_chat_send",
    "/api/admin/confirm-signup":        "route_post_admin_confirm_signup",
    "/api/admin/move-team-member":      "route_post_admin_move_team_member",
    "/api/admin/cancel-game":           "route_post_admin_cancel_game",
    "/api/admin/complete-game":         "route_post_admin_complete_game",
    "/api/admin/complete-match":        "route_post_admin_complete_match",
    "/api/admin/save-match-stats":      "route_post_admin_save_match_stats",
    "/api/admin/delete-game":           "route_post_admin_delete_game",
    "/api/admin/create-announcement":   "route_post_admin_create_announcement",
    "/api/admin/publish-announcement":  "route_post_admin_publish_announcement",
    "/api/admin/delete-announcement":   "route_post_admin_delete_announcement",
}

GET_ROUTES = {
    "/app":                     "route_get_app_page",
    "/quiz":                    "route_get_quiz_page",
    "/battle":                  "route_get_battle_page",
    "/admin":                   "route_get_admin_page",
    "/games":                   "route_get_games_page",
    "/scanner":                 "route_get_scanner_page",
    "/player":                  "route_get_player_page",
    "/api/is-admin":            "route_get_is_admin",
    "/api/announcements":       "route_get_announcements",
    "/api/admin/announcements": "route_get_admin_announcements",
    "/api/games":               "route_get_games",
    "/api/games/chat":          "route_get_games_chat",
    "/api/games/invites":       "route_get_games_invites",
    "/api/tournaments":         "route_get_tournaments",
    "/api/tournament":          "route_get_tournament",
    "/api/admin/tournaments":   "route_get_admin_tournaments",
    "/tournament":              "route_get_tournament_page",
    "/tournaments":             "route_get_tournaments_page",
    "/api/admin/game-templates":"route_get_admin_game_templates",
    "/api/admin/games":         "route_get_admin_games",
    "/api/admin/users":         "route_get_admin_users",
    "/api/admin/awaiting-results": "route_get_admin_awaiting_results",
    "/logo.jpg":                "route_get_logo",
    "/api/stats":               "route_get_stats",
    "/api/battle/list":         "route_get_battle_list",
    "/api/battle/state":        "route_get_battle_state",
    "/api/profile":             "route_get_profile",
    "/api/player-profile":      "route_get_player_profile",
    "/api/leaderboard":         "route_get_leaderboard",
    "/match-report":            "route_get_match_report_page",
    "/api/match-report":        "route_get_match_report",
    "/":                        "route_get_root_admin_html",
}


class Handler(
    BaseRoutesMixin,
    QuizRoutesMixin,
    PredictRoutesMixin,
    BattleRoutesMixin,
    ProfileRoutesMixin,
    GamesRoutesMixin,
    AdminGamesRoutesMixin,
    AnnouncementsRoutesMixin,
    ScannerRoutesMixin,
    StaticRoutesMixin,
    MatchReportRoutesMixin,
    TournamentRoutesMixin,
    BaseHTTPRequestHandler,
):
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

        handler_name = POST_ROUTES.get(path)
        if handler_name:
            getattr(self, handler_name)(body)
        else:
            self.send_response(404); self.end_headers()

    def do_GET(self):
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(self.path)
        path = parsed.path
        q = parse_qs(parsed.query)

        handler_name = GET_ROUTES.get(path)
        if handler_name:
            getattr(self, handler_name)(q)
        else:
            self.send_response(404); self.end_headers()


def run():
    httpd = HTTPServer(("0.0.0.0", PORT), Handler)
    print(f"  Admin panel: http://0.0.0.0:{PORT}")
    httpd.serve_forever()


def start_background():
    t = threading.Thread(target=run, daemon=True)
    t.start()
