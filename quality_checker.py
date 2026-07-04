"""
quality_checker.py — проверка клипов на галлюцинации.

В режиме dry_run: всегда возвращает "прошло" (заглушка, бесплатно).
В режиме production: вызовет Gemini Vision (подключим позже) — проверит клип
на визуальные артефакты и несоответствия (лишние пальцы, искажённые лица и т.д.).

Возвращает результат проверки: прошёл клип или нет.
"""

import config


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
