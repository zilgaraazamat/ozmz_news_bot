"""AI-сканер футбольных мячей по фото (Claude Vision)."""
import json

from api import claude_vision


class ScannerRoutesMixin:
    def route_post_scanner_analyze(self, body):
        try:
            data = json.loads(body)
            image_b64 = data.get("image") or ""
            if "," in image_b64 and image_b64.strip().startswith("data:"):
                image_b64 = image_b64.split(",", 1)[1]
            if not image_b64:
                self._json({"ok": False, "error": "Нет изображения"})
                return

            prompt = (
                "Ты — эксперт по футбольным мячам (Adidas, Nike, Puma, Select, Mikasa и другие). "
                "Внимательно рассмотри фото и определи модель мяча.\n\n"
                "Верни ТОЛЬКО валидный JSON, без markdown-обрамления, строго в такой структуре:\n"
                '{"found": true, "confidence": 90, "name": "Adidas Teamgeist", '
                '"model": "Teamgeist Berlin", "year": "2006", '
                '"usage": "короткая фраза, 3-6 слов", '
                '"tournaments": ["Турнир"], '
                '"fun_fact": "одно короткое яркое предложение", '
                '"design": "короткая фраза про дизайн, 3-8 слов"}\n\n'
                "ВАЖНЫЕ правила:\n"
                "- Пиши МАКСИМАЛЬНО кратко. Каждое поле — короткая фраза, не абзац. Без воды "
                "и общих слов.\n"
                "- НЕ утверждай, что мяч 'официальный' или 'оригинальный', если это не считывается "
                "явно и однозначно с фото (чёткие официальные логотипы турнира на самом мяче). "
                "Обычный реплика/сувенирный/любительский мяч — не выдавай за официальный. Если "
                "сомневаешься в статусе — пиши мягко: 'дизайн в стиле...', 'похож на...', без "
                "утвердительных заявлений о подлинности.\n"
                "- tournaments заполняй, ТОЛЬКО если реально узнаёшь конкретный турнир по дизайну "
                "мяча. Если не уверен — пустой массив [].\n"
                "- usage — если не можешь определить точное использование, просто укажи тип мяча "
                "(тренировочный / любительский / реплика / коллекционный и т.п.), без выдумок.\n"
                "- Если на фото не похоже на футбольный мяч или совсем нечётко — верни "
                '{"found": false, "confidence": null, "name": null, "model": null, "year": null, '
                '"usage": null, "tournaments": [], "fun_fact": null, "design": null}.\n'
                "- Если мяч виден, но не уверен в точной модели — всё равно дай лучшую догадку "
                "(found: true) и честный процент уверенности confidence, не завышай.\n"
                "- Пиши по-русски, без ссылок и markdown."
            )
            raw = claude_vision(image_b64, "image/jpeg", prompt, max_tokens=500)
            cleaned = raw.replace("```json", "").replace("```", "").strip()
            try:
                result = json.loads(cleaned)
            except Exception:
                result = {"found": False, "confidence": None}

            self._json({"ok": True, "result": result})
        except Exception as e:
            print(f"  [WARN] scanner/analyze: {e}")
            self.send_response(400); self.end_headers()

