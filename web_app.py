"""
web_app.py — простой веб-интерфейс для запуска pipeline без терминала.

Страница в браузере: промпт, стиль, длительность, кнопка "Создать" и прогресс-бар.
Генерация всегда идёт в текущем режиме config.MODE (для этого веб-интерфейса
предполагается dry_run — без трат денег).

Запуск: venv\\Scripts\\python.exe -m uvicorn web_app:app --reload
Потом открыть в браузере: http://127.0.0.1:8000
"""

import threading
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel

import config
import main

app = FastAPI(title="Music Video AI")

# Варианты стиля, которые пользователь может выбрать в интерфейсе
STYLE_OPTIONS = [
    "Lo-fi / Chill",
    "Indie Folk",
    "Electronic / Synthwave",
    "Cinematic Orchestral",
    "Rock",
    "Pop",
]

# Варианты длительности ролика — кратны длине одного клипа (config.CLIP_DURATION)
DURATION_OPTIONS = [2, 3, 4, 5, 6]  # количество сцен

# Единственная текущая задача генерации (упрощение: одна задача за раз)
job_lock = threading.Lock()
job: dict = {"status": "idle"}


class GenerateRequest(BaseModel):
    prompt: str
    style: str
    num_scenes: int


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("static/index.html")


@app.get("/api/config")
def get_config():
    """Отдаёт странице текущий режим и доступные варианты стиля/длительности."""
    return {
        "mode": config.MODE,
        "clip_duration": config.CLIP_DURATION,
        "styles": STYLE_OPTIONS,
        "duration_options": DURATION_OPTIONS,
    }


@app.post("/api/generate")
def start_generate(req: GenerateRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "Промпт не может быть пустым")
    if req.num_scenes not in DURATION_OPTIONS:
        raise HTTPException(400, "Недопустимая длительность")

    with job_lock:
        if job.get("status") == "running":
            raise HTTPException(409, "Уже идёт генерация, дождись её завершения")
        job.clear()
        job.update({"status": "running", "step": "Запуск...", "percent": 0})

    combined_prompt = f"{req.style}. {req.prompt.strip()}"
    thread = threading.Thread(
        target=_run_pipeline, args=(combined_prompt, req.num_scenes), daemon=True
    )
    thread.start()
    return {"started": True}


def _run_pipeline(prompt: str, num_scenes: int):
    def on_progress(step: str, percent: int):
        with job_lock:
            job["step"] = step
            job["percent"] = percent

    try:
        result = main.create_music_video(prompt, num_scenes, on_progress=on_progress)
        with job_lock:
            job["status"] = "done"
            job["percent"] = 100
            job["step"] = "Готово"
            job["output_path"] = result["output_path"]
            job["title"] = result["title"]
    except Exception as exc:
        with job_lock:
            job["status"] = "error"
            job["error"] = str(exc)


@app.get("/api/status")
def get_status():
    with job_lock:
        return dict(job)


@app.get("/api/video")
def get_video():
    with job_lock:
        output_path = job.get("output_path")
    if not output_path:
        raise HTTPException(404, "Видео ещё не готово")
    return FileResponse(output_path, media_type="video/mp4")
