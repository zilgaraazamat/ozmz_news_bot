"""Цены и суммы оплаты — единственное место в приложении, где из игры
извлекается цена за игрока и считается сумма записи.

Поле games.price исторически свободный текст («2500 ₸», «2 500 тг с человека»
и т.п.), поэтому цена за игрока = первое число в этой строке. Ни фронтенд,
ни другие модули не должны парсить цену сами — только звать функции отсюда:
  - price_per_player(game) — цена за одного игрока (int) или None, если цена
    не задана / не распознана;
  - entry_amount(game, people_count) — сумма партии записи:
    price_per_player × количество людей, или None, если цены нет.

Сумма считается ТОЛЬКО на бэкенде в момент записи (см. routes/games.py →
signup) и сохраняется в game_signups.amount — клиент никогда не присылает
сумму сам, поэтому подменить её из приложения нельзя. Всё, что показывает
деньги (шит записи, карточка игры, админка, уведомления админам), читает либо
сохранённый amount записи, либо price_per_player из /api/games.
"""
import re

_PRICE_RE = re.compile(r"\d[\d\s]*")


def price_per_player(game):
    """Цена за одного игрока из свободного текста games.price.
    None — цена не задана или число не распознано."""
    m = _PRICE_RE.search(str((game or {}).get("price") or ""))
    if not m:
        return None
    try:
        n = int(m.group(0).replace(" ", "").replace("\u00a0", ""))
    except ValueError:
        return None
    return n if n > 0 else None


def entry_amount(game, people_count):
    """Сумма партии записи = цена за игрока × число людей в партии.
    «Записаться самому» — people_count=1 (платит один игрок),
    «Записать компанию» — people_count = регистрант + гости.
    None, если у игры нет распознаваемой цены."""
    per = price_per_player(game)
    if per is None:
        return None
    try:
        people_count = int(people_count)
    except (TypeError, ValueError):
        return None
    if people_count < 1:
        return None
    return per * people_count
