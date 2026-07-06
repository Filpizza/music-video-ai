"""
image_generator.py — генерация изображений для сцен.

Провайдер выбирается настройкой config.IMAGE_PROVIDER (ОТДЕЛЬНО от config.MODE),
чтобы можно было включить реальные картинки, оставив музыку и видео на заглушках:
  "stub"   — цветная placeholder-картинка через Pillow (бесплатно, по умолчанию);
  "google" — реальная генерация через Gemini API / Imagen (ТРАТИТ ДЕНЬГИ);
  "fal"    — Flux через fal.ai (пока не реализовано).

Возвращает путь к сгенерированному изображению.
"""

import base64
import hashlib
import textwrap
import uuid

import httpx
from PIL import Image, ImageDraw, ImageFont

import config

# Сколько реальных (платных) картинок уже создано за жизнь процесса.
# Служит предохранителем против случайных больших трат (см. MAX_IMAGES_PER_RUN).
_paid_images_generated = 0


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

    provider = config.IMAGE_PROVIDER
    if provider == "google":
        return _generate_google(image_prompt, scene_id, run_id)
    elif provider == "fal":
        return _generate_production(image_prompt, scene_id)
    else:
        # "stub" и любое незнакомое значение -> безопасная бесплатная заглушка
        return _generate_dry_run(image_prompt, scene_id, run_id)


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
#  GOOGLE — реальная генерация через Gemini API / Imagen (ПЛАТНО)
# ─────────────────────────────────────────────────────────────
def _generate_google(image_prompt: str, scene_id: int, run_id: str = None) -> dict:
    """Генерирует настоящую картинку через Imagen (Gemini API) по тому же ключу.

    Тратит деньги (~$0.02 за Imagen 4 Fast). Защищён лимитом
    config.MAX_IMAGES_PER_RUN и подробной обработкой ошибок — при любой
    проблеме бросает понятное исключение, а не роняет весь pipeline безлико.
    """
    global _paid_images_generated

    # --- Предохранитель от случайных больших трат ---
    if _paid_images_generated >= config.MAX_IMAGES_PER_RUN:
        raise RuntimeError(
            f"Достигнут лимит картинок MAX_IMAGES_PER_RUN={config.MAX_IMAGES_PER_RUN}. "
            f"Остановился, чтобы не потратить лишнего. Если это осознанно — подними "
            f"лимит в config.py или переменной окружения MAX_IMAGES_PER_RUN."
        )

    if not config.GEMINI_API_KEY:
        raise RuntimeError("Нет GEMINI_API_KEY в .env — реальная генерация невозможна.")

    run_id = run_id or uuid.uuid4().hex[:8]
    model = config.IMAGE_MODEL
    price = config.IMAGE_PRICE_USD.get(model, 0.04)
    print(f"   💸 [GOOGLE] Модель {model} — платно, ~${price:.3f} за картинку")

    url = (
        f"https://generativelanguage.googleapis.com/v1beta/"
        f"models/{model}:predict?key={config.GEMINI_API_KEY}"
    )
    payload = {
        "instances": [{"prompt": image_prompt}],
        "parameters": {
            "sampleCount": 1,
            "aspectRatio": "16:9",  # под наш формат 1920x1080
        },
    }

    # 1) Сетевой запрос — ловим таймауты и обрывы сети
    try:
        resp = httpx.post(url, json=payload, timeout=120)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Ошибка сети при запросе картинки к Google: {exc}") from exc

    # 2) HTTP-статус — показываем читаемую причину, а не голый код
    if resp.status_code != 200:
        raise RuntimeError(
            f"Google вернул ошибку {resp.status_code} при генерации картинки:\n"
            f"{resp.text[:600]}"
        )

    # 3) Разбор ответа — картинка могла быть отклонена фильтром безопасности
    data = resp.json()
    predictions = data.get("predictions") or []
    if not predictions:
        raise RuntimeError(
            "Google не вернул картинку (пустой список predictions). Возможно, промпт "
            f"отклонён фильтром безопасности. Ответ: {str(data)[:600]}"
        )

    b64 = predictions[0].get("bytesBase64Encoded")
    if not b64:
        raise RuntimeError(
            f"В ответе Google нет данных картинки: {str(predictions[0])[:400]}"
        )

    # 4) Сохраняем картинку на диск
    image_bytes = base64.b64decode(b64)
    output_path = config.IMAGES_DIR / f"scene_{scene_id}_{run_id}_google.png"
    with open(output_path, "wb") as f:
        f.write(image_bytes)

    _paid_images_generated += 1
    print(
        f"   ✅ [GOOGLE] Сохранено: {output_path.name} ({len(image_bytes) // 1024} КБ). "
        f"Потрачено ~${price:.3f}. За этот процесс: "
        f"{_paid_images_generated}/{config.MAX_IMAGES_PER_RUN}"
    )

    return {
        "image_path": str(output_path),
        "prompt": image_prompt,
        "provider": "google",
        "model": model,
        "cost_usd": price,
    }


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
