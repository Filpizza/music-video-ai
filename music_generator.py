"""
music_generator.py — генерация музыки.

В режиме dry_run: создаёт тихий MP3-файл нужной длины (заглушка, бесплатно).
В режиме production: вызовет Suno через Apiframe (подключим позже).

Возвращает путь к сгенерированному аудиофайлу и метаданные (текст песни и т.д.).
"""

import subprocess
from pathlib import Path

import config


def generate_music(prompt: str, duration_sec: int = 30) -> dict:
    """
    Главная функция. Генерирует музыку по текстовому промпту.

    prompt       — описание желаемой музыки (жанр, настроение и т.д.)
    duration_sec — желаемая длина трека в секундах

    Возвращает словарь:
      {
        "audio_path": путь к mp3,
        "lyrics": текст песни,
        "title": название,
        "duration": длина в секундах
      }
    """
    print(f"\n🎵 Генерация музыки...")
    print(f"   Промпт: {prompt}")
    print(f"   Длительность: {duration_sec} сек")

    if config.MODE == "dry_run":
        return _generate_dry_run(prompt, duration_sec)
    else:
        return _generate_production(prompt, duration_sec)


# ─────────────────────────────────────────────────────────────
#  DRY RUN — заглушка (бесплатно)
# ─────────────────────────────────────────────────────────────
def _generate_dry_run(prompt: str, duration_sec: int) -> dict:
    """Создаёт тихий MP3 нужной длины через FFmpeg."""
    output_path = config.MUSIC_DIR / "track_dryrun.mp3"

    # FFmpeg генерирует тишину заданной длины
    cmd = [
        "ffmpeg", "-y",              # -y = перезаписать без вопросов
        "-f", "lavfi",              # генератор сигнала
        "-i", f"anullsrc=r=44100:cl=stereo",  # тишина, стерео, 44.1кГц
        "-t", str(duration_sec),    # длительность
        "-q:a", "9",                # качество (не важно для тишины)
        str(output_path)
    ]

    subprocess.run(cmd, capture_output=True, check=True)

    print(f"   ✅ [DRY RUN] Создана заглушка: {output_path.name}")

    return {
        "audio_path": str(output_path),
        "lyrics": f"[Заглушка текста песни для промпта: {prompt}]",
        "title": "Dry Run Track",
        "duration": duration_sec,
    }


# ─────────────────────────────────────────────────────────────
#  PRODUCTION — реальный Suno (подключим позже)
# ─────────────────────────────────────────────────────────────
def _generate_production(prompt: str, duration_sec: int) -> dict:
    """Реальная генерация через Suno API. Реализуем на этапе подключения API."""
    raise NotImplementedError(
        "Production-режим Suno ещё не подключён. "
        "Пока работай в MODE=dry_run."
    )


# ─────────────────────────────────────────────────────────────
#  Тест модуля — запусти напрямую: python music_generator.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config.check_config()
    result = generate_music(
        prompt="Спокойный лоу-фай бит для расслабления, мягкое пианино",
        duration_sec=10
    )
    print("\nРезультат:")
    for key, value in result.items():
        print(f"  {key}: {value}")
