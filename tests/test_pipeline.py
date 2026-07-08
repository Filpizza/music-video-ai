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
import quality_checker


def _make_fake_preview(num_scenes=2, run_id="pipetest"):
    """Собирает предпросмотр без обращения к Gemini."""
    duration = num_scenes * config.CLIP_DURATION
    audio = music_generator.generate_music("test music", duration_sec=duration, run_id=run_id)

    scenes = [
        {
            "id": i + 1,
            "description": f"тестовая сцена {i + 1}",
            "image_prompt": f"cinematic test scene {i + 1}, high detail",
            "motion_prompt": "slow drift",
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
        "music_prompt": "test music prompt",
        "style": "",
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


def test_style_is_appended_to_every_image_prompt(monkeypatch):
    """Закреплённый стиль дописывается в промпт КАЖДОГО кадра.

    Подменяем генераторы заглушками, чтобы проверить именно текст промпта,
    не создавая реальных файлов и не гоняя FFmpeg.
    """
    captured_prompts = []

    def fake_generate_image(image_prompt, scene_id=1, run_id=None):
        captured_prompts.append(image_prompt)
        return {"image_path": "dummy.png", "prompt": image_prompt}

    monkeypatch.setattr(main.image_generator, "generate_image", fake_generate_image)
    monkeypatch.setattr(main.video_generator, "generate_video",
                        lambda *a, **k: {"video_path": "dummy.mp4", "duration": 1})
    monkeypatch.setattr(main.assembler, "assemble_video",
                        lambda *a, **k: {"output_path": "dummy_out.mp4"})

    preview = _make_fake_preview(num_scenes=2, run_id="styletest")
    preview["style"] = "CYBORG_DNA_TOKEN"
    for scene in preview["scenes"]:
        scene["image_prompt"] = "a lab desk"

    main.generate_from_preview(preview)

    assert len(captured_prompts) == 2
    for prompt in captured_prompts:
        assert "a lab desk" in prompt          # текст сцены сохранён
        assert "CYBORG_DNA_TOKEN" in prompt     # стиль принудительно добавлен


def test_progress_callback_reaches_100(monkeypatch):
    """Прогресс-колбэк вызывается и в конце доходит до 100%."""
    monkeypatch.setattr(config, "CLIP_DURATION", 1)

    percents = []
    preview = _make_fake_preview(num_scenes=2, run_id="progtest")
    main.generate_from_preview(preview, on_progress=lambda step, pct: percents.append(pct))

    assert percents, "колбэк ни разу не вызвался"
    assert percents[-1] == 100


def test_artifact_image_is_regenerated(monkeypatch):
    """Если Gemini Vision нашёл артефакт — картинка перегенерируется.

    Сценарий: сцена 1 бракуется один раз (две руки с разных сторон),
    перегенерация проходит; сцена 2 проходит сразу.
    Итого генераций картинок: 2 сцены + 1 перегенерация = 3.
    """
    monkeypatch.setattr(config, "CLIP_DURATION", 1)
    monkeypatch.setattr(config, "IMAGE_PROVIDER", "google")   # проверка только для платных
    monkeypatch.setattr(config, "IMAGE_QUALITY_CHECK", True)
    monkeypatch.setattr(config, "MAX_IMAGE_RETRIES", 2)

    gen_calls = []

    def fake_generate_image(image_prompt, scene_id=1, run_id=None):
        gen_calls.append(run_id)
        return {"image_path": f"fake_{len(gen_calls)}.png", "prompt": image_prompt}

    check_results = iter([
        {"passed": False, "reason": "two hands from different sides"},  # сцена 1, брак
        {"passed": True, "reason": "ok"},                               # сцена 1, после перегенерации
        {"passed": True, "reason": "ok"},                               # сцена 2
    ])
    check_calls = []

    def fake_check_image(image_path, image_prompt, negative_tags=None):
        check_calls.append(image_path)
        return next(check_results)

    monkeypatch.setattr(main.image_generator, "generate_image", fake_generate_image)
    monkeypatch.setattr(main.quality_checker, "check_image", fake_check_image)
    monkeypatch.setattr(main.video_generator, "generate_video",
                        lambda *a, **k: {"video_path": "dummy.mp4", "duration": 1})
    monkeypatch.setattr(main.assembler, "assemble_video",
                        lambda *a, **k: {"output_path": "dummy_out.mp4"})

    preview = _make_fake_preview(num_scenes=2, run_id="artifacttest")
    main.generate_from_preview(preview)

    assert len(gen_calls) == 3, "ожидалось 2 сцены + 1 перегенерация"
    assert len(check_calls) == 3, "каждая версия картинки должна проверяться"


def test_check_image_without_key_does_not_block(monkeypatch):
    """Без GEMINI_API_KEY проверка не блокирует pipeline (passed=True)."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")
    result = quality_checker.check_image("nonexistent.png", "any prompt")
    assert result["passed"] is True


def test_slugify_makes_safe_filenames():
    """_slugify превращает название в безопасное имя файла."""
    assert main._slugify("Test Track") == "test_track"
    assert main._slugify("Привет Мир") == "привет_мир"
    assert main._slugify("!!!") == "video"  # если ничего не осталось — запасное имя
