import asyncio
import speech_recognition as sr
from faster_whisper import WhisperModel
import pyttsx3
import pyaudio
import wave
import aiohttp
from fuzzywuzzy import fuzz

# Инициализация голосового движка для text-to-speech (локальное воспроизведение для тестов)
engine = pyttsx3.init()
voices = engine.getProperty('voices')
for voice in voices:
    if "Russian" in voice.id:  # Выбираем русский голос, если доступен
        engine.setProperty('voice', voice.id)
engine.setProperty('rate', 115)  # Скорость речи

# Инициализация распознавания речи
recognizer = sr.Recognizer()
mic = sr.Microphone()

# Инициализация модели Faster Whisper для локального распознавания речи
whisper_model = WhisperModel("small", device="cpu", compute_type="int8")

# Параметры для записи аудио
CHUNK = 1024
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
WAVE_OUTPUT_FILENAME = "input.wav"

# URL для локального сервера Ollama
OLLAMA_URL = "http://localhost:11434/api/generate"

# Данные пользователя
user_data = {
    "name": "Иван Иванов",
    "balance": 10000.0,
    "card_number": "1234 5678 9012 3456"
}

# Список контактов для переводов
contacts = {
    "алексей": {"name": "Алексей Петров", "card_number": "4321 8765 2109 6543"},
    "мария": {"name": "Мария Смирнова", "card_number": "9876 5432 1098 7654"},
    "мама": {"name": "Анна Владимировна", "card_number": "3939 1223 8292 5436"}
}

# Функция для записи аудио
async def record_audio(duration=5):
    """Запись аудио с микрофона"""
    p = pyaudio.PyAudio()
    stream = p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
    frames = []
    print("Запись началась... Говорите.")
    for i in range(0, int(RATE / CHUNK * duration)):
        data = stream.read(CHUNK)
        frames.append(data)
    print("Запись завершена.")
    stream.stop_stream()
    stream.close()
    p.terminate()
    wf = wave.open(WAVE_OUTPUT_FILENAME, 'wb')
    wf.setnchannels(CHANNELS)
    wf.setsampwidth(p.get_sample_size(FORMAT))
    wf.setframerate(RATE)
    wf.writeframes(b''.join(frames))
    wf.close()
    return WAVE_OUTPUT_FILENAME

# Функция для распознавания речи с помощью Faster Whisper
async def recognize_speech(audio_file):
    """Распознавание речи из аудиофайла"""
    try:
        segments, info = whisper_model.transcribe(audio_file, beam_size=5, language="ru")
        text = " ".join([segment.text for segment in segments])
        return text
    except Exception as e:
        return f"Ошибка распознавания речи: {str(e)}"

# Функция для генерации ответа через Ollama
async def generate_response(query):
    """Генерация ответа через Ollama"""
    try:
        async with aiohttp.ClientSession() as session:
            payload = {
                "model": "deepseek-r1:1.7b",
                "messages": [
                    {"role": "system", "content": "Ты голосовой помощник банка."},
                    {"role": "user", "content": query}
                ],
                "temperature": 0,
                "stream": False
            }
            async with session.post(OLLAMA_URL, json=payload) as response:
                response.raise_for_status()
                data = await response.json()
                return data.get("response", "Не удалось получить ответ от модели.")
    except Exception as e:
        return f"Ошибка при генерации ответа: {str(e)}"

# Функция для озвучивания текста локально
async def speak_text(text):
    """Озвучивание текста через pyttsx3 (для тестов)"""
    try:
        if engine._inLoop:
            engine.endLoop()
        engine.say(text)
        engine.runAndWait()
    except RuntimeError as e:
        print(f"Ошибка воспроизведения текста (RuntimeError): {str(e)}")
        try:
            engine.endLoop()
            engine.say(text)
            engine.runAndWait()
        except Exception as inner_e:
            print(f"Повторная ошибка воспроизведения текста: {str(inner_e)}")
    except Exception as e:
        print(f"Ошибка воспроизведения текста: {str(e)}")

# Вспомогательная функция для извлечения суммы из запроса
def extract_amount(query):
    """Извлечение суммы из текста запроса"""
    words = query.split()
    for word in words:
        try:
            return float(word)
        except ValueError:
            continue
    return None

# Функция для поиска контакта с использованием fuzzywuzzy
def find_contact(query_lower):
    """Поиск контакта по имени с учётом неточностей"""
    best_match = None
    best_score = 0
    threshold = 70  # Порог совпадения

    for name in contacts.keys():
        score = fuzz.partial_ratio(name, query_lower)
        if score > best_score and score >= threshold:
            best_score = score
            best_match = name

    return best_match

# Функция для обработки запросов пользователя
async def process_query(query):
    """Обработка запроса пользователя с учётом вариаций слов через нечёткий поиск"""
    query_lower = query.lower().strip()
    threshold = 70  # Порог совпадения для нечёткого поиска

    query_types = {
        "balance": ["баланс", "остаток", "счёт", "деньги", "сколько на счету"],
        "card": ["карта", "номер карты", "карточка", "данные карты"],
        "transfer": ["перевод", "перевести", "отправить", "перекинуть", "послать"],
    }

    for query_type, keywords in query_types.items():
        is_match = False
        for keyword in keywords:
            for word in query_lower.split():
                score = fuzz.partial_ratio(keyword, word)
                if score >= threshold:
                    is_match = True
                    break
            if is_match:
                break

        if is_match:
            if query_type == "balance":
                return f"Ваш баланс: {user_data['balance']} рублей."
            elif query_type == "card":
                return f"Ваш номер карты: {user_data['card_number']}."
            elif query_type == "transfer":
                contact_name = find_contact(query_lower)
                if contact_name:
                    amount = extract_amount(query_lower)
                    if not amount:
                        return "Не удалось определить сумму перевода. Укажите сумму."
                    if amount > user_data['balance']:
                        return f"Недостаточно средств для перевода. Ваш баланс: {user_data['balance']} рублей."
                    return {
                        "status": "confirmation_needed",
                        "message": f"Подтвердите перевод на сумму {amount} рублей для {contacts[contact_name]['name']}.",
                        "amount": amount,
                        "contact": contact_name
                    }
                else:
                    return "Контакт не найден. Пожалуйста, уточните имя получателя."

    return await generate_response(query)

# Функция для подтверждения перевода
async def confirm_transfer(amount, contact_name):
    """Подтверждение перевода"""
    if amount <= user_data['balance']:
        user_data['balance'] -= amount
        return f"Перевод на сумму {amount} рублей для {contacts[contact_name]['name']} выполнен. Новый баланс: {user_data['balance']} рублей."
    else:
        return f"Недостаточно средств для перевода. Баланс: {user_data['balance']} рублей."

# Единая функция для обработки ввода (голосового или текстового)
async def handle_input(input_type, data=None):
    """Обработка голосового или текстового ввода"""
    query = ""
    if input_type == "voice":
        try:
            audio_file = await record_audio(duration=5)
            query = await recognize_speech(audio_file)
            if "Ошибка" in query:
                return {"query": "", "response": query}
        except Exception as e:
            return {"query": "", "response": f"Ошибка записи или распознавания: {str(e)}"}
    elif input_type == "text":
        query = data if data else ""

    if not query:
        response = "Пустой запрос. Пожалуйста, повторите."
        return {"query": "", "response": response}

    result = await process_query(query)
    if isinstance(result, dict) and result.get("status") == "confirmation_needed":
        return {
            "query": query,
            "response": result["message"],
            "confirmation_data": {
                "amount": result["amount"],
                "contact": result["contact"]
            }
        }
    else:
        return {"query": query, "response": result}

# Основной цикл программы
async def main():
    """Тестовый цикл для проверки работы"""
    print("Запуск голосового помощника банка...")

    while True:
        mode = input("Выберите режим (1 - голос, 2 - текст, 3 - выход): ")
        if mode == "1":
            result = await handle_input("voice")
            print(f"Запрос: {result['query']}")
            print(f"Ответ: {result['response']}")
            if "confirmation_data" in result:
                confirm = input("Подтверждаете перевод? (да/нет): ").lower()
                if confirm == "да":
                    confirm_result = await confirm_transfer(
                        result["confirmation_data"]["amount"],
                        result["confirmation_data"]["contact"]
                    )
                    print(f"Результат: {confirm_result}")
        elif mode == "2":
            query = input("Введите ваш вопрос: ")
            result = await handle_input("text", query)
            print(f"Запрос: {result['query']}")
            print(f"Ответ: {result['response']}")
            if "confirmation_data" in result:
                confirm = input("Подтверждаете перевод? (да/нет): ").lower()
                if confirm == "да":
                    confirm_result = await confirm_transfer(
                        result["confirmation_data"]["amount"],
                        result["confirmation_data"]["contact"]
                    )
                    print(f"Результат: {confirm_result}")
        elif mode == "3":
            break

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Программа завершена пользователем.")
    except Exception as e:
        print(f"Произошла ошибка: {str(e)}")
