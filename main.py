"""
main.py — оркестратor. Связывает все модули в единый pipeline.

Полный поток:
  1. brain.improve_prompt()      — улучшаем промпт пользователя
  2. music_generator.generate_music() — генерируем музыку
  3. brain.plan_scenes()         — строим план визуальных сцен
  4. для каждой сцены:
       image_generator.generate_image()   — картинка
       video_generator.generate_video()   — картинка → видеоклип
       quality_checker.check_quality()    — проверка клипа
  5. assembler.assemble_video()  — склейка всех клипов + музыки в финальный ролик

Работает в dry_run (бесплатно, заглушки) или production (реальные API) — режим
берётся из config.MODE.
"""

import re

import brain
import music_generator
import image_generator
import video_generator
import quality_checker
import assembler
import config


def create_music_video(user_prompt: str, num_scenes: int = 3) -> dict:
    """
    Главная функция. Прогоняет весь pipeline от промпта до готового ролика.

    user_prompt — исходное описание клипа от пользователя
    num_scenes  — сколько сцен построить

    Возвращает словарь:
      {
        "output_path": путь к готовому ролику,
        "title": название трека,
        "lyrics": текст песни,
        "scenes": список сцен с их путями к клипам
      }
    """
    duration_sec = num_scenes * config.CLIP_DURATION

    print("=" * 60)
    print("MUSIC VIDEO AI — ЗАПУСК PIPELINE")
    print("=" * 60)

    print("\n[1/5] Улучшение промпта")
    improved_prompt = brain.improve_prompt(user_prompt)

    print("\n[2/5] Генерация музыки")
    music = music_generator.generate_music(improved_prompt, duration_sec)

    print("\n[3/5] Планирование сцен")
    plan = brain.plan_scenes(improved_prompt, music["lyrics"], num_scenes)

    print(f"\n[4/5] Генерация {len(plan['scenes'])} клипов")
    clip_paths = []
    for scene in plan["scenes"]:
        image = image_generator.generate_image(scene["image_prompt"], scene["id"])
        video = video_generator.generate_video(image["image_path"], scene["id"])
        quality = quality_checker.check_quality(video["video_path"], scene["id"])
        if not quality["passed"]:
            print(f"   ⚠️  Сцена {scene['id']} не прошла проверку: {quality['reason']}")
        clip_paths.append(video["video_path"])

    print("\n[5/5] Склейка финального ролика")
    output_name = f"{_slugify(music['title'])}.mp4"
    final = assembler.assemble_video(clip_paths, music["audio_path"], output_name)

    print("\n" + "=" * 60)
    print(f"ГОТОВО: {final['output_path']}")
    print("=" * 60)

    return {
        "output_path": final["output_path"],
        "title": music["title"],
        "lyrics": music["lyrics"],
        "scenes": plan["scenes"],
    }


def _slugify(text: str) -> str:
    """Превращает название трека в безопасное имя файла."""
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE).strip().lower()
    return re.sub(r"[\s]+", "_", text) or "video"


# ─────────────────────────────────────────────────────────────
#  Тест — запусти напрямую: python main.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config.check_config()
    result = create_music_video(
        user_prompt="грустная песня о дожде",
        num_scenes=3,
    )
    print("\nРезультат:")
    for key, value in result.items():
        print(f"  {key}: {value}")
