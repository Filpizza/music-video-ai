"""
image_generator.py — генерация изображений для сцен.

В режиме dry_run: создаёт цветную placeholder-картинку нужного размера (заглушка, бесплатно).
В режиме production: вызовет Flux через fal.ai (подключим позже).

Возвращает путь к сгенерированному изображению.
"""

import hashlib
import textwrap
import uuid

from PIL import Image, ImageDraw, ImageFont

import config


def generate_image(image_prompt: str, scene_id: int = 1, run_id: str = None) -> dict:
    """
    Главная функция. Генерирует изображение по текстовому промпту.

    image_prompt — детальное описание сцены (на английском, для генератора картинок)
    scene_id     — номер сцены (используется в имени файла)
    run_id       — id запуска для уникального имени файла (если None — сгенерируется)

    Возвращает словарь:
      {
        "image_path": путь к картинке,
        "prompt": промпт, из которого сгенерировано изображение
      }
    """
    print(f"\n🖼️  Генерация изображения...")
    print(f"   Сцена: {scene_id}")
    print(f"   Промпт: {image_prompt}")

    if config.MODE == "dry_run":
        return _generate_dry_run(image_prompt, scene_id, run_id)
    else:
        return _generate_production(image_prompt, scene_id)


# ─────────────────────────────────────────────────────────────
#  DRY RUN — заглушка (бесплатно)
# ─────────────────────────────────────────────────────────────
def _generate_dry_run(image_prompt: str, scene_id: int, run_id: str = None) -> dict:
    """Создаёт цветную placeholder-картинку нужного размера через Pillow."""
    run_id = run_id or uuid.uuid4().hex[:8]
    output_path = config.IMAGES_DIR / f"scene_{scene_id}_{run_id}.png"

    # Цвет зависит от промпта — чтобы разные сцены визуально отличались
    color = _color_from_text(image_prompt)

    image = Image.new("RGB", (config.VIDEO_WIDTH, config.VIDEO_HEIGHT), color)
    draw = ImageDraw.Draw(image)

    title_font = _load_font(120)
    prompt_font = _load_font(40)

    # Крупный номер сцены по центру
    title = f"SCENE {scene_id}"
    title_box = draw.textbbox((0, 0), title, font=title_font)
    title_w, title_h = title_box[2] - title_box[0], title_box[3] - title_box[1]
    title_x = (config.VIDEO_WIDTH - title_w) / 2
    title_y = config.VIDEO_HEIGHT / 2 - title_h - 40
    draw.text(
        (title_x, title_y), title, font=title_font,
        fill="white", stroke_width=4, stroke_fill="black",
    )

    # Промпт, разбитый на строки, под номером сцены
    wrapped_lines = textwrap.wrap(image_prompt, width=60)
    line_y = title_y + title_h + 60
    for line in wrapped_lines:
        line_box = draw.textbbox((0, 0), line, font=prompt_font)
        line_w = line_box[2] - line_box[0]
        line_x = (config.VIDEO_WIDTH - line_w) / 2
        draw.text(
            (line_x, line_y), line, font=prompt_font,
            fill="white", stroke_width=2, stroke_fill="black",
        )
        line_y += 50

    draw.text(
        (40, 40), "DRY RUN", font=prompt_font,
        fill="white", stroke_width=2, stroke_fill="black",
    )

    image.save(output_path)

    print(f"   ✅ [DRY RUN] Создана заглушка: {output_path.name}")

    return {
        "image_path": str(output_path),
        "prompt": image_prompt,
    }


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Пытается загрузить Arial нужного размера, иначе — встроенный шрифт Pillow."""
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default(size=size)


def _color_from_text(text: str) -> tuple:
    """Превращает текст промпта в стабильный RGB-цвет (для наглядности в dry_run)."""
    digest = hashlib.md5(text.encode("utf-8")).hexdigest()
    return tuple(int(digest[i:i + 2], 16) for i in (0, 2, 4))


# ─────────────────────────────────────────────────────────────
#  PRODUCTION — реальный Flux через fal.ai (подключим позже)
# ─────────────────────────────────────────────────────────────
def _generate_production(image_prompt: str, scene_id: int) -> dict:
    """Реальная генерация через Flux (fal.ai). Реализуем на этапе подключения API."""
    raise NotImplementedError(
        "Production-режим Flux ещё не подключён. "
        "Пока работай в MODE=dry_run."
    )


# ─────────────────────────────────────────────────────────────
#  Тест модуля — запусти напрямую: python image_generator.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config.check_config()
    result = generate_image(
        image_prompt="cinematic scene, rain on window, melancholic mood, high detail",
        scene_id=1,
    )
    print("\nРезультат:")
    for key, value in result.items():
        print(f"  {key}: {value}")
