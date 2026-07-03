import threading
import time

FOOTBALL_TRIVIA = [
    ("Сколько игроков от одной команды на поле одновременно (включая вратаря)?",
     ["9", "10", "11", "12"], 2),
    ("Сколько таймов в футбольном матче по стандартным правилам?",
     ["1", "2", "3", "4"], 1),
    ("Сколько минут длится один тайм (без добавленного времени)?",
     ["30", "40", "45", "50"], 2),
    ("Какая страна принимала Чемпионат мира по футболу 2018 года?",
     ["Бразилия", "Россия", "Катар", "ЮАР"], 1),
    ("Какая страна принимала Чемпионат мира по футболу 2022 года?",
     ["ОАЭ", "Саудовская Аравия", "Катар", "Кувейт"], 2),
    ("Сколько раз сборная Бразилии выигрывала Чемпионат мира (на 2022 год)?",
     ["3", "4", "5", "6"], 2),
    ("Как называется вторая жёлтая карточка одному игроку за матч?",
     ["Штраф", "Удаление", "Пенальти", "Предупреждение"], 1),
    ("Кто автор гола «рука Бога» на ЧМ-1986?",
     ["Пеле", "Марадона", "Зидан", "Роналдо"], 1),
    ("Какой клуб выигрывал Лигу чемпионов УЕФА больше всех раз?",
     ["Милан", "Барселона", "Бавария", "Реал Мадрид"], 3),
    ("Сколько судей работает на поле во время матча (главный + линейные, без VAR)?",
     ["1", "2", "3", "4"], 2),
]

_lock = threading.Lock()
_battles = {}   # battle_id -> state dict
_next_id = [0]
_TTL = 3600     # автоочистка старых баттлов, сек


def _gen_id():
    _next_id[0] += 1
    return str(_next_id[0])


def _cleanup():
    now = time.time()
    dead = [bid for bid, b in _battles.items() if now - b["created"] > _TTL]
    for bid in dead:
        del _battles[bid]


def create_battle(title, creator_id, creator_name):
    """Создаёт открытый баттл, ждущий соперника. Возвращает battle_id."""
    creator_id = str(creator_id)
    with _lock:
        _cleanup()
        battle_id = _gen_id()
        _battles[battle_id] = {
            "title": (title or "Футбольный баттл")[:40],
            "players": {creator_id: {"name": creator_name, "score": 0}},
            "order": [creator_id],
            "step": -1,
            "answered": {},
            "created": time.time(),
            "status": "waiting",  # waiting -> active -> finished
        }
    return battle_id


def list_open_battles():
    """Список открытых баттлов, ждущих соперника — видно всем."""
    with _lock:
        _cleanup()
        return [
            {
                "id": bid,
                "title": b["title"],
                "creator_name": b["players"][b["order"][0]]["name"],
            }
            for bid, b in _battles.items() if b["status"] == "waiting"
        ]


def join_battle(battle_id, user_id, user_name):
    """Первый, кто зайдёт — сразу стартует баттл. Возвращает None (ок) или строку ошибки."""
    user_id = str(user_id)
    with _lock:
        b = _battles.get(battle_id)
        if not b:
            return "not_found"
        if user_id in b["players"]:
            return None  # уже в баттле — просто продолжаем
        if b["status"] != "waiting":
            return "full"

        b["players"][user_id] = {"name": user_name, "score": 0}
        b["order"].append(user_id)
        b["step"] = 0
        b["answered"] = {}
        b["status"] = "active"
    return None


def get_state(battle_id, user_id):
    user_id = str(user_id)
    with _lock:
        b = _battles.get(battle_id)
        if not b or user_id not in b["players"]:
            return None

        if b["status"] == "waiting":
            return {"waiting": True, "title": b["title"], "finished": False}

        opp_id = next((p for p in b["order"] if p != user_id), None)
        opponent = b["players"].get(opp_id)
        total = len(FOOTBALL_TRIVIA)
        finished = b["step"] >= total

        state = {
            "waiting": False,
            "title": b["title"],
            "opponent_name": opponent["name"] if opponent else None,
            "step": min(b["step"], total),
            "total": total,
            "finished": finished,
            "you_answered": user_id in b["answered"],
            "scores": [
                {"name": b["players"][pid]["name"], "score": b["players"][pid]["score"], "is_me": pid == user_id}
                for pid in b["order"]
            ],
        }
        if not finished:
            q, opts, _ = FOOTBALL_TRIVIA[b["step"]]
            state["question"] = {"text": q, "options": opts}
        else:
            state["question"] = None
            top = max(state["scores"], key=lambda s: s["score"])
            tie = sum(1 for s in state["scores"] if s["score"] == top["score"]) > 1
            state["winner"] = None if tie else top["name"]
        return state


def submit_answer(battle_id, user_id, answer_text):
    user_id = str(user_id)
    with _lock:
        b = _battles.get(battle_id)
        if not b or user_id not in b["players"] or b["status"] != "active":
            return None
        total = len(FOOTBALL_TRIVIA)
        if b["step"] >= total or user_id in b["answered"]:
            return None
        q, opts, correct_idx = FOOTBALL_TRIVIA[b["step"]]
        if answer_text not in opts:
            return None

        is_correct = opts.index(answer_text) == correct_idx
        b["answered"][user_id] = is_correct
        if is_correct:
            b["players"][user_id]["score"] += 1

        if len(b["answered"]) >= len(b["players"]):
            b["step"] += 1
            b["answered"] = {}

        return {"correct": is_correct, "correct_answer": opts[correct_idx]}
