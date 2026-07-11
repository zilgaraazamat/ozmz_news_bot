"""Профиль игрока: ник/номер футболки (свой), публичный профиль (чужой),
проверка админских прав."""
import json

from config import ADMIN_IDS
from storage import (
    get_profile, set_nickname, set_jersey_number, get_role,
    get_progression, settle_completed_games_xp, display_name_from_profile, get_history_games,
    get_player_stats,
)


class ProfileRoutesMixin:
    def route_post_profile(self, body):
        try:
            data     = json.loads(body)
            user_id  = str(data.get("user_id", ""))
            has_nickname = "nickname" in data
            has_jersey   = "jersey_number" in data
            if not user_id or not (has_nickname or has_jersey):
                self._json({"ok": False, "error": "bad_request"})
                return
            if has_nickname:
                nickname = (data.get("nickname") or "").strip()[:24]
                if not nickname:
                    self._json({"ok": False, "error": "bad_request"})
                    return
                set_nickname(user_id, nickname)
            if has_jersey:
                try:
                    jersey_number = int(data.get("jersey_number"))
                except (TypeError, ValueError):
                    self._json({"ok": False, "error": "invalid_number"})
                    return
                if jersey_number < 0 or jersey_number > 99:
                    self._json({"ok": False, "error": "invalid_number"})
                    return
                set_jersey_number(user_id, jersey_number)
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] profile: {e}")
            self.send_response(400); self.end_headers()


    def route_get_is_admin(self, q):
        user_id = (q.get("user_id") or [""])[0]
        self._json({"is_admin": user_id in ADMIN_IDS})

    def route_get_profile(self, q):
        user_id = (q.get("user_id") or [""])[0]
        profile = get_profile(user_id)
        role = get_role(user_id)
        stats = get_player_stats(user_id) if user_id else {"games_played": 0, "goals": 0, "mvp_count": 0, "ovr": 60}
        if user_id:
            settle_completed_games_xp(user_id)  # начислить XP за игры, завершившиеся с прошлого визита
        progression = get_progression(user_id)
        self._json({
            "name": profile["name"] if profile else None,
            "nickname": profile["nickname"] if profile else None,
            "jersey_number": profile["jersey_number"] if profile else None,
            "role": role,
            "games_played": stats["games_played"],
            "goals": stats["goals"],
            "mvp_count": stats["mvp_count"],
            "level": progression["level"],
            "xp": progression["xp"],
            "ovr": stats["ovr"],
            "xp_for_next_level": progression["xp_for_next_level"],
            "xp_progress_pct": progression["xp_progress_pct"],
        })

    def route_get_player_profile(self, q):
        # Публичный профиль — доступен всем, без проверки владения.
        target_id = (q.get("user_id") or [""])[0]
        if not target_id:
            self._json({"error": "user_id required"})
        else:
            profile = get_profile(target_id)
            role = get_role(target_id)
            display_name = display_name_from_profile(profile)
            recent = get_history_games(target_id)[:5]
            recent_out = [{
                "id": g["id"], "date": g["date"], "time": g["time"], "location": g["location"],
            } for g in recent]
            settle_completed_games_xp(target_id)  # начислить XP за игры, завершившиеся с прошлого визита
            progression = get_progression(target_id)
            stats = get_player_stats(target_id)
            self._json({
                "user_id": target_id,
                "name": display_name,
                "role": role,
                "games_played": stats["games_played"],
                "goals": stats["goals"],
                "mvp_count": stats["mvp_count"],
                "recent_matches": recent_out,
                "level": progression["level"],
                "xp": progression["xp"],
                "ovr": stats["ovr"],
                "xp_for_next_level": progression["xp_for_next_level"],
                "xp_progress_pct": progression["xp_progress_pct"],
                "mvp_implemented": True,
                "achievements_implemented": False,
            })
