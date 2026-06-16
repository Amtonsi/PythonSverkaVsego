"""
Сравнение файлов

Главный файл запуска проекта для PyCharm.

Весь основной код приложения находится в папке:
    src/file_compare_app/

Зачем так сделано:
    - main.py остается простой точкой запуска;
    - логика сравнения, интерфейс, отчеты и анализаторы лежат отдельно;
    - проект проще тестировать и собирать в .exe.

Чтобы запустить приложение:
    1. Откройте этот файл в PyCharm.
    2. Нажмите зеленую кнопку Run.
"""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SOURCE_ROOT = PROJECT_ROOT / "src"

if str(SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(SOURCE_ROOT))

from file_compare_app.__main__ import main


if __name__ == "__main__":
    raise SystemExit(main())
