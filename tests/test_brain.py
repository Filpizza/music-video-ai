"""
Тесты для brain.py (Gemini-«мозг»).

Важно: тесты НЕ ходят в сеть и не тратят деньги. Мы проверяем:
  - заглушки, которые brain отдаёт, когда GEMINI_API_KEY пустой;
  - разбор JSON из ответа модели (чистая функция, без сети).
Ключ Gemini мы временно «обнуляем» через monkeypatch, чтобы гарантированно
пойти по пути заглушки.
"""

import brain
import config


def test_improve_prompt_stub_has_all_fields(monkeypatch):
    """Без ключа improve_prompt отдаёт заглушку со всеми нужными полями."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")

    result = brain.improve_prompt("грустная песня о дожде")

    expected_fields = {
        "genre", "sub_genre", "bpm", "mood",
        "key_instruments", "vocal_type", "suno_prompt", "negative_tags",
    }
    assert expected_fields.issubset(result.keys())
    assert isinstance(result["key_instruments"], list)
    assert isinstance(result["negative_tags"], list)


def test_plan_scenes_stub_returns_requested_number(monkeypatch):
    """Без ключа plan_scenes отдаёт ровно столько сцен, сколько попросили."""
    monkeypatch.setattr(config, "GEMINI_API_KEY", "")

    music = brain.improve_prompt("test")  # тоже заглушка
    plan = brain.plan_scenes(music, lyrics="какой-то текст", num_scenes=4)

    assert "color_palette" in plan
    assert len(plan["scenes"]) == 4
    for scene in plan["scenes"]:
        assert "id" in scene
        assert "video_prompt" in scene


def test_parse_json_strips_code_fences():
    """_parse_json умеет убирать ограждение ```json ... ```."""
    raw = '```json\n{"genre": "techno"}\n```'
    assert brain._parse_json(raw) == {"genre": "techno"}


def test_parse_json_extracts_json_from_noise():
    """_parse_json достаёт JSON, даже если модель добавила текст вокруг."""
    raw = 'Вот ответ: {"bpm": "120-130"} — надеюсь, подходит'
    assert brain._parse_json(raw) == {"bpm": "120-130"}
