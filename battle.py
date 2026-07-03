import random
import string
import secrets
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
_battles = {}  # code -> state dict
_TTL = 3600    # автоочистка старых комнат, сек


def _gen_code():
    code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    while code in _battles:
        code = "".join(random.choices(string.ascii_uppercase + string.digits, k=4))
    return code


def _cleanup():
    now = time.time()
    dead = [c for c, b in _battles.items() if now - b["created"] > _TTL]
    for c in dead:
        del _battles[c]


def create_battle(name):
    with _lock:
        _cleanup()
        code = _gen_code()
        player_id = secrets.token_hex(4)
        _battles[code] = {
            "players": {player_id: {"name": name, "score": 0}},
            "order": [player_id],
            "step": -1,
            "answered": {},
            "created": time.time(),
        }
    return code, player_id


def join_battle(code, name):
    code = code.upper().strip()
    with _lock:
        b = _battles.get(code)
        if not b:
            return None, "not_found"
        if len(b["players"]) >= 2:
            return None, "full"
        player_id = secrets.token_hex(4)
        b["players"][player_id] = {"name": name, "score": 0}
        b["order"].append(player_id)
        b["step"] = 0
        b["answered"] = {}
    return player_id, None


def get_state(code, player_id):
    with _lock:
        b = _battles.get(code)
        if not b or player_id not in b["players"]:
            return None

        if len(b["players"]) < 2:
            return {"waiting": True, "opponent_name": None, "finished": False}

        opp_id = next((p for p in b["order"] if p != player_id), None)
        opponent = b["players"].get(opp_id)
        total = len(FOOTBALL_TRIVIA)
        finished = b["step"] >= total

        state = {
            "waiting": False,
            "opponent_name": opponent["name"] if opponent else None,
            "step": min(b["step"], total),
            "total": total,
            "finished": finished,
            "you_answered": player_id in b["answered"],
            "scores": [
                {"name": b["players"][pid]["name"], "score": b["players"][pid]["score"], "is_me": pid == player_id}
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


def submit_answer(code, player_id, answer_text):
    with _lock:
        b = _battles.get(code)
        if not b or player_id not in b["players"]:
            return None
        total = len(FOOTBALL_TRIVIA)
        if b["step"] >= total or player_id in b["answered"]:
            return None
        q, opts, correct_idx = FOOTBALL_TRIVIA[b["step"]]
        if answer_text not in opts:
            return None

        is_correct = opts.index(answer_text) == correct_idx
        b["answered"][player_id] = is_correct
        if is_correct:
            b["players"][player_id]["score"] += 1

        if len(b["answered"]) >= len(b["players"]):
            b["step"] += 1
            b["answered"] = {}

        return {"correct": is_correct, "correct_answer": opts[correct_idx]}
