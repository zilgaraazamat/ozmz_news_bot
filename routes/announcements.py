"""Анонсы/новости: создание, публикация, удаление (админ) и лента (все)."""
import json

from api import tg_post
from config import ADMIN_IDS, CHAT_ID
from storage import (
    create_announcement, get_active_announcements, get_all_announcements,
    delete_announcement, publish_announcement,
)


class AnnouncementsRoutesMixin:
    def route_post_admin_create_announcement(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            title = (data.get("title") or "").strip()
            text = (data.get("text") or "").strip()
            category = (data.get("category") or "Анонс").strip()
            event_date = (data.get("event_date") or "").strip() or None
            published = data.get("published", True)
            image = data.get("image") or None
            if image and "," in image and image.strip().startswith("data:"):
                image = image.split(",", 1)[1]
            if image and len(image) > 900_000:
                self._json({"ok": False, "error": "Фото слишком большое, выбери другое"})
                return
            if not title or not text:
                self._json({"ok": False, "error": "Заполни заголовок и текст"})
                return

            create_announcement(title, text, admin_id, image, category, event_date, published)

            if published:
                group_text = f"📢 <b>{category}: {title}</b>\n\n{text}"
                tg_post(CHAT_ID, "sendMessage", text=group_text, parse_mode="HTML")

            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] create-announcement: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_publish_announcement(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            ann_id = data.get("id")
            items = [a for a in get_all_announcements() if a["id"] == ann_id]
            publish_announcement(ann_id)
            if items:
                a = items[0]
                group_text = f"📢 <b>{a['category'] or 'Анонс'}: {a['title']}</b>\n\n{a['text']}"
                tg_post(CHAT_ID, "sendMessage", text=group_text, parse_mode="HTML")
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] publish-announcement: {e}")
            self.send_response(400); self.end_headers()


    def route_post_admin_delete_announcement(self, body):
        try:
            data = json.loads(body)
            admin_id = str(data.get("user_id", ""))
            if admin_id not in ADMIN_IDS:
                self._json({"ok": False, "error": "Нет прав администратора"})
                return
            delete_announcement(data.get("id"))
            self._json({"ok": True})
        except Exception as e:
            print(f"  [WARN] delete-announcement: {e}")
            self.send_response(400); self.end_headers()

    def route_get_announcements(self, q):
        self._json({"announcements": get_active_announcements(10)})

    def route_get_admin_announcements(self, q):
        user_id = (q.get("user_id") or [""])[0]
        if user_id not in ADMIN_IDS:
            self._json({"error": "forbidden"})
        else:
            self._json({"announcements": get_all_announcements()})
