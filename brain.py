"""
brain.py — "мозг" проекта на основе Gemini.

Делает две вещи:
  1. improve_prompt()  — улучшает твой промпт для лучшего понимания ИИ
  2. plan_scenes()     — строит план сцен для клипа

Gemini бесплатный, поэтому работает по-настоящему если вставлен GEMINI_API_KEY.
Если ключа нет — возвращает разумную заглушку (для теста без ключа).
"""

import json
import httpx

import config

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-1.5-flash:generateContent"
)


def _call_gemini(prompt_text: str, temperature: float = 0.7) -> str:
    """Низкоуровневый вызов Gemini API. Возвращает текст ответа."""
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": 2048,
        },
    }
    resp = httpx.post(
        f"{GEMINI_URL}?key={config.GEMINI_API_KEY}",
        json=payload,
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def _parse_json(raw: str) -> dict:
    """Безопасно достаёт JSON из ответа модели."""
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        # убираем ```json ... ```
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
    cleaned = cleaned.strip().strip("`").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", cleaned, re.DOTALL)
        if m:
            return json.loads(m.group())
        raise


# ─────────────────────────────────────────────────────────────
#  1. Улучшение промпта
# ─────────────────────────────────────────────────────────────
def improve_prompt(user_prompt: str) -> str:
    """Превращает короткий промпт пользователя в детальный музыкальный промпт."""
    print(f"\n🧠 Улучшаю промпт...")
    print(f"   Было: {user_prompt}")

    if not config.GEMINI_API_KEY:
        improved = (
            f"{user_prompt}, professional production, clear melody, "
            f"balanced mix, emotional depth, high quality audio"
        )
        print(f"   ⚠️  [Заглушка, нет ключа] Стало: {improved}")
        return improved

    instruction = (
        "You are a music production expert. Improve this music prompt for an "
        "AI music generator (like Suno). Add genre, tempo, instruments, mood, "
        "and structure. Keep it under 200 characters. Reply with ONLY the "
        f"improved prompt, nothing else.\n\nPrompt: {user_prompt}"
    )
    improved = _call_gemini(instruction, temperature=0.8).strip()
    print(f"   ✅ Стало: {improved}")
    return improved


# ─────────────────────────────────────────────────────────────
#  2. Планирование сцен
# ─────────────────────────────────────────────────────────────
def plan_scenes(music_prompt: str, lyrics: str, num_scenes: int = 5) -> dict:
    """Строит план визуальных сцен для клипа под музыку."""
    print(f"\n🎬 Планирую {num_scenes} сцен...")

    if not config.GEMINI_API_KEY:
        scenes = [
            {
                "id": i + 1,
                "description": f"Сцена {i + 1} для: {music_prompt}",
                "image_prompt": f"cinematic scene {i + 1}, {music_prompt}, high detail",
                "mood": "atmospheric",
            }
            for i in range(num_scenes)
        ]
        print(f"   ⚠️  [Заглушка, нет ключа] Создано {num_scenes} сцен")
        return {"scenes": scenes}

    instruction = (
        f"You are a music video director. Create a plan of {num_scenes} visual "
        f"scenes for a music video.\n\n"
        f"Music style: {music_prompt}\n"
        f"Lyrics: {lyrics}\n\n"
        f"Reply with ONLY valid JSON in this format:\n"
        f'{{"scenes": [{{"id": 1, "description": "...", '
        f'"image_prompt": "detailed English prompt for image generation", '
        f'"mood": "..."}}]}}'
    )
    raw = _call_gemini(instruction, temperature=0.9)
    result = _parse_json(raw)
    print(f"   ✅ Создано {len(result.get('scenes', []))} сцен")
    return result


# ─────────────────────────────────────────────────────────────
#  Тест: python brain.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config.check_config()

    improved = improve_prompt("грустная песня о дожде")

    plan = plan_scenes(
        music_prompt=improved,
        lyrics="Дождь стучит по крыше, я вспоминаю тебя...",
        num_scenes=3,
    )

    print("\nПлан сцен:")
    for scene in plan.get("scenes", []):
        print(f"  Сцена {scene['id']}: {scene['description']}")
        print(f"    image_prompt: {scene['image_prompt']}")
