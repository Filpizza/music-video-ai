"""
assembler.py — склейка клипов и аудио в финальный ролик.

В отличие от остальных модулей, не вызывает никаких платных API — работает
одинаково в dry_run и production, всегда через локальный FFmpeg (бесплатно).

Склеивает клипы сцен друг за другом и накладывает поверх звуковую дорожку.
"""

import subprocess
from pathlib import Path

import config


def assemble_video(clip_paths: list, audio_path: str, output_name: str = "final_video.mp4") -> dict:
    """
    Главная функция. Склеивает клипы сцен и добавляет звук.

    clip_paths  — список путей к видеоклипам сцен, в нужном порядке
    audio_path  — путь к аудиофайлу (музыке)
    output_name — имя итогового файла

    Возвращает словарь:
      {
        "output_path": путь к готовому ролику
      }
    """
    print(f"\n🎬 Склейка финального ролика...")
    print(f"   Клипов: {len(clip_paths)}")
    print(f"   Аудио: {audio_path}")

    output_path = config.OUTPUT_DIR / output_name
    concat_list_path = config.WORK_DIR / "concat_list.txt"

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

    subprocess.run(cmd, capture_output=True, check=True)

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
