"""
assembler.py — склейка клипов и аудио в финальный ролик.

В отличие от остальных модулей, не вызывает никаких платных API — работает
одинаково в dry_run и production, всегда через локальный FFmpeg (бесплатно).

Склеивает клипы сцен друг за другом и накладывает поверх звуковую дорожку.
"""

import subprocess
import uuid
from pathlib import Path

import config


def _run_ffmpeg(cmd: list) -> None:
    """Запускает FFmpeg и, если он упал, показывает его реальную ошибку (stderr)."""
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        error_text = result.stderr.decode("utf-8", errors="replace").strip()
        raise RuntimeError(f"FFmpeg завершился с ошибкой:\n{error_text}")


def assemble_video(clip_paths: list, audio_path: str, output_name: str = "final_video.mp4",
                   run_id: str = None) -> dict:
    """
    Главная функция. Склеивает клипы сцен и добавляет звук.

    clip_paths  — список путей к видеоклипам сцен, в нужном порядке
    audio_path  — путь к аудиофайлу (музыке)
    output_name — имя итогового файла
    run_id      — id запуска для уникального имени временного списка (если None — сгенерируется)

    Возвращает словарь:
      {
        "output_path": путь к готовому ролику
      }
    """
    print(f"\n🎬 Склейка финального ролика...")
    print(f"   Клипов: {len(clip_paths)}")
    print(f"   Аудио: {audio_path}")

    run_id = run_id or uuid.uuid4().hex[:8]
    output_path = config.OUTPUT_DIR / output_name
    # Уникальное имя списка — чтобы параллельные склейки не писали в один файл
    concat_list_path = config.WORK_DIR / f"concat_list_{run_id}.txt"

    with open(concat_list_path, "w", encoding="utf-8") as f:
        for clip_path in clip_paths:
            f.write(f"file '{Path(clip_path).resolve().as_posix()}'\n")

    cmd = [
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0",
        "-i", str(concat_list_path),   # склеенные клипы (видео)
        "-i", str(audio_path),         # звуковая дорожка
        "-c:v", "copy",                # видео не перекодируем — просто склеиваем
        "-c:a", "aac",
        "-shortest",                   # обрезать по более короткой дорожке
        str(output_path)
    ]

    _run_ffmpeg(cmd)

    print(f"   ✅ Готовый ролик: {output_path.name}")

    return {
        "output_path": str(output_path),
    }


# ─────────────────────────────────────────────────────────────
#  Тест модуля — запусти напрямую: python assembler.py
#  Собирает короткий тестовый ролик из 2 сцен.
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import image_generator
    import video_generator
    import music_generator

    config.check_config()

    scene_prompts = [
        "cinematic scene, rain on window, melancholic mood, high detail",
        "cinematic scene, empty street at night, city lights, high detail",
    ]

    clip_paths = []
    for i, prompt in enumerate(scene_prompts, start=1):
        image_result = image_generator.generate_image(image_prompt=prompt, scene_id=i)
        video_result = video_generator.generate_video(
            image_path=image_result["image_path"], scene_id=i
        )
        clip_paths.append(video_result["video_path"])

    music_result = music_generator.generate_music(
        prompt="melancholic indie ballad about rain",
        duration_sec=len(clip_paths) * config.CLIP_DURATION,
    )

    result = assemble_video(
        clip_paths=clip_paths,
        audio_path=music_result["audio_path"],
        output_name="test_final_dryrun.mp4",
    )
    print("\nРезультат:")
    for key, value in result.items():
        print(f"  {key}: {value}")
