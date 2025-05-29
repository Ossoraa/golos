from faster_whisper import WhisperModel
from fuzzywuzzy import fuzz
import requests
import json
import re

OLLAMA_URL = "http://localhost:11434/api/chat"

whisper_model = WhisperModel("small", device="cpu", compute_type="int8")

user_data = {
    "name": "Иван Иванов",
    "balance": 10000.0,
    "card_number": "1234 5678 9012 3456"
}

contacts = {
    "алексей": {"name": "Алексей Петров", "card_number": "4321 8765 2109 6543"},
    "мария": {"name": "Мария Смирнова", "card_number": "9876 5432 1098 7654"},
    "мама": {"name": "Анна Владимировна", "card_number": "3939 1223 8292 5436"}
}

def recognize_speech(audio_file):
    try:
        segments, info = whisper_model.transcribe(audio_file, beam_size=5, language="ru")
        return " ".join([segment.text for segment in segments])
    except Exception as e:
        return f"Ошибка распознавания речи: {str(e)}"

def ask_llm(query: str):
    try:
        context = {
            "user_data": user_data,
            "contacts": {k: v["name"] for k, v in contacts.items()},
            "instructions": (
                "Ты — голосовой помощник банка «Центр Инвест». У тебя есть база контактов в `contacts`.\n"
                "В ответе ты ДОЛЖЕН вернуть ровно один JSON-объект.\n"
                "Базовые ключи:\n"
                "  • command — строка (balance, card, transfer, confirm_transfer, none).\n"
                "  • message — текст для пользователя.\n"
                "Для команд, требующих дополнительные данные (transfer, confirm_transfer), ОБЯЗАТЕЛЬНО включай ключи:\n"
                "  • contact — имя получателя,\n"
                "  • amount — число (сумма перевода).\n"
                "Если вопрос НЕ связан с командами\n"
                "то всегда возвращай:\n"
                '  {"command":"none","message":"<результат или ответ>"}\n'
                "НИ ПРИ КАКИХ УСЛОВИЯХ НЕ ДОБАВЛЯЙ В ОТВЕТ markdown, БЭКТИКИ ``` ИЛИ ВЛОЖЕННЫЕ JSON!!!\n"
                "НЕ ВЫВОДИ НИЧЕГО, КРОМЕ ОДНОГО JSON-объекта!!!\n\n"
                "Форматы команд:\n"
                "- Баланс:\n"
                '  {"command":"balance","message":"текст"}\n'
                "- Номер карты:\n"
                '  {"command":"card","message":"текст"}\n'
                "- Перевод средств:\n"
                '  {"command":"transfer","contact":"имя_контакта","amount":число,"message":"текст"}\n'
                "- Подтверждение перевода:\n"
                '  {"command":"confirm_transfer","contact":"имя_контакта","amount":число,"message":"текст"}\n'
                "При отказе подтверждения перевода:\n"
                ' {"command":"cancel_transfer"}\n'
                "- Общий ответ без действия:\n"
                '  {"command":"none","message":"текст"}\n\n'
                "Если не понимаешь запрос — верни:\n"
                '  {"command":"none","message":"не понял вопрос"}\n'
                "Ниже указаны жёстко заданные ответы на распространённые вопросы. Используй ИХ БЕЗ ИЗМЕНЕНИЙ, если запрос пользователя содержит указанные ключевые слова.\n"
                "— Если вопрос содержит: «курс доллара» или «доллар», ответ должен быть:\n"
                '{"command": "none", "message": "Курс доллара зависит от рыночных условий. Актуальный курс можно уточнить на сайте ЦБ РФ."}\n'
                "— Если вопрос содержит: «что такое СБП» или просто «СБП», ответ должен быть:\n"
                '{"command": "none", "message": "СБП — это Система Быстрых Платежей, позволяющая переводить деньги между банками без комиссии."}\n'
                "— Если вопрос содержит: «взять кредит», «как получить кредит» или «оформить кредит», ответ должен быть:\n"
                '{"command": "none", "message": "Чтобы взять кредит, обратитесь в отделение банка или подайте заявку на сайте банка Центр Инвест."}\n'
                "— Если вопрос содержит: «что такое ЖКХ» или «ЖКХ», ответ должен быть:\n"
                '{"command": "none", "message": "ЖКХ — это жилищно-коммунальное хозяйство: услуги по содержанию жилья, отопление, вода и вывоз мусора."}\n'
            )
        }
        payload = {
            "model": "qwen2.5:1.5b",
            "messages": [
                {"role": "system", "content": json.dumps(context, ensure_ascii=False)},
                {"role": "user", "content": query}
            ],
            "temperature": 0,
            "stream": False
        }
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        response_content = response.json()["message"]["content"]
        print(f'ПЕРЕД ОБРАБОТКОЙ ОТВЕТ:{response_content}')

        clean = re.sub(r"```(?:json)?\s*", "", response_content)
        clean = re.sub(r"\s*```", "", clean)
        clean = clean.strip()

        try:
            return json.loads(clean)
        except json.JSONDecodeError:
            return {"command": "none", "message": clean}

    except Exception as e:
        return {"command": "error", "message": f"Ошибка при обращении к LLM: {str(e)}"}

def execute_command(command_data):
    command = command_data.get("command")
    if command == "balance":
        return {"message": f"Ваш баланс: {user_data['balance']} рублей."}
    elif command == "card":
        return {"message": f"Ваш номер карты: {user_data['card_number']}."}
    elif command == "transfer":
        contact_name = command_data.get("contact")
        amount = command_data.get("amount")
        if not contact_name or contact_name.lower() not in contacts:
            return {"message": "Контакт не найден. Укажите имя получателя."}
        if not amount:
            return {"message": "Не указана сумма перевода. Укажите сумму."}
        if amount > user_data['balance']:
            return {"message": f"Недостаточно средств. Баланс: {user_data['balance']} рублей."}
        return {
            "message": f"Подтвердите перевод {amount} руб. для {contacts[contact_name.lower()]['name']}.(подтверждаю/отказываюсь)",
            "status": "confirmation_needed",
            "data": {"amount": amount, "contact": contact_name.lower()}
        }
    elif command == "confirm_transfer":
        contact_name = command_data.get("contact", "").lower()
        amount = command_data.get("amount")
        if amount and amount <= user_data['balance']:
            user_data['balance'] -= amount
            return {"message": f"Перевод {amount} рублей для {contacts[contact_name]['name']} выполнен. Новый баланс: {user_data['balance']}."}
        else:
            return {"message": f"Недостаточно средств. Баланс: {user_data['balance']} рублей."}
    elif command == "cancel_transfer":
        return {"message": "Перевод отменён"}
    elif command == "none":
        return {"message": command_data.get("message", "Неизвестная команда.")}
    elif command == "error":
        return {"message": command_data.get("message", "Произошла ошибка.")}
    return {"message": "Неизвестная команда."}

def process_query(query):
    llm_response = ask_llm(query)
    print(f'ОТВЕТ МОДЕЛИ:\n{llm_response}')
    result = execute_command(llm_response)
    return result

def confirm_transfer(amount, contact_name):
    query = f"Подтверждаю перевод {amount} рублей для {contact_name}."
    return process_query(query)

def sanitize_text(text):
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        raise ValueError("Невозможно озвучить JSON-структуру.")
    clean_text = re.sub(r"[^\w\s,.!?ёЁа-яА-Я]", "", text)
    if not clean_text or len(clean_text) < 3:
        raise ValueError("Недопустимый текст для озвучки.")
    return clean_text

def speak_text(text):
    text = sanitize_text(text)
    from tts_silero import silero_tts
    return silero_tts(text)
