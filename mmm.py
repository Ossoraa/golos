from faster_whisper import WhisperModel
from fuzzywuzzy import fuzz
import requests
import json

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
        # Формируем контекст для LLM с данными о пользователе и контактах
        context = {
            "user_data": user_data,
            "contacts": {k: v["name"] for k, v in contacts.items()},  # Передаем только имена контактов
            "instructions": (
                "Ты голосовой помощник банка Центр Инвест. Отвечай на запросы пользователя. "
                "Если запрос связан с балансом, картой или переводом, верни JSON-ответ в формате: "
                '{"command": "balance"} или {"command": "card"} или '
                '{"command": "transfer", "contact": "имя_контакта", "amount": сумма}. '
                'Если запрос не связан с банковскими операциями, верни текстовый ответ в формате: '
                '{"command": "none", "message": "твой_ответ"}. '
                'Если нужно подтверждение перевода, верни {"command": "confirm_transfer", "contact": "имя_контакта", "amount": сумма, "message": "текст_для_пользователя"}. '
                'Не раскрывай конфиденциальные данные (например, номер карты) без явного запроса. '
                'Если контакт или сумма не ясны, запроси уточнение у пользователя.'
            )
        }
        payload = {
            "model": "qwen2.5:1.5b",
            "messages": [
                {"role": "system", "content": json.dumps(context, ensure_ascii=False)},
                {"role": "user", "content": query}
            ],
            "temperature": 0.2,
            "stream": False
        }
        response = requests.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        response_content = response.json()["message"]["content"]
        # Пробуем распарсить ответ как JSON
        try:
            return json.loads(response_content)
        except json.JSONDecodeError:
            # Если не JSON, возвращаем как обычный текст
            return {"command": "none", "message": response_content}
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
            "message": f"Подтвердите перевод {amount} руб. для {contacts[contact_name.lower()]['name']}.",
            "status": "confirmation_needed",
            "data": {"amount": amount, "contact": contact_name.lower()}
        }
    elif command == "confirm_transfer":
        contact_name = command_data.get("contact").lower()
        amount = command_data.get("amount")
        if amount <= user_data['balance']:
            user_data['balance'] -= amount
            return {"message": f"Перевод {amount} рублей для {contacts[contact_name]['name']} выполнен. Новый баланс: {user_data['balance']}."}
        else:
            return {"message": f"Недостаточно средств. Баланс: {user_data['balance']} рублей."}
    elif command == "none":
        return {"message": command_data.get("message", "Неизвестная команда.")}
    elif command == "error":
        return {"message": command_data.get("message", "Произошла ошибка.")}
    return {"message": "Неизвестная команда."}

def process_query(query):
    # Передаем запрос в LLM для анализа и получения команды
    llm_response = ask_llm(query)
    # Выполняем команду и возвращаем только сообщение для пользователя
    result = execute_command(llm_response)
    return result

def confirm_transfer(amount, contact_name):
    # Формируем запрос для LLM на подтверждение
    query = f"Подтверждаю перевод {amount} рублей для {contact_name}."
    return process_query(query)
