"""
🎯 УГАДАЙ СЧЁТ — вирусная механика

Как работает:
1. Утром бот постит матч + просит прогнозы (/счёт 2:1)
2. Пользователи пишут боту прогноз
3. Вечером (или вручную) бот объявляет победителей

Состояние конкурса живёт в SQLite (storage.py) — переживает рестарт бота.
"""
import re
from api import now_astana, tg_post, send_msg, from_config
from storage import (
    save_predict_match, set_predict_message_id, set_predict_active,
    get_predict_match, add_prediction, get_predictions, clear_predictions,
)


def start_prediction(match):
    """Постим матч в группу и открываем приём прогнозов."""
    clear_predictions()
    save_predict_match(match, message_id=None, active=True)

    text = (
        f"🎯 <b>УГАДАЙ СЧЁТ — выиграй упоминание!</b>\n\n"
        f"⚽ <b>{match['home']} — {match['away']}</b>\n"
        f"🕐 {match['time']} AST | {match['comp']}\n\n"
        f"Напиши боту свой прогноз:\n"
        f"<code>/счёт 2:1</code>\n\n"
        f"🏆 Угадавших назовём после матча!\n"
        f"👥 @football_igraem_astana"
    )

    chat_id = from_config("CHAT_ID")
    result = tg_post(chat_id, "sendMessage", text=text, parse_mode="HTML")
    if result and result.get("ok"):
        set_predict_message_id(result["result"]["message_id"])
    print(f"  [PREDICT] Contest started for {match['home']} vs {match['away']}")


def handle_prediction(user_id, user_name, text):
    """Обрабатываем /счёт X:Y от пользователя."""
    match, active, _ = get_predict_match()
    if not active or not match:
        send_msg(user_id, "⚽ Сейчас нет активного конкурса прогнозов. Приходи утром!")
        return

    m = re.search(r"(\d{1,2})\s*[:–-]\s*(\d{1,2})", text)
    if not m:
        send_msg(user_id,
                 "❌ Формат: <code>/счёт 2:1</code>\n"
                 "Напиши счёт через двоеточие, например 2:1 или 0:0")
        return

    score = f"{m.group(1)}:{m.group(2)}"
    add_prediction(user_id, user_name, score)

    send_msg(user_id,
             f"✅ Принял твой прогноз!\n\n"
             f"⚽ {match['home']} — {match['away']}\n"
             f"🔮 Твой счёт: <b>{score}</b>\n\n"
             f"Следи за результатом в @football_igraem_astana 👀")
    print(f"  [PREDICT] {user_name} → {score}")


def announce_result(real_score: str):
    """Вызывается когда стал известен реальный счёт. Постит итоги в группу."""
    match, active, _ = get_predict_match()
    if not active or not match:
        return

    preds = get_predictions()
    winners = [p["name"] for p in preds.values() if p["score"] == real_score]
    total = len(preds)

    if winners:
        w_text = ", ".join(f"<b>{w}</b>" for w in winners)
        result_text = (
            f"🏆 <b>ИТОГИ КОНКУРСА ПРОГНОЗОВ</b>\n\n"
            f"⚽ {match['home']} — {match['away']}\n"
            f"📊 Реальный счёт: <b>{real_score}</b>\n\n"
            f"🥇 Угадали ({len(winners)} из {total}):\n"
            f"{w_text}\n\n"
            f"🔥 Красавцы! Играете с нами? @football_igraem_astana"
        )
    else:
        result_text = (
            f"😅 <b>ИТОГИ КОНКУРСА ПРОГНОЗОВ</b>\n\n"
            f"⚽ {match['home']} — {match['away']}\n"
            f"📊 Реальный счёт: <b>{real_score}</b>\n\n"
            f"Из {total} участников никто не угадал точный счёт!\n"
            f"В следующий раз повезёт 💪\n\n"
            f"@football_igraem_astana"
        )

    chat_id = from_config("CHAT_ID")
    tg_post(chat_id, "sendMessage", text=result_text, parse_mode="HTML")
    set_predict_active(False)
    print(f"  [PREDICT] Result announced: {real_score}, winners: {len(winners)}")


def get_stats():
    """Для панели админа."""
    match, active, _ = get_predict_match()
    preds = get_predictions()
    return {
        "active": active,
        "match": match,
        "total_predictions": len(preds),
        "predictions": list(preds.values()),
    }
