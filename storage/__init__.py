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
    MATCH_DURATION_HOURS, is_match_completed,
)

from .games import (
    mark_game_completed, get_games_played_count, get_leaderboard_most_games,
    create_game, get_all_games, cancel_game, delete_game, get_active_games,
    get_history_games, get_game,
)

from .game_templates import (
    create_game_template, get_game_templates, get_game_template,
    update_game_template, delete_game_template,
)

from .signups import (
    signup_for_game, get_signups, get_my_signups, mark_payment_claimed,
    get_my_signup, cancel_signup, confirm_signup,
)

from .progression import (
    DEFAULT_LEVEL, DEFAULT_XP, DEFAULT_OVR, XP_PER_COMPLETED_GAME,
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
    get_player_stat_in_match, delete_match_stats,
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
    "MATCH_DURATION_HOURS", "is_match_completed",
    "mark_game_completed", "get_games_played_count", "get_leaderboard_most_games",
    "create_game", "get_all_games", "cancel_game", "delete_game", "get_active_games",
    "get_history_games", "get_game",
    "create_game_template", "get_game_templates", "get_game_template",
    "update_game_template", "delete_game_template",
    "signup_for_game", "get_signups", "get_my_signups", "mark_payment_claimed",
    "get_my_signup", "cancel_signup", "confirm_signup",
    "DEFAULT_LEVEL", "DEFAULT_XP", "DEFAULT_OVR", "XP_PER_COMPLETED_GAME",
    "xp_required_for_level", "get_progression", "award_xp", "settle_completed_games_xp",
    "get_team_members", "clear_game_teams", "add_team_member", "move_team_member",
    "is_registered_for_game", "add_chat_message", "get_chat_messages",
    "create_announcement", "publish_announcement", "get_active_announcements",
    "get_all_announcements", "delete_announcement",
    "STAT_FIELDS",
    "record_match_stat", "get_match_stats", "get_player_match_stats",
    "get_player_stat_in_match", "delete_match_stats",
]
