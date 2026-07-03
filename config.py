import os
from datetime import timezone, timedelta

BOT_TOKEN     = os.environ.get("BOT_TOKEN", "")
CHAT_ID       = os.environ.get("CHAT_ID", "")
ANTHROPIC_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
FOOTBALL_KEY  = os.environ.get("FOOTBALL_API_KEY", "")
PORT          = int(os.environ.get("PORT", 8080))
RAILWAY_DOMAIN = os.environ.get("RAILWAY_PUBLIC_DOMAIN", "")

ASTANA_TZ = timezone(timedelta(hours=5))

RSS_FEEDS = [
    ("Lenta.ru",  "https://lenta.ru/rss/news/sport/football"),
    ("Чемпионат", "https://www.championat.com/football/rss.xml"),
    ("РИА Спорт", "https://rsport.ria.ru/trend/football_news/"),
    ("Sports.kz", "https://sports.kz/rss/"),
    ("Soccer.ru",  "https://www.soccer.ru/rss/news.xml"),
]

PHOTOS = [
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Wembley_Stadium_interior.jpg/1280px-Wembley_Stadium_interior.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/6/61/Camp_Nou_aerial_%28cropped%29.jpg/1280px-Camp_Nou_aerial_%28cropped%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5e/Allianz_Arena_Abend.jpg/1280px-Allianz_Arena_Abend.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg/1280px-Signal_Iduna_Park_-_Gesamtansicht_%282012%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3c/Stadio_Giuseppe_Meazza_%28Milano%29.jpg/1280px-Stadio_Giuseppe_Meazza_%28Milano%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/5/59/Stade_de_France_2007.jpg/1280px-Stade_de_France_2007.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0f/Luzhniki_Stadium_2018_FIFA_World_Cup.jpg/1280px-Luzhniki_Stadium_2018_FIFA_World_Cup.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8e/Metropolitano_-_Atletico_de_Madrid.jpg/1280px-Metropolitano_-_Atletico_de_Madrid.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/1/1d/FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg/1280px-FC_Barcelona_vs_Real_Madrid_CF%2C_2013_%2801%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Messi_vs_Nigeria_2018.jpg/1024px-Messi_vs_Nigeria_2018.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Cristiano_Ronaldo_in_2018.jpg/800px-Cristiano_Ronaldo_in_2018.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/FIFA_World_Cup_2018_-_Group_F_-_Germany_v_Sweden_%2821%29_%28cropped%29.jpg/1280px-FIFA_World_Cup_2018_-_Group_F_-_Germany_v_Sweden_%2821%29_%28cropped%29.jpg",
    "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e3/2018_FIFA_World_Cup_Russia%2C_Round_of_16%2C_France_vs_Argentina_%2801%29.jpg/1280px-2018_FIFA_World_Cup_Russia%2C_Round_of_16%2C_France_vs_Argentina_%2801%29.jpg",
]

PLAYER_PHOTOS = {
    "Криштиану Роналду":  "https://upload.wikimedia.org/wikipedia/commons/thumb/3/34/Cristiano_Ronaldo_in_2018.jpg/800px-Cristiano_Ronaldo_in_2018.jpg",
    "Лионель Месси":      "https://upload.wikimedia.org/wikipedia/commons/thumb/b/b8/Messi_vs_Nigeria_2018.jpg/1024px-Messi_vs_Nigeria_2018.jpg",
    "Килиан Мбаппе":      "https://upload.wikimedia.org/wikipedia/commons/thumb/5/57/2019-07-17_SG_Dynamo_Dresden_vs._Paris_Saint-Germain_F.C._by_Sandro_Halank%E2%80%93074_%28cropped%29.jpg/800px-2019-07-17_SG_Dynamo_Dresden_vs._Paris_Saint-Germain_F.C._by_Sandro_Halank%E2%80%93074_%28cropped%29.jpg",
    "Эрлинг Холанд":      "https://upload.wikimedia.org/wikipedia/commons/thumb/a/a9/Erling_Haaland_2022_%28cropped%29.jpg/800px-Erling_Haaland_2022_%28cropped%29.jpg",
    "Неймар":             "https://upload.wikimedia.org/wikipedia/commons/thumb/b/bc/Bra-Col_%281%29_%28cropped%29.jpg/800px-Bra-Col_%281%29_%28cropped%29.jpg",
    "Зинедин Зидан":      "https://upload.wikimedia.org/wikipedia/commons/thumb/f/f3/Zinedine_Zidane_by_Tasnim_03.jpg/800px-Zinedine_Zidane_by_Tasnim_03.jpg",
    "Роналдиньо":         "https://upload.wikimedia.org/wikipedia/commons/thumb/e/e0/Ronaldinho_in_2018.jpg/800px-Ronaldinho_in_2018.jpg",
    "Тьерри Анри":        "https://upload.wikimedia.org/wikipedia/commons/thumb/6/67/Thierry_Henry_2.jpg/800px-Thierry_Henry_2.jpg",
    "Андрес Иньеста":     "https://upload.wikimedia.org/wikipedia/commons/thumb/9/9b/Andres_Iniesta_%28Euro_2012_cropped%29.jpg/800px-Andres_Iniesta_%28Euro_2012_cropped%29.jpg",
    "Роберт Левандовски": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/37/Robert_Lewandowski%2C_FC_Bayern_M%C3%BCnchen_%28by_Sven_Mandel%2C_2019-09-28%29_02_%28cropped%29.jpg/800px-Robert_Lewandowski%2C_FC_Bayern_M%C3%BCnchen_%28by_Sven_Mandel%2C_2019-09-28%29_02_%28cropped%29.jpg",
}

FOOTBALLERS = list(PLAYER_PHOTOS.keys())

# ── Роли для баланса команд ──────────────────────────────────────────────────
# ВАЖНО (Railway): контейнер эфемерный — файл БД переживёт рестарт,
# но пропадёт при новом деплое, если не подключить Volume.
# Создай Volume в Railway (например на /data) и пропиши ROLE_DB_PATH=/data/roles.db
ROLE_DB_PATH = os.environ.get("ROLE_DB_PATH", "roles.db")

PLAYER_CATEGORIES = {
    "Криштиану Роналду":  "Атака",
    "Эрлинг Холанд":      "Атака",
    "Роберт Левандовски": "Атака",
    "Тьерри Анри":        "Атака",
    "Лионель Месси":      "Центр",
    "Зинедин Зидан":      "Центр",
    "Андрес Иньеста":     "Центр",
    "Килиан Мбаппе":      "Оборона",
    "Неймар":             "Оборона",
    "Роналдиньо":         "Оборона",
}

BAD_PHRASES = [
    "я не могу", "не могу написать", "у меня нет данных", "дезинформация",
    "нет информации", "к сожалению", "извините", "не имею доступа",
    "что могу сделать", "что я могу", "турнир ещё не начался",
    "могу предложить", "если ты скинешь", "шаблон поста",
]

QUIZ_QUESTIONS = [
    ("Как ты ведёшь себя на поле?", ["Я лидер, всё через меня", "Работяга в обороне", "Творю магию в атаке", "Дирижирую из центра"]),
    ("Твой стиль игры?", ["Скорость и дриблинг", "Сила и напор", "Точность и техника", "Умная позиция"]),
    ("Что делаешь после гола?", ["Бегу к угловому флагу", "Спокойно иду на центр", "Кричу и прыгаю на партнёров", "Показываю жест команде"]),
    ("Твоя любимая позиция?", ["Нападающий", "Полузащитник", "Защитник", "Всё равно — главное играть"]),
    ("Финал, 0:0, серия пенальти. Ты:", ["Иду первым — не боюсь", "Жду своей очереди спокойно", "Отказываюсь — не мой день", "Бью последним, как герой"]),
    ("Твоё отношение к тренеру?", ["Спорю — я лучше знаю", "Уважаю и слушаюсь", "Делаю по-своему на поле", "Нейтрально, лишь бы играть"]),
    ("Как готовишься к матчу?", ["Музыка и концентрация", "Тактический разбор", "Разминка и растяжка", "Просто выхожу и играю"]),
    ("Твой кумир в детстве?", ["Роналду", "Месси", "Зидан", "Роналдиньо"]),
    ("Что важнее?", ["Личные голы и рекорды", "Командный трофей", "Красивая игра", "Признание болельщиков"]),
    ("Как заканчиваешь карьеру?", ["На вершине — ухожу чемпионом", "Играю до последнего", "Становлюсь тренером", "Ещё не думал об этом"]),
]
