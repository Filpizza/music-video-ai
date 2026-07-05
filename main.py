"""
main.py — оркестратор. Связывает все модули в единый pipeline.

Pipeline разбит на два шага, чтобы веб-интерфейс мог сначала показать
пользователю сгенерированные промпты и только потом (по подтверждению)
тратить время на рендер видео:

  create_preview()       — Gemini придумывает музыкальный бриф и план сцен
                            (это единственное место, где идёт обращение к Gemini)
  generate_from_preview() — картинки → видео → проверка → склейка,
                            Gemini здесь больше не вызывается

create_music_video() — удобная обёртка над обоими шагами сразу
                        (используется в CLI-тесте и в режиме config.AUTO_MODE)
"""

import re
import uuid

import brain
import music_generator
import image_generator
import video_generator
import quality_checker
import assembler
import config


def create_preview(user_prompt: str, num_scenes: int = 3,
                    mood_hint: str = "", bpm_hint: str = "", palette_hint: str = "") -> dict:
    """
    Шаг 1: промпт-инжиниринг без рендера видео.

    Вызывает Gemini дважды (музыкальный бриф + план сцен) и создаёт dry_run
    заглушку аудио (бесплатно и локально через FFmpeg — нужна как источник
    текста песни для планирования сцен).

    Возвращает словарь:
      {
        "run_id": уникальный id этого запуска (чтобы файлы не перезаписывались),
        "user_prompt": исходная идея,
        "num_scenes": число сцен,
        "music": бриф из brain.improve_prompt(),
        "audio_path": путь к аудио-заглушке,
        "lyrics": текст песни,
        "title": название трека,
        "color_palette": единая цветовая гамма ролика,
        "scenes": список сцен с их video_prompt,
      }
    """
    duration_sec = num_scenes * config.CLIP_DURATION

    # Уникальный id запуска — чтобы два одновременных запуска не затирали
    # файлы-заглушки друг друга (у каждого будут свои track_/scene_/clip_ файлы).
    run_id = uuid.uuid4().hex[:8]

    music = brain.improve_prompt(user_prompt, mood_hint=mood_hint, bpm_hint=bpm_hint)
    audio = music_generator.generate_music(music["suno_prompt"], duration_sec, run_id=run_id)
    plan = brain.plan_scenes(music, audio["lyrics"], num_scenes, palette_hint=palette_hint)

    return {
        "run_id": run_id,
        "user_prompt": user_prompt,
        "num_scenes": num_scenes,
        "music": music,
        "audio_path": audio["audio_path"],
        "lyrics": audio["lyrics"],
        "title": audio["title"],
        "color_palette": plan["color_palette"],
        "scenes": plan["scenes"],
    }


def generate_from_preview(preview: dict, on_progress=None) -> dict:
    """
    Шаг 2: превращает уже готовый предпросмотр в финальный ролик.
    Gemini здесь не вызывается — все промпты уже согласованы на шаге 1.

    on_progress — необязательная функция(step: str, percent: int) для прогресс-бара.

    Возвращает словарь:
      {
        "output_path": путь к готовому ролику,
        "title": название трека,
        "lyrics": текст песни,
        "scenes": список сцен,
      }
    """
    def notify(step: str, percent: int):
        if on_progress:
            on_progress(step, percent)

    # run_id прокидываем в имена файлов сцен, чтобы клипы разных запусков
    # не перезаписывали друг друга. Старые превью без него — тоже переживут.
    run_id = preview.get("run_id") or uuid.uuid4().hex[:8]
    scenes = preview["scenes"]
    total_scenes = len(scenes)
    clip_paths = []

    print(f"\n[1/2] Генерация {total_scenes} клипов")
    for i, scene in enumerate(scenes):
        scene_percent = 10 + int(70 * i / total_scenes)

        notify(f"Сцена {scene['id']}/{total_scenes}: картинка", scene_percent)
        image = image_generator.generate_image(scene["video_prompt"], scene["id"], run_id=run_id)

        notify(f"Сцена {scene['id']}/{total_scenes}: видео", scene_percent)
        video = video_generator.generate_video(image["image_path"], scene["id"], run_id=run_id)

        notify(f"Сцена {scene['id']}/{total_scenes}: проверка качества", scene_percent)
        quality = quality_checker.check_quality(video["video_path"], scene["id"])
        if not quality["passed"]:
            print(f"   ⚠️  Сцена {scene['id']} не прошла проверку: {quality['reason']}")
        clip_paths.append(video["video_path"])

    print("\n[2/2] Склейка финального ролика")
    notify("Склейка финального ролика", 90)
    output_name = f"{_slugify(preview['title'])}_{run_id}.mp4"
    final = assembler.assemble_video(clip_paths, preview["audio_path"], output_name, run_id=run_id)

    print(f"\nГОТОВО: {final['output_path']}")
    notify("Готово", 100)

    return {
        "output_path": final["output_path"],
        "title": preview["title"],
        "lyrics": preview["lyrics"],
        "scenes": scenes,
    }


def create_music_video(user_prompt: str, num_scenes: int = 3,
                        mood_hint: str = "", bpm_hint: str = "", palette_hint: str = "",
                        on_progress=None) -> dict:
    """Удобная обёртка: весь pipeline сразу, без ручного предпросмотра (режим "автомат")."""
    def notify(step: str, percent: int):
        if on_progress:
            on_progress(step, percent)

    print("=" * 60)
    print("MUSIC VIDEO AI — ЗАПУСК PIPELINE")
    print("=" * 60)

    notify("Улучшение промпта и планирование сцен", 5)
    preview = create_preview(user_prompt, num_scenes, mood_hint, bpm_hint, palette_hint)

    return generate_from_preview(preview, on_progress=on_progress)


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
