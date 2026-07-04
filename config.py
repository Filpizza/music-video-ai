"""
config.py — центральные настройки всего проекта.
Читает ключи из .env и определяет режим работы (dry_run / production).
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Загружаем переменные из .env
load_dotenv()

# ── Режим работы ──────────────────────────────────────────────
# "dry_run"    = заглушки, без реальных API, бесплатно
# "production" = реальные вызовы API (тратит деньги)
MODE = os.getenv("MODE", "dry_run").strip().lower()

# ── API ключи ─────────────────────────────────────────────────
GEMINI_API_KEY    = os.getenv("GEMINI_API_KEY", "")
APIFRAME_KEY      = os.getenv("APIFRAME_KEY", "")
FAL_KEY           = os.getenv("FAL_KEY", "")
KLING_API_KEY     = os.getenv("KLING_API_KEY", "")
KLING_API_SECRET  = os.getenv("KLING_API_SECRET", "")

# ── Пути к папкам ─────────────────────────────────────────────
BASE_DIR    = Path(__file__).parent
OUTPUT_DIR  = BASE_DIR / "output"          # готовые ролики
WORK_DIR    = BASE_DIR / "work"            # промежуточные файлы
MUSIC_DIR   = WORK_DIR / "music"
IMAGES_DIR  = WORK_DIR / "images"
CLIPS_DIR   = WORK_DIR / "clips"
ASSETS_DIR  = BASE_DIR / "assets"          # заглушки для dry_run

# Создаём все папки если их нет
for folder in [OUTPUT_DIR, WORK_DIR, MUSIC_DIR, IMAGES_DIR, CLIPS_DIR, ASSETS_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# ── Настройки видео ───────────────────────────────────────────
VIDEO_WIDTH      = 1920
VIDEO_HEIGHT     = 1080
VIDEO_FPS        = 30
CLIP_DURATION    = 8                       # секунд на один клип

# ── Проверка при запуске ──────────────────────────────────────
def check_config():
    """Показывает текущие настройки при старте."""
    print(f"  Режим работы: {MODE.upper()}")
    if MODE == "production":
        print("  ⚠️  PRODUCTION — будут тратиться реальные деньги!")
        missing = []
        if not GEMINI_API_KEY:   missing.append("GEMINI_API_KEY")
        if not APIFRAME_KEY:     missing.append("APIFRAME_KEY")
        if not FAL_KEY:          missing.append("FAL_KEY")
        if not KLING_API_KEY:    missing.append("KLING_API_KEY")
        if missing:
            print(f"  ❌ Не хватает ключей: {', '.join(missing)}")
    else:
        print("  ✅ DRY RUN — заглушки, деньги не тратятся")
    print(f"  Папка результатов: {OUTPUT_DIR}")


if __name__ == "__main__":
    check_config()
