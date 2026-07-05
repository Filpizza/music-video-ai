"""
conftest.py — общие настройки для всех тестов pytest.

Лежит в корне проекта, поэтому pytest добавляет корень в путь импорта
(модули config, brain, main и т.д. становятся видны из папки tests/).
"""

import pytest

import config


@pytest.fixture(autouse=True)
def require_dry_run():
    """
    Страховка: все тесты рассчитаны на режим dry_run (заглушки, без трат денег).
    Если случайно запустить их в production — тест сразу честно об этом скажет,
    а не начнёт дёргать платные API.
    """
    assert config.MODE == "dry_run", (
        f"Тесты нужно запускать в MODE=dry_run, а сейчас MODE={config.MODE}. "
        "Проверь .env (или переменную окружения MODE)."
    )
