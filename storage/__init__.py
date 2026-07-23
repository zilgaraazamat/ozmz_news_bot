"""storage — доступ к SQLite для всего приложения, разбитый на модули по
предметной области. Раньше это был один файл storage.py; поведение и SQL
не менялись, изменилась только организация кода.

Этот __init__.py переэкспортирует все публичные имена, которые раньше жили
в storage.py, так что весь остальной код (`from storage import X`) продолжает
работать без изменений — менять ничего в bot.py/server.py/teams.py/quiz.py/
predict.py/api.py не нужно.
"""

from ._db import init_db

from .roles import (
    get_role, set_role, get_roles_bulk, get_all_roles,
)

from .quiz_history import (
    add_quiz_history, get_quiz_history,
)

from .news_dedup import (
    is_news_sent, mark_news_sent,
)

from .predict import (
    save_predict_match, set_predict_message_id, set_predict_active, get_predict_match,
    add_prediction, get_predictions, clear_predictions,
)

from .users import (
    has_phone, save_phone, get_user, get_all_users, get_profile,
    display_name_from_profile, get_display_name,
    set_nickname, set_jersey_number, save_username, get_username,
)

from .game_status import (
    MATCH_DURATION_HOURS, is_match_completed, is_awaiting_results,
)

from .pricing import (
    price_per_player, entry_amount,
)

from .games import (
    mark_game_completed, get_games_played_count,
    create_game, get_all_games, cancel_game, delete_game, get_active_games,
    get_history_games, get_game, get_completed_match_dates, get_games_awaiting_results,
)

from .leaderboards import get_leaderboard, CATEGORIES as LEADERBOARD_CATEGORIES

from .game_templates import (
    create_game_template, get_game_templates, get_game_template,
    update_game_template, delete_game_template,
)

from .signups import (
    signup_for_game, get_signups, get_my_signups, mark_payment_claimed,
    get_my_signup, cancel_signup, confirm_signup,
)

from .invites import (
    create_invites_for_signup, get_invites_for_signup, get_invite,
    claim_invite, get_claimed_slots,
)

from .progression import (
    DEFAULT_LEVEL, DEFAULT_XP, XP_PER_COMPLETED_GAME,
    xp_required_for_level, get_progression, award_xp, settle_completed_games_xp,
)

from .teams_slots import (
    get_team_members, clear_game_teams, add_team_member, move_team_member,
)

from .chat import (
    is_registered_for_game, add_chat_message, get_chat_messages,
)

from .announcements import (
    create_announcement, publish_announcement, get_active_announcements,
    get_all_announcements, delete_announcement,
)

from .match_stats import (
    STAT_FIELDS,
    record_match_stat, get_match_stats, get_player_match_stats,
    get_player_stat_in_match, delete_match_stats, get_career_totals,
    normalize_player_stats, record_match_stats_bulk,
)

from .match_completion import complete_match

from .match_report import get_match_report

from .player_stats import get_player_stats, get_players_stats_bulk

from .ovr import calculate_ovr, BASE_OVR

from .streak import calculate_weekly_streak, get_weekly_streak

from .achievements import (
    ACHIEVEMENTS, calculate_achievements, get_player_achievements, get_achievements_summary,
)

__all__ = [
    "init_db",
    "get_role", "set_role", "get_roles_bulk", "get_all_roles",
    "add_quiz_history", "get_quiz_history",
    "is_news_sent", "mark_news_sent",
    "save_predict_match", "set_predict_message_id", "set_predict_active", "get_predict_match",
    "add_prediction", "get_predictions", "clear_predictions",
    "has_phone", "save_phone", "get_user", "get_all_users", "get_profile",
    "display_name_from_profile", "get_display_name",
    "set_nickname", "set_jersey_number", "save_username", "get_username",
    "MATCH_DURATION_HOURS", "is_match_completed", "is_awaiting_results",
    "mark_game_completed", "get_games_played_count",
    "create_game", "get_all_games", "cancel_game", "delete_game", "get_active_games",
    "get_history_games", "get_game", "get_completed_match_dates", "get_games_awaiting_results",
    "get_leaderboard", "LEADERBOARD_CATEGORIES",
    "create_game_template", "get_game_templates", "get_game_template",
    "update_game_template", "delete_game_template",
    "signup_for_game", "get_signups", "get_my_signups", "mark_payment_claimed",
    "get_my_signup", "cancel_signup", "confirm_signup",
    "DEFAULT_LEVEL", "DEFAULT_XP", "XP_PER_COMPLETED_GAME",
    "xp_required_for_level", "get_progression", "award_xp", "settle_completed_games_xp",
    "get_team_members", "clear_game_teams", "add_team_member", "move_team_member",
    "is_registered_for_game", "add_chat_message", "get_chat_messages",
    "create_announcement", "publish_announcement", "get_active_announcements",
    "get_all_announcements", "delete_announcement",
    "STAT_FIELDS",
    "record_match_stat", "get_match_stats", "get_player_match_stats",
    "get_player_stat_in_match", "delete_match_stats", "get_career_totals",
    "normalize_player_stats", "record_match_stats_bulk",
    "complete_match",
    "get_match_report",
    "get_player_stats", "get_players_stats_bulk",
    "calculate_ovr", "BASE_OVR",
    "calculate_weekly_streak", "get_weekly_streak",
    "ACHIEVEMENTS", "calculate_achievements", "get_player_achievements", "get_achievements_summary",
]
