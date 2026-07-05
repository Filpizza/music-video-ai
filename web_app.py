"""
web_app.py — веб-интерфейс для запуска pipeline без терминала.

Два режима работы (переключаются галочкой на странице, по умолчанию — первый):
  1. Предпросмотр (config.AUTO_MODE = False): пользователь жмёт "Показать
     промпты" → Gemini придумывает музыкальный бриф и план сцен, страница
     показывает их. Только после нажатия "Создать клип" запускается рендер
     (картинки/видео/склейка) — Gemini на этом шаге уже не вызывается.
  2. Автомат (config.AUTO_MODE = True или галочка на странице): одна кнопка
     сразу запускает весь pipeline от идеи до готового ролика.

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

# Варианты длительности ролика — кратны длине одного клипа (config.CLIP_DURATION)
DURATION_OPTIONS = [2, 3, 4, 5, 6]  # количество сцен

# Единственная текущая задача генерации (упрощение: одна задача за раз)
job_lock = threading.Lock()
job: dict = {"status": "idle"}

# Последний сгенерированный предпросмотр (промпты музыки + сцен)
preview_lock = threading.Lock()
current_preview: dict = {}


class PromptRequest(BaseModel):
    prompt: str
    num_scenes: int
    mood_hint: str = ""
    bpm_hint: str = ""
    palette_hint: str = ""


class ConfirmRequest(BaseModel):
    preview_id: str


@app.get("/", response_class=HTMLResponse)
def index():
    return FileResponse("static/index.html")


@app.get("/api/config")
def get_config():
    """Отдаёт странице текущий режим и доступные варианты длительности."""
    return {
        "mode": config.MODE,
        "clip_duration": config.CLIP_DURATION,
        "duration_options": DURATION_OPTIONS,
        "auto_mode_default": config.AUTO_MODE,
    }


def _validate_prompt_request(req: PromptRequest):
    if not req.prompt.strip():
        raise HTTPException(400, "Промпт не может быть пустым")
    if req.num_scenes not in DURATION_OPTIONS:
        raise HTTPException(400, "Недопустимая длительность")


# ─────────────────────────────────────────────────────────────
#  Режим предпросмотра: сначала промпты, потом (по подтверждению) рендер
# ─────────────────────────────────────────────────────────────
@app.post("/api/preview")
def create_preview_endpoint(req: PromptRequest):
    _validate_prompt_request(req)
    try:
        preview = main.create_preview(
            req.prompt.strip(), req.num_scenes,
            mood_hint=req.mood_hint.strip(),
            bpm_hint=req.bpm_hint.strip(),
            palette_hint=req.palette_hint.strip(),
        )
    except Exception as exc:
        raise HTTPException(500, str(exc))

    preview_id = str(uuid.uuid4())
    with preview_lock:
        current_preview.clear()
        current_preview.update({"id": preview_id, "data": preview})

    return {"preview_id": preview_id, **preview}


@app.post("/api/confirm")
def confirm_generate(req: ConfirmRequest):
    with preview_lock:
        if current_preview.get("id") != req.preview_id:
            raise HTTPException(409, "Промпты устарели — сгенерируй предпросмотр заново")
        preview_data = current_preview["data"]

    with job_lock:
        if job.get("status") == "running":
            raise HTTPException(409, "Уже идёт генерация, дождись её завершения")
        job.clear()
        job.update({"status": "running", "step": "Запуск...", "percent": 0})

    thread = threading.Thread(target=_run_from_preview, args=(preview_data,), daemon=True)
    thread.start()
    return {"started": True}


def _run_from_preview(preview_data: dict):
    def on_progress(step: str, percent: int):
        with job_lock:
            job["step"] = step
            job["percent"] = percent

    try:
        result = main.generate_from_preview(preview_data, on_progress=on_progress)
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


# ─────────────────────────────────────────────────────────────
#  Режим автомата: идея → сразу готовый ролик, без показа промптов
# ─────────────────────────────────────────────────────────────
@app.post("/api/generate_auto")
def generate_auto(req: PromptRequest):
    _validate_prompt_request(req)

    with job_lock:
        if job.get("status") == "running":
            raise HTTPException(409, "Уже идёт генерация, дождись её завершения")
        job.clear()
        job.update({"status": "running", "step": "Запуск...", "percent": 0})

    thread = threading.Thread(
        target=_run_auto,
        args=(req.prompt.strip(), req.num_scenes,
              req.mood_hint.strip(), req.bpm_hint.strip(), req.palette_hint.strip()),
        daemon=True,
    )
    thread.start()
    return {"started": True}


def _run_auto(prompt: str, num_scenes: int, mood_hint: str, bpm_hint: str, palette_hint: str):
    def on_progress(step: str, percent: int):
        with job_lock:
            job["step"] = step
            job["percent"] = percent

    try:
        result = main.create_music_video(
            prompt, num_scenes, mood_hint=mood_hint, bpm_hint=bpm_hint,
            palette_hint=palette_hint, on_progress=on_progress,
        )
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


# ─────────────────────────────────────────────────────────────
#  Общие эндпоинты для обоих режимов
# ─────────────────────────────────────────────────────────────
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
