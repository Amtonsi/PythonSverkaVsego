# Сравнение файлов

Локальное Windows-приложение на Python для сравнения любых файлов: документов, config-файлов, PDF, Excel, изображений и неизвестных бинарных форматов.

## Запуск из PyCharm

Откройте проект `PythonSverkaVsego` и запускайте `main.py`.

## Development

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\python -m pytest
.\.venv\Scripts\python main.py
```

Если текущая `.venv` сломана, удалите ее через PyCharm или создайте новую в настройках интерпретатора.

## Возможности

- современный локальный PySide6-интерфейс;
- выбор файлов через кнопки или drag-and-drop;
- сравнение текстов и config-файлов;
- структурное сравнение JSON/YAML/TOML/INI/XML/env;
- DOCX, PDF, Excel, изображения и бинарный fallback;
- OCR для сканов при установленном `tesseract.exe`;
- HTML-отчет со строками, значениями "было/стало" и сводкой изменений.

## OCR

Python-библиотека `pytesseract` входит в зависимости, но сам движок Tesseract устанавливается отдельно в Windows.
Если `tesseract.exe` не найден в `PATH`, приложение продолжит работать, а OCR будет отмечен как недоступный в диагностике.

## Реестр объектов

В режиме `Реестр объектов` приложение хранит локальную SQLite-базу:

- объекты и подобъекты без ограничения глубины;
- файлы, закрепленные за выбранным объектом;
- baseline-хеш при добавлении файла;
- ручную проверку изменений;
- историю событий мониторинга.

База по умолчанию создается в `%LOCALAPPDATA%\FileCompareRegistry\registry.sqlite3`.

## Сборка exe

```powershell
.\.venv\Scripts\python -m pip install -e ".[dev]"
.\.venv\Scripts\pyinstaller packaging\file-compare-app.spec --clean
```

Готовый файл появится в `dist\Сравнение файлов.exe`.

## Приватность

Приложение работает локально. Текст документов не пишется в логи и не отправляется в сеть.
