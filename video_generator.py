"""
video_generator.py — превращение картинки в видеоклип.

В режиме dry_run: делает видео из статичной картинки нужной длины через FFmpeg (заглушка, бесплатно).
В режиме production: вызовет Kling или Veo (подключим позже) — картинка оживает в движении.

Возвращает путь к сгенерированному видеоклипу.
"""

import subprocess
import uuid

import config


def _run_ffmpeg(cmd: list) -> None:
    """Запускает FFmpeg и, если он упал, показывает его реальную ошибку (stderr)."""
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        error_text = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"FFmpeg завершился с ошибкой:\n{error_text}")


def generate_video(image_path: str, scene_id: int = 1, duration_sec: int = None,
                   run_id: str = None) -> dict:
    """
    Главная функция. Превращает картинку в видеоклип.

    image_path   — путь к исходной картинке сцены
    scene_id     — номер сцены (используется в имени файла)
    duration_sec — длина клипа в секундах (по умолчанию — config.CLIP_DURATION)
    run_id       — id запуска для уникального имени файла (если None — сгенерируется)

    Возвращает словарь:
      {
        "video_path": путь к mp4,
        "duration": длина клипа в секундах
      }
    """
    duration_sec = duration_sec or config.CLIP_DURATION

    print(f"\n🎥 Генерация видеоклипа...")
    print(f"   Сцена: {scene_id}")
    print(f"   Картинка: {image_path}")
    print(f"   Длительность: {duration_sec} сек")

    if config.MODE == "dry_run":
        return _generate_dry_run(image_path, scene_id, duration_sec, run_id)
    else:
        return _generate_production(image_path, scene_id, duration_sec)


# ─────────────────────────────────────────────────────────────
#  DRY RUN — заглушка (бесплатно)
# ─────────────────────────────────────────────────────────────
def _generate_dry_run(image_path: str, scene_id: int, duration_sec: int,
                      run_id: str = None) -> dict:
    """Делает видео из статичной картинки нужной длины через FFmpeg (без оживления)."""
    run_id = run_id or uuid.uuid4().hex[:8]
    output_path = config.CLIPS_DIR / f"clip_{scene_id}_{run_id}.mp4"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1",                # зациклить картинку
        "-i", str(image_path),
        "-t", str(duration_sec),     # длительность
        "-r", str(config.VIDEO_FPS),
        "-vf", f"scale={config.VIDEO_WIDTH}:{config.VIDEO_HEIGHT}",
        "-c:v", "libx264",           # явный кодек, не полагаемся на дефолт ffmpeg
        "-pix_fmt", "yuv420p",       # совместимость с большинством плееров
        str(output_path)
    ]

    _run_ffmpeg(cmd)

    print(f"   ✅ [DRY RUN] Создана заглушка: {output_path.name}")

    return {
        "video_path": str(output_path),
        "duration": duration_sec,
    }


# ─────────────────────────────────────────────────────────────
#  PRODUCTION — реальный Kling/Veo (подключим позже)
# ─────────────────────────────────────────────────────────────
def _generate_production(image_path: str, scene_id: int, duration_sec: int) -> dict:
    """Реальное оживление картинки через Kling/Veo. Реализуем на этапе подключения API."""
    raise NotImplementedError(
        "Production-режим Kling/Veo ещё не подключён. "
        "Пока работай в MODE=dry_run."
    )


# ─────────────────────────────────────────────────────────────
#  Тест модуля — запусти напрямую: python video_generator.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import image_generator

    config.check_config()

    image_result = image_generator.generate_image(
        image_prompt="cinematic scene, rain on window, melancholic mood, high detail",
        scene_id=1,
    )
    result = generate_video(
        image_path=image_result["image_path"],
        scene_id=1,
    )
    print("\nРезультат:")
    for key, value in result.items():
        print(f"  {key}: {value}")
