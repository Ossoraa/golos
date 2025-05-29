from fastapi import FastAPI, UploadFile, File
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from tts_silero import silero_tts
import uuid
import os

from mmm import process_query, recognize_speech, confirm_transfer, speak_text

app = FastAPI()

class MessageRequest(BaseModel):
    text: str

is_speaking = False
confirmation_context = {"awaiting": False, "amount": None, "contact": None}

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/static", StaticFiles(directory="static"), name="static")
os.makedirs("static", exist_ok=True)

@app.post("/api/message")
async def handle_text(request: MessageRequest):
    global confirmation_context
    text = request.text.strip().lower()

    if confirmation_context["awaiting"] and text in ["да", "подтверждаю", "ок"]:
        result = confirm_transfer(
            confirmation_context["amount"],
            confirmation_context["contact"]
        )
        confirmation_context = {"awaiting": False, "amount": None, "contact": None}
        try:
            audio_path = speak_text(result["message"])
        except Exception as e:
            print("Ошибка озвучки:", e)
            audio_path = None
        return {
            "answer": result["message"],
            "audio_url": f"http://localhost:8000/{audio_path}" if audio_path else None
        }

    result = process_query(text)

    if isinstance(result, dict) and result.get("status") == "confirmation_needed":
        confirmation_context = {
            "awaiting": True,
            "amount": result.get("data", {}).get("amount"),
            "contact": result.get("data", {}).get("contact")
        }
        return {"answer": result["message"], "audio_url": None}

    response_text = result["message"] if isinstance(result, dict) and "message" in result else str(result)
    try:
        audio_path = speak_text(response_text)
    except Exception as e:
        print("Ошибка озвучки:", e)
        audio_path = None

    return {
        "answer": response_text,
        "audio_url": f"http://localhost:8000/{audio_path}" if audio_path else None
    }

@app.post("/api/chat/voice")
async def handle_voice(audio_file: UploadFile = File(...)):
    temp_file = f"temp_{uuid.uuid4()}.webm"
    with open(temp_file, "wb") as f:
        f.write(await audio_file.read())

    question = recognize_speech(temp_file)
    os.remove(temp_file)

    result = process_query(question)

    if isinstance(result, dict) and result.get("status") == "confirmation_needed":
        return {
            "question": question,
            "answer": result["message"],
            "audio_url": None
        }

    response_text = result["message"] if isinstance(result, dict) and "message" in result else str(result)
    try:
        audio_path = speak_text(response_text)
    except Exception as e:
        print("Ошибка озвучки:", e)
        audio_path = None

    return {
        "question": question,
        "answer": response_text,
        "audio_url": f"http://localhost:8000/{audio_path}" if audio_path else None
    }

@app.get("/api/speaking")
async def speaking_status():
    return {"speaking": is_speaking}
