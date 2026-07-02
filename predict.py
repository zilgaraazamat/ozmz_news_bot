"""
🎯 УГАДАЙ СЧЁТ — вирусная механика

Как работает:
1. Утром бот постит матч + просит прогнозы (/счёт 2:1)
2. Пользователи пишут боту прогноз
3. Вечером (или вручную) бот объявляет победителей

predict_state = {
    "match": {"home": ..., "away": ..., "time": ...},
    "predictions": {user_id: {"name": ..., "score": "2:1"}},
    "message_id": ...,   # id поста в группе
    "active": True/False,
}
"""
import re
from api import now_astana, tg_post, send_msg, from_config

predict_state = {
    "match": None,
    "predictions": {},
    "message_id": None,
    "active": False,
}


def start_prediction(match):
    """Постим матч в группу и открываем приём прогнозов."""
    predict_state["match"] = match
    predict_state["predictions"] = {}
    predict_state["active"] = True

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
    result = tg_post(chat_id, "sendMessage",
                     text=text, parse_mode="HTML")
    if result and result.get("ok"):
        predict_state["message_id"] = result["result"]["message_id"]
    print(f"  [PREDICT] Contest started for {match['home']} vs {match['away']}")


def handle_prediction(user_id, user_name, text):
    """Обрабатываем /счёт X:Y от пользователя."""
    if not predict_state["active"]:
        send_msg(user_id, "⚽ Сейчас нет активного конкурса прогнозов. Приходи утром!")
        return

    match = re.search(r"(\d{1,2})\s*[:–-]\s*(\d{1,2})", text)
    if not match:
        send_msg(user_id,
                 "❌ Формат: <code>/счёт 2:1</code>\n"
                 "Напиши счёт через двоеточие, например 2:1 или 0:0")
        return

    score = f"{match.group(1)}:{match.group(2)}"
    m = predict_state["match"]

    predict_state["predictions"][str(user_id)] = {
        "name": user_name,
        "score": score,
    }

    send_msg(user_id,
             f"✅ Принял твой прогноз!\n\n"
             f"⚽ {m['home']} — {m['away']}\n"
             f"🔮 Твой счёт: <b>{score}</b>\n\n"
             f"Следи за результатом в @football_igraem_astana 👀")
    print(f"  [PREDICT] {user_name} → {score}")


def announce_result(real_score: str):
    """
    Вызывается когда стал известен реальный счёт.
    real_score = "2:1"
    Постит итоги в группу.
    """
    if not predict_state["active"] or not predict_state["match"]:
        return

    m = predict_state["match"]
    preds = predict_state["predictions"]

    winners = [
        p["name"] for p in preds.values()
        if p["score"] == real_score
    ]

    total = len(preds)

    if winners:
        w_text = ", ".join(f"<b>{w}</b>" for w in winners)
        result_text = (
            f"🏆 <b>ИТОГИ КОНКУРСА ПРОГНОЗОВ</b>\n\n"
            f"⚽ {m['home']} — {m['away']}\n"
            f"📊 Реальный счёт: <b>{real_score}</b>\n\n"
            f"🥇 Угадали ({len(winners)} из {total}):\n"
            f"{w_text}\n\n"
            f"🔥 Красавцы! Играете с нами? @football_igraem_astana"
        )
    else:
        result_text = (
            f"😅 <b>ИТОГИ КОНКУРСА ПРОГНОЗОВ</b>\n\n"
            f"⚽ {m['home']} — {m['away']}\n"
            f"📊 Реальный счёт: <b>{real_score}</b>\n\n"
            f"Из {total} участников никто не угадал точный счёт!\n"
            f"В следующий раз повезёт 💪\n\n"
            f"@football_igraem_astana"
        )

    chat_id = from_config("CHAT_ID")
    tg_post(chat_id, "sendMessage", text=result_text, parse_mode="HTML")
    predict_state["active"] = False
    print(f"  [PREDICT] Result announced: {real_score}, winners: {len(winners)}")


def get_stats():
    """Для панели админа."""
    return {
        "active": predict_state["active"],
        "match": predict_state["match"],
        "total_predictions": len(predict_state["predictions"]),
        "predictions": list(predict_state["predictions"].values()),
    }
