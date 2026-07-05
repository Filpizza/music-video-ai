"""
Тест всего конвейера в dry_run — от готового предпросмотра до финального mp4.

Мы НЕ вызываем Gemini (чтобы тест не зависел от сети и ключа): вместо этого
собираем «предпросмотр» вручную с фиктивными сценами и прогоняем через
main.generate_from_preview — это самый ценный тест, он проверяет всю цепочку
картинка -> видео -> проверка качества -> склейка.
"""

import os

import config
import main
import music_generator


def _make_fake_preview(num_scenes=2, run_id="pipetest"):
    """Собирает предпросмотр без обращения к Gemini."""
    duration = num_scenes * config.CLIP_DURATION
    audio = music_generator.generate_music("test music", duration_sec=duration, run_id=run_id)

    scenes = [
        {
            "id": i + 1,
            "description": f"тестовая сцена {i + 1}",
            "video_prompt": f"cinematic test scene {i + 1}, high detail",
            "mood": "test",
            "negative_tags": [],
        }
        for i in range(num_scenes)
    ]

    return {
        "run_id": run_id,
        "user_prompt": "test",
        "num_scenes": num_scenes,
        "music": {},
        "audio_path": audio["audio_path"],
        "lyrics": "la la la",
        "title": "Test Track",
        "color_palette": "neutral tones",
        "scenes": scenes,
    }


def test_full_dry_run_pipeline_produces_mp4(monkeypatch):
    """Весь конвейер в dry_run выдаёт непустой .mp4 с ожидаемым названием."""
    # Укорачиваем клипы до 1 сек — чтобы тест шёл быстро (по умолчанию 8 сек).
    monkeypatch.setattr(config, "CLIP_DURATION", 1)

    preview = _make_fake_preview(num_scenes=2)
    result = main.generate_from_preview(preview)

    assert result["output_path"].endswith(".mp4")
    assert os.path.exists(result["output_path"])
    assert os.path.getsize(result["output_path"]) > 0
    assert result["title"] == "Test Track"


def test_progress_callback_reaches_100(monkeypatch):
    """Прогресс-колбэк вызывается и в конце доходит до 100%."""
    monkeypatch.setattr(config, "CLIP_DURATION", 1)

    percents = []
    preview = _make_fake_preview(num_scenes=2, run_id="progtest")
    main.generate_from_preview(preview, on_progress=lambda step, pct: percents.append(pct))

    assert percents, "колбэк ни разу не вызвался"
    assert percents[-1] == 100


def test_slugify_makes_safe_filenames():
    """_slugify превращает название в безопасное имя файла."""
    assert main._slugify("Test Track") == "test_track"
    assert main._slugify("Привет Мир") == "привет_мир"
    assert main._slugify("!!!") == "video"  # если ничего не осталось — запасное имя
