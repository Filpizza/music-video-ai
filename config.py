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

# ── Режим предпросмотра ────────────────────────────────────────
# True  = веб-интерфейс сразу запускает полный pipeline (без показа промптов)
# False = сначала показать промпты (музыка + сцены), запуск — только после подтверждения
AUTO_MODE = os.getenv("AUTO_MODE", "false").strip().lower() == "true"

# ── Провайдер генерации картинок ──────────────────────────────
# Выбирается ОТДЕЛЬНО от MODE — чтобы можно было включить реальные картинки,
# оставив музыку и видео на бесплатных заглушках (dry_run).
#   "stub"   = заглушка через Pillow (БЕСПЛАТНО, по умолчанию)
#   "google" = реальная генерация через Gemini API / Imagen (ТРАТИТ ДЕНЬГИ)
#   "fal"    = Flux через fal.ai (пока не реализовано)
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "stub").strip().lower()

# Модель Google для картинок. Самая дешёвая — Imagen 4 Fast (~$0.02/шт).
IMAGE_MODEL = os.getenv("IMAGE_MODEL", "imagen-4.0-fast-generate-001").strip()

# Ориентировочная цена в USD за одну картинку (для отчёта о тратах).
IMAGE_PRICE_USD = {
    "imagen-4.0-fast-generate-001": 0.02,
    "imagen-4.0-generate-001": 0.04,
    "imagen-4.0-ultra-generate-001": 0.06,
}

# ── ЗАЩИТА ОТ СЛУЧАЙНЫХ ТРАТ ───────────────────────────────────
# Максимум реальных (платных) картинок за один запуск. Если сцен больше —
# код остановится с ошибкой, а не сгенерирует случайно сотни штук.
MAX_IMAGES_PER_RUN = int(os.getenv("MAX_IMAGES_PER_RUN", "3"))

# ── Автопроверка картинок на артефакты (Gemini Vision) ────────
# Gemini смотрит на каждую реальную картинку ДО того, как она уйдёт в видео:
# лишние руки/пальцы, искажённые лица, невозможная анатомия и т.п.
# Сама проверка почти бесплатна; при браке картинка перегенерируется.
IMAGE_QUALITY_CHECK = os.getenv("IMAGE_QUALITY_CHECK", "true").strip().lower() == "true"

# Модель для проверки. Проверено на реальном артефакте (руки с разных сторон):
# gemini-2.5-flash его ПРОПУСКАЕТ, gemini-3-flash-preview и 2.5-pro — ловят.
QUALITY_CHECK_MODEL = os.getenv("QUALITY_CHECK_MODEL", "gemini-3-flash-preview").strip()

# Сколько раз МАКСИМУМ перегенерировать бракованную картинку
# (каждый повтор — это ещё ~$0.02, поэтому держим маленьким).
MAX_IMAGE_RETRIES = int(os.getenv("MAX_IMAGE_RETRIES", "2"))

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

    # Картинки выбираются отдельно от MODE — предупреждаем, если включён платный провайдер
    if IMAGE_PROVIDER == "stub":
        print("  🖼️  Картинки: STUB (заглушка, бесплатно)")
    else:
        price = IMAGE_PRICE_USD.get(IMAGE_MODEL, 0.04)
        print(f"  🖼️  Картинки: {IMAGE_PROVIDER.upper()} / {IMAGE_MODEL} "
              f"— ⚠️ ПЛАТНО, ~${price:.3f}/шт, лимит {MAX_IMAGES_PER_RUN} за запуск")

    print(f"  Папка результатов: {OUTPUT_DIR}")


if __name__ == "__main__":
    check_config()
