"""
brain.py — "мозг" проекта на основе Gemini.

Универсальный промпт-движок: пользователь даёт короткую идею, а Gemini,
выступая в роли эксперта-музыканта и режиссёра, сам определяет жанр,
характеристики музыки и подходящий под неё визуальный стиль. Никаких
захардкоженных правил под конкретные жанры — вся экспертиза берётся у Gemini,
поэтому подход одинаково работает для techno, phonk, lo-fi, оркестра, джаза и т.д.

Делает две вещи:
  1. improve_prompt()  — превращает идею в структурированный музыкальный бриф
  2. plan_scenes()     — строит план сцен, визуально соответствующий этой музыке

Gemini бесплатный, поэтому работает по-настоящему если вставлен GEMINI_API_KEY.
Если ключа нет — возвращает разумную заглушку (для теста без ключа).
"""

import json
import time

import httpx

import config

GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/"
    "models/gemini-2.5-flash:generateContent"
)

# Временные ошибки Gemini (перегрузка сервера / превышен лимит запросов в минуту)
_RETRYABLE_STATUS_CODES = {429, 503}
_MAX_RETRIES = 3


def _call_gemini(prompt_text: str, temperature: float = 0.7, max_output_tokens: int = 4096) -> str:
    """Один запрос к Gemini API. Возвращает текст ответа или бросает исключение.

    Повторы (и временные ошибки сети 429/503, и обрезанный JSON) делает
    вызывающий _call_gemini_json — раньше повторы были и здесь, и там, из-за
    чего в худшем случае один вызов превращался в _MAX_RETRIES × _MAX_RETRIES
    обращений к API. Теперь место повторов ровно одно.

    thinkingBudget=0 отключает "размышления" модели — gemini-2.5-flash тратит
    на них часть maxOutputTokens ещё до основного ответа, из-за чего ответ
    иногда обрывался на середине (нужен полный бюджет под сам текст/JSON).
    """
    payload = {
        "contents": [{"parts": [{"text": prompt_text}]}],
        "generationConfig": {
            "temperature": temperature,
            "maxOutputTokens": max_output_tokens,
            "thinkingConfig": {"thinkingBudget": 0},
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


def _call_gemini_json(instruction: str, temperature: float, max_output_tokens: int) -> dict:
    """Вызывает Gemini и парсит JSON-ответ.

    Единый цикл повторов на оба случая: временная ошибка сети (429/503) —
    ждём и пробуем снова; JSON пришёл битым/обрезанным — перегенерируем ответ.
    Ровно один сетевой запрос на попытку (без вложенных повторов).
    """
    for attempt in range(1, _MAX_RETRIES + 1):
        try:
            raw = _call_gemini(instruction, temperature=temperature, max_output_tokens=max_output_tokens)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_RETRIES:
                wait_sec = 5 * attempt
                print(f"   ⏳ Gemini временно недоступен ({exc.response.status_code}), "
                      f"повтор через {wait_sec} сек...")
                time.sleep(wait_sec)
                continue
            raise

        try:
            return _parse_json(raw)
        except json.JSONDecodeError:
            if attempt == _MAX_RETRIES:
                raise
            print(f"   ⏳ Ответ Gemini обрезан/некорректен, повтор попытки {attempt + 1}...")

    # Сюда попадаем только если все попытки ушли на паузы из-за 429/503
    raise RuntimeError("Gemini не ответил после всех попыток (перегрузка/лимит запросов)")


# ─────────────────────────────────────────────────────────────
#  1. Улучшение промпта → структурированный музыкальный бриф
# ─────────────────────────────────────────────────────────────
def improve_prompt(user_prompt: str, mood_hint: str = "", bpm_hint: str = "") -> dict:
    """
    Превращает короткую идею пользователя в структурированный музыкальный бриф.

    user_prompt — идея пользователя, в любом жанре ("грустная баллада",
                  "агрессивный phonk", "спокойный ambient" и т.д.)
    mood_hint   — необязательная подсказка по настроению (если пусто — решает Gemini)
    bpm_hint    — необязательная подсказка по темпу (если пусто — решает Gemini)

    Возвращает словарь:
      {
        "genre": жанр,
        "sub_genre": под-жанр,
        "bpm": диапазон темпа, например "120-130",
        "mood": настроение,
        "key_instruments": [список ключевых инструментов],
        "vocal_type": тип вокала или "instrumental",
        "suno_prompt": готовый промпт для Suno с тегами стиля,
        "negative_tags": [чего в музыке быть не должно],
      }
    """
    print(f"\n🧠 Улучшаю промпт...")
    print(f"   Было: {user_prompt}")

    if not config.GEMINI_API_KEY:
        result = _stub_music_brief(user_prompt, mood_hint, bpm_hint)
        print(f"   ⚠️  [Заглушка, нет ключа] Жанр: {result['genre']}")
        return result

    hints = []
    if mood_hint:
        hints.append(f"Desired mood: {mood_hint}")
    if bpm_hint:
        hints.append(f"Desired tempo (BPM): {bpm_hint}")
    hints_text = ("\n" + "\n".join(hints)) if hints else ""

    instruction = (
        "You are a world-class music producer and A&R expert across every genre — "
        "techno, phonk, lo-fi, synthwave, orchestral, jazz, ambient, ballads, rock, "
        "and everything else. A user gave you a short idea for a track. Using your "
        "own expertise, work out a complete music brief for an AI music generator "
        "(like Suno). Do not follow rigid genre templates — reason about what "
        "actually fits the specific genre implied by the idea.\n\n"
        f'User\'s idea: "{user_prompt}"{hints_text}\n\n'
        "Decide:\n"
        "- genre: the primary genre\n"
        "- sub_genre: a more specific sub-genre/style within it\n"
        "- bpm: a realistic tempo range for this genre, as a string like \"120-130\"\n"
        "- mood: the emotional character of the track\n"
        "- key_instruments: 4-6 instruments/sounds that define this genre's sound\n"
        "- vocal_type: e.g. \"female vocals\", \"male vocals\", \"instrumental\", "
        "\"sampled vocal chops\" — whatever actually fits\n"
        "- suno_prompt: a ready-to-use comma-separated style-tag prompt for Suno "
        "(genre, sub-genre, mood, instruments, tempo, vocal type, production style)\n"
        "- negative_tags: things that must NOT appear in this track (clashing "
        "instruments, moods, or production styles)\n\n"
        "Reply with ONLY valid JSON in this exact shape:\n"
        '{"genre": "...", "sub_genre": "...", "bpm": "...", "mood": "...", '
        '"key_instruments": ["...", "..."], "vocal_type": "...", '
        '"suno_prompt": "...", "negative_tags": ["...", "..."]}'
    )

    result = _call_gemini_json(instruction, temperature=0.8, max_output_tokens=1536)
    print(f"   ✅ Жанр: {result.get('genre')} / {result.get('sub_genre')} "
          f"({result.get('bpm')} BPM, {result.get('mood')})")
    print(f"   Suno-промпт: {result.get('suno_prompt')}")
    return result


def _stub_music_brief(user_prompt: str, mood_hint: str, bpm_hint: str) -> dict:
    """Заглушка на случай отсутствия GEMINI_API_KEY — просто для теста без ключа."""
    return {
        "genre": "Unknown",
        "sub_genre": "Unknown",
        "bpm": bpm_hint or "100-120",
        "mood": mood_hint or "neutral",
        "key_instruments": ["synth", "drums", "bass"],
        "vocal_type": "instrumental",
        "suno_prompt": f"{user_prompt}, professional production, balanced mix, high quality audio",
        "negative_tags": [],
    }


# ─────────────────────────────────────────────────────────────
#  2. Планирование сцен под музыку
# ─────────────────────────────────────────────────────────────
def plan_scenes(music: dict, lyrics: str, num_scenes: int = 5,
                style: str = "", palette_hint: str = "") -> dict:
    """
    Строит план визуальных сцен, подобранный под конкретную музыку из improve_prompt().

    Это ЧЕРНОВИК — пользователь потом правит его в интерфейсе перед генерацией.

    music         — словарь из improve_prompt() (жанр, настроение, инструменты и т.д.)
    lyrics        — текст песни/тема (контекст для сюжета)
    num_scenes    — сколько сцен построить
    style         — закреплённая «визуальная ДНК» (герой/образ), которую нужно держать
                    во всех сценах ради единого стиля серии
    palette_hint  — необязательная подсказка по цветовой гамме (если пусто — решает Gemini)

    Возвращает словарь:
      {
        "color_palette": единая цветовая гамма для всего ролика,
        "scenes": [
          {
            "id": номер сцены,
            "description": короткое описание того, что происходит,
            "image_prompt": промпт того, ЧТО В КАДРЕ (для генератора картинок),
            "motion_prompt": промпт ДВИЖЕНИЯ камеры/субъекта (для Veo),
            "mood": настроение конкретной сцены,
            "negative_tags": [чего в кадре быть не должно],
          },
          ...
        ]
      }
    """
    print(f"\n🎬 Планирую {num_scenes} сцен под жанр {music.get('genre')}...")

    if not config.GEMINI_API_KEY:
        result = _stub_scene_plan(music, num_scenes, style, palette_hint)
        print(f"   ⚠️  [Заглушка, нет ключа] Создано {num_scenes} сцен")
        return result

    instruments = ", ".join(music.get("key_instruments", []))
    palette_line = f"\nRequested color palette: {palette_hint}" if palette_hint else ""
    style_line = (
        f"\nFixed visual style/subject that MUST be present and consistent in EVERY "
        f"scene (do not drift away from it): {style}"
    ) if style else ""

    instruction = (
        "You are an award-winning music video director. You've been given a "
        "fully-produced track and must design the visual concept for its music "
        "video. The visual language MUST match the specific genre and mood — for "
        "example, a slow melancholic ballad and an aggressive dark techno track "
        "should look completely different.\n\n"
        f"Track genre: {music.get('genre')} ({music.get('sub_genre')})\n"
        f"Mood: {music.get('mood')}\n"
        f"BPM: {music.get('bpm')}\n"
        f"Instruments: {instruments}\n"
        f"Vocal: {music.get('vocal_type')}\n"
        f"Lyrics/theme: {lyrics}{palette_line}{style_line}\n\n"
        f"First, decide ONE consistent color_palette for the whole video (2-4 "
        f"sentences describing tones/colors/lighting style) that will be shared "
        f"across every scene for visual consistency.\n\n"
        f"Then create a plan of {num_scenes} scenes that tell a visual story while "
        f"ALL keeping the same fixed style/subject above. For each scene write:\n"
        "- description: short human-readable summary of what happens\n"
        "- image_prompt: a detailed, cinematic English prompt describing WHAT IS IN "
        "THE FRAME (subject, setting, composition, lighting) for an AI image "
        "generator — keep the fixed style/subject and shared color palette\n"
        "- motion_prompt: a short English description of CAMERA/SUBJECT MOVEMENT for "
        "an AI video generator (e.g. 'slow push-in, subtle camera drift')\n"
        "- mood: this scene's emotional tone\n"
        "- negative_tags: things that must NOT appear in this shot\n\n"
        "Reply with ONLY valid JSON in this exact shape:\n"
        '{"color_palette": "...", "scenes": [{"id": 1, "description": "...", '
        '"image_prompt": "...", "motion_prompt": "...", "mood": "...", '
        '"negative_tags": ["...", "..."]}]}'
    )

    max_tokens = 1024 + 500 * num_scenes  # больше сцен — длиннее JSON-ответ
    result = _call_gemini_json(instruction, temperature=0.9, max_output_tokens=max_tokens)
    print(f"   ✅ Создано {len(result.get('scenes', []))} сцен")
    print(f"   Цветовая гамма: {result.get('color_palette')}")
    return result


def _stub_scene_plan(music: dict, num_scenes: int, style: str, palette_hint: str) -> dict:
    """Заглушка на случай отсутствия GEMINI_API_KEY — просто для теста без ключа."""
    genre = music.get("genre", "Unknown")
    palette = palette_hint or "neutral, balanced tones"
    style = style or f"{genre} music video, cinematic, high detail"
    scenes = [
        {
            "id": i + 1,
            "description": f"Сцена {i + 1} для жанра {genre}",
            "image_prompt": f"cinematic scene {i + 1}, {style}, {palette}",
            "motion_prompt": "slow subtle camera drift",
            "mood": music.get("mood", "atmospheric"),
            "negative_tags": [],
        }
        for i in range(num_scenes)
    ]
    return {"color_palette": palette, "scenes": scenes}


# ─────────────────────────────────────────────────────────────
#  Черновик «визуальной ДНК» (стиль/герой ролика)
# ─────────────────────────────────────────────────────────────
def draft_style(user_prompt: str) -> str:
    """Предлагает черновой единый стиль/героя ролика по идее пользователя.

    Возвращает короткую строку-«визуальную ДНК», которую потом принудительно
    дописываем в каждый кадр ради единого стиля всей серии роликов. Пользователь
    может её отредактировать в интерфейсе. Если ключа нет — простая заглушка.
    """
    if not config.GEMINI_API_KEY:
        return f"{user_prompt}, cinematic, high detail, consistent style"

    instruction = (
        "You are an art director for a music-video series that must keep ONE "
        "consistent visual identity across many videos. From the user's idea, write "
        "a single concise 'visual DNA' line (the recurring subject/character plus the "
        "overall look) that will be appended to EVERY shot to keep the whole series "
        "consistent — for example: \"lone cyborg developer, chrome-plated armor, "
        "neon-lit lab, cinematic 4k, moody volumetric lighting\".\n\n"
        f'User\'s idea: "{user_prompt}"\n\n'
        'Reply with ONLY valid JSON: {"style": "..."}'
    )
    result = _call_gemini_json(instruction, temperature=0.7, max_output_tokens=256)
    return result.get("style", f"{user_prompt}, cinematic, high detail")


# ─────────────────────────────────────────────────────────────
#  Тест: python brain.py
# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    config.check_config()

    music = improve_prompt("грустная песня о дожде")
    style = draft_style("грустная песня о дожде")
    print(f"\nСтиль: {style}")

    plan = plan_scenes(
        music=music,
        lyrics="Дождь стучит по крыше, я вспоминаю тебя...",
        num_scenes=3,
        style=style,
    )

    print("\nПлан сцен:")
    for scene in plan.get("scenes", []):
        print(f"  Сцена {scene['id']}: {scene['description']}")
        print(f"    image_prompt:  {scene['image_prompt']}")
        print(f"    motion_prompt: {scene['motion_prompt']}")
