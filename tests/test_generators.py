"""
Тесты генераторов-заглушек (dry_run): музыка, картинка, видео.

Проверяем, что каждый генератор реально создаёт файл на диске, кладёт его
под уникальным (по run_id) именем и что картинка нужного размера.
Всё локально через FFmpeg/Pillow — денег не тратит.
"""

import os

from PIL import Image

import config
import image_generator
import music_generator
import video_generator


def test_music_dry_run_creates_file():
    """Музыка-заглушка создаёт непустой mp3 с именем по run_id."""
    result = music_generator.generate_music("test prompt", duration_sec=2, run_id="testmus")

    assert result["audio_path"].endswith("track_testmus.mp3")
    assert os.path.exists(result["audio_path"])
    assert os.path.getsize(result["audio_path"]) > 0
    assert result["duration"] == 2


def test_image_dry_run_has_video_dimensions():
    """Картинка-заглушка ровно того размера, что настроен для видео."""
    result = image_generator.generate_image("cinematic test scene", scene_id=1, run_id="testimg")

    assert os.path.exists(result["image_path"])
    with Image.open(result["image_path"]) as im:
        assert im.size == (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)


def test_video_dry_run_creates_file():
    """Видео-заглушка создаёт mp4 из картинки, имя — по scene_id и run_id."""
    image = image_generator.generate_image("scene for video", scene_id=2, run_id="testvid")
    result = video_generator.generate_video(
        image["image_path"], scene_id=2, duration_sec=2, run_id="testvid"
    )

    assert result["video_path"].endswith("clip_2_testvid.mp4")
    assert os.path.exists(result["video_path"])
    assert os.path.getsize(result["video_path"]) > 0


def test_run_id_makes_filenames_unique():
    """Разный run_id -> разные файлы (это тот самый баг, что мы чинили:
    раньше одинаковые имена перезаписывали друг друга)."""
    a = image_generator.generate_image("same prompt", scene_id=1, run_id="aaaaaaaa")
    b = image_generator.generate_image("same prompt", scene_id=1, run_id="bbbbbbbb")

    assert a["image_path"] != b["image_path"]
    assert os.path.exists(a["image_path"])
    assert os.path.exists(b["image_path"])
