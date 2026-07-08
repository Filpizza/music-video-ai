"""
quality_checker.py — проверка на галлюцинации/артефакты.

Две проверки:
  check_image()   — РЕАЛЬНАЯ проверка картинки через Gemini Vision, ДО того как
                    картинка уйдёт в видео. Ловит лишние руки/пальцы, искажённые
                    лица, невозможную анатомию. Сама проверка почти бесплатна,
                    а брак, пойманный на этапе картинки, экономит деньги на видео.
  check_quality() — проверка готового клипа (пока dry_run-заглушка; в production
                    подключим Gemini Vision по видео позже).
"""

import base64

import httpx

import brain
import config

def _vision_url() -> str:
    """URL модели проверки (настраивается через config.QUALITY_CHECK_MODEL)."""
    return (
        "https://generativelanguage.googleapis.com/v1beta/"
        f"models/{config.QUALITY_CHECK_MODEL}:generateContent"
    )


# ─────────────────────────────────────────────────────────────
#  Реальная проверка КАРТИНКИ (Gemini Vision) — почти бесплатно
# ─────────────────────────────────────────────────────────────
def check_image(image_path: str, image_prompt: str, negative_tags: list = None) -> dict:
    """
    Показывает картинку Gemini и спрашивает про артефакты.

    image_path    — путь к картинке
    image_prompt  — промпт, по которому она генерировалась (для сверки смысла)
    negative_tags — чего в кадре быть НЕ должно (из плана сцены)

    Возвращает {"passed": bool, "reason": str}.
    Если проверка сама не сработала (сеть, лимиты) — НЕ роняем pipeline,
    а пропускаем картинку с предупреждением (проверка — помощник, не блокер).
    """
    if not config.GEMINI_API_KEY:
        return {"passed": True, "reason": "нет GEMINI_API_KEY — проверка пропущена"}

    print(f"\n🔍 Проверка картинки на артефакты (Gemini Vision)...")

    with open(image_path, "rb") as f:
        image_b64 = base64.b64encode(f.read()).decode("utf-8")

    negative_line = ""
    if negative_tags:
        negative_line = (
            "\nAdditionally, these should NOT appear in the image: "
            + ", ".join(str(t) for t in negative_tags)
            + ". For THIS list fail only if the forbidden element is prominent "
            "and clearly noticeable — a faint hint in a blurred background is "
            "acceptable (regeneration costs money)."
        )

    instruction = (
        "You are a strict quality inspector for AI-generated images used in a "
        "professional music video. Analyze the attached image STEP BY STEP:\n\n"
        "1. body_analysis: count every hand, arm, leg and face visible. For each "
        "limb state WHO it belongs to and whether it connects to a plausible body "
        "at a plausible angle. Unless the prompt explicitly asks for multiple "
        "characters, all limbs must belong to ONE subject with correct anatomy "
        "(max 2 arms/2 hands). Limbs entering the frame from OPPOSITE sides that "
        "cannot belong to the same body = artifact. This applies to robots and "
        "cyborgs too — a humanoid cyborg still has exactly 2 arms attached to one "
        "torso.\n"
        "2. Check for: deformed faces/eyes/teeth, wrong finger count, duplicated "
        "or fused body parts/objects, garbled text, broken geometry.\n"
        f'\nThe image was generated from this prompt: "{image_prompt}"'
        f"{negative_line}\n\n"
        "Minor stylistic imperfections are OK — fail ONLY for clear artifacts a "
        "viewer would notice. But anatomy violations from step 1 ALWAYS fail.\n"
        'Reply with ONLY valid JSON: {"body_analysis": "1-2 sentences: limbs count '
        'and ownership", "passed": true/false, "problems": ["each clear artifact, '
        'empty if none"]}'
    )

    payload = {
        "contents": [{
            "parts": [
                {"text": instruction},
                {"inline_data": {"mime_type": "image/png", "data": image_b64}},
            ]
        }],
        "generationConfig": {
            "temperature": 0.1,      # проверка должна быть стабильной, не творческой
            # Запас под "размышления" модели: анализ анатомии требует подумать,
            # с маленьким лимитом ответ обрезался на середине JSON.
            "maxOutputTokens": 8192,
        },
    }

    try:
        resp = httpx.post(
            f"{_vision_url()}?key={config.GEMINI_API_KEY}",
            json=payload,
            timeout=180,
        )
        resp.raise_for_status()
        raw = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        result = brain._parse_json(raw)
    except Exception as exc:
        print(f"   ⚠️  Проверка не сработала ({exc}) — пропускаю картинку без проверки")
        return {"passed": True, "reason": f"проверка недоступна: {exc}"}

    passed = bool(result.get("passed"))
    problems = result.get("problems") or []
    reason = "; ".join(str(p) for p in problems) if problems else "артефактов не найдено"

    if passed:
        print(f"   ✅ Картинка прошла проверку")
    else:
        print(f"   ❌ Найдены артефакты: {reason}")

    return {"passed": passed, "reason": reason}


def check_quality(video_path: str, scene_id: int = 1) -> dict:
    """
    Главная функция. Проверяет клип на качество.

    video_path — путь к видеоклипу сцены
    scene_id   — номер сцены (для лога)

    Возвращает словарь:
      {
        "passed": прошёл ли клип проверку (bool),
        "reason": пояснение результата
      }
    """
    print(f"\n🔍 Проверка качества...")
    print(f"   Сцена: {scene_id}")
    print(f"   Клип: {video_path}")

    if config.MODE == "dry_run":
        return _check_dry_run(video_path, scene_id)
    else:
        return _check_production(video_path, scene_id)


# ─────────────────────────────────────────────────────────────
#  DRY RUN — заглушка (бесплатно)
# ─────────────────────────────────────────────────────────────
def _check_dry_run(video_path: str, scene_id: int) -> dict:
    """Пропускает проверку — в dry_run клипы всегда 'проходят'."""
    print(f"   ✅ [DRY RUN] Проверка пропущена, клип принят")

    return {
        "passed": True,
        "reason": "dry_run — реальная проверка не выполнялась",
    }


# ─────────────────────────────────────────────────────────────
#  PRODUCTION — реальная проверка через Gemini Vision (подключим позже)
# ─────────────────────────────────────────────────────────────
def _check_production(video_path: str, scene_id: int) -> dict:
    """Реальная проверка на галлюцинации через Gemini Vision. Реализуем на этапе подключения API."""
    raise NotImplementedError(
        "Production-режим Gemini Vision ещё не подключён. "
        "Пока работай в MODE=dry_run."
    )


# ─────────────────────────────────────────────────────────────
#  Тест модуля — запусти напрямую: python quality_checker.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import image_generator
    import video_generator

    config.check_config()

    image_result = image_generator.generate_image(
        image_prompt="cinematic scene, rain on window, melancholic mood, high detail",
        scene_id=1,
    )
    video_result = video_generator.generate_video(
        image_path=image_result["image_path"],
        scene_id=1,
    )
    result = check_quality(
        video_path=video_result["video_path"],
        scene_id=1,
    )
    print("\nРезультат:")
    for key, value in result.items():
        print(f"  {key}: {value}")
