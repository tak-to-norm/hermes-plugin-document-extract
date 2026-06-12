<p align="center">
  <img src="assets/logo.png" alt="Логотип Hermes Document Extract Plugin" width="160" />
</p>

<h1 align="center">Hermes Document Extract Plugin</h1>

<p align="center">
  Локальное извлечение документов и изображений для Hermes Agent: файлы → cached Markdown → текст для агента.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
  <a href="README.md">English README</a>
</p>

> Сделано под native plugin system [Hermes Agent](https://github.com/NousResearch/hermes-agent). Community plugin; это не официальный плагин Nous Research / Hermes Agent.

## Интеграция с Hermes Agent

Hermes Agent — open-source AI agent framework с инструментами. Этот плагин добавляет извлечение документов как native Hermes tools, чтобы агент мог сам вызывать их, когда пользователь просит посмотреть локальный PDF, Office-документ, таблицу, презентацию, архив или изображение.

Плагин устанавливается через `hermes plugins install`, регистрируется в существующий toolset `file` и работает в обычных CLI/gateway-сессиях Hermes после restart/reset.

## Что делает плагин

`hermes-plugin-document-extract` добавляет Hermes tools, которые конвертируют локальные документы и изображения в Markdown перед тем, как агент их читает.

```text
PDF / DOCX / изображение / папка
        ↓
document_extract
        ↓
~/.hermes/cache/document-extract/*.md
        ↓
Hermes читает Markdown через read_file
```

Это уменьшает расход контекста, не заставляет агента читать бинарные файлы напрямую и ускоряет повторную обработку за счёт cache reuse.

## Зачем использовать

- **Меньше контекста**: tool возвращает `markdown_path`, а не весь текст документа.
- **Локальная обработка**: для extraction и OCR не нужны внешние API-ключи.
- **Удобно для агента**: tools регистрируются в существующий Hermes toolset `file`.
- **Повторяемость**: cache reuse по SHA-256 для неизменённых файлов.
- **Приватность при необходимости**: режим `sensitive` отключает preview и использует короткий TTL cache.

## Tools

| Tool | Когда использовать | Что возвращает |
|---|---|---|
| `document_extract` | Один файл: PDF, DOCX, XLSX, PPTX, изображение и т.д. | `markdown_path`, metadata, warnings |
| `document_extract_batch` | Папка или список файлов | `manifest_path` + результаты по каждому файлу |
| `document_extract_status` | Диагностика установки | Статус MarkItDown/Tesseract/Pillow/cache |
| `document_extract_cleanup` | Очистка extracted text | Количество/размер удалённых файлов, dry-run |

Все tools доступны через существующий Hermes toolset `file`. Отдельный видимый toolset или skill не устанавливается.

## Поддерживаемые форматы

| Вход | Движок | Примечания |
|---|---|---|
| PDF | MarkItDown | Лучше всего для текстовых PDF; сканированные PDF могут дать мало текста. |
| DOC / DOCX | MarkItDown | Извлекает текст и структуру документа. |
| PPT / PPTX | MarkItDown | Извлекает содержимое слайдов, где поддерживается. |
| XLS / XLSX | MarkItDown | Извлекает таблицы/содержимое workbook. |
| HTML / HTM / EPUB | MarkItDown | Конвертирует структурированный контент в Markdown. |
| CSV / JSON / XML / YAML | MarkItDown | Полезно для данных и конфигов. |
| ZIP | MarkItDown | Зависит от содержимого архива и поддержки MarkItDown. |
| PNG / JPG / WEBP / TIFF / BMP | Tesseract OCR | По умолчанию `rus+eng`; orientation detection может авто-развернуть изображение, если установлен Pillow. |

## Установка

### 1. Установить плагин

```bash
hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable
```

### 2. Установить Python-зависимости

Устанавливайте в то же Python-окружение, где работает Hermes:

```bash
python -m pip install "markitdown[pdf,docx,pptx,xlsx,xls]>=0.1.6" "Pillow>=10.0.0"
```

Если в окружении Hermes нет `pip`, используйте `uv` с Python executable Hermes:

```bash
cd ~/.hermes/plugins/document_extract
uv pip install --python "<path-to-hermes-python>" -r requirements.txt
```

### 3. Опционально: установить Tesseract для OCR изображений

Tesseract нужен только для OCR изображений.

| OS | Команда |
|---|---|
| Windows | `winget install --id tesseract-ocr.tesseract --accept-source-agreements --accept-package-agreements` |
| macOS | `brew install tesseract tesseract-lang` |
| Ubuntu / Debian | `sudo apt-get update && sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus` |

Проверка:

```bash
tesseract --version
tesseract --list-langs
```

Для русского + английского OCR в списке должны быть `eng` и `rus`.

### 4. Перезапустить Hermes

CLI:

```text
/reset
```

Gateway:

```bash
hermes gateway restart
```

## Примеры

### Кратко пересказать PDF

Промпт пользователя:

```text
Summarize C:/Users/me/Documents/report.pdf in 5 bullets.
```

Ожидаемый flow агента:

```text
document_extract(path="C:/Users/me/Documents/report.pdf")
read_file(markdown_path)
```

### Распознать текст на скриншоте

```text
Read the text from C:/Users/me/Desktop/screenshot.png.
```

Плагин использует Tesseract OCR. При `orientation="auto"` он может определить повёрнутый текст и автоматически развернуть изображение, если установлен Pillow.

### Обработать папку

```text
Extract all supported files in C:/Users/me/Documents/inbox and give me a short inventory.
```

Ожидаемый flow агента:

```text
document_extract_batch(path="C:/Users/me/Documents/inbox", recursive=false)
read_file(manifest_path)
```

### Приватный документ

```text
This contract is private. Extract only what you need and don't preview the text.
```

Ожидаемые настройки tool:

```text
document_extract(path="...", sensitive=true, preview_chars=0)
```

Sensitive mode использует redacted source metadata, hash-only имена файлов, отключённый preview по умолчанию и более короткий TTL.

### Проверить установку

```text
Check whether document extraction and OCR are ready.
```

Ожидаемый flow агента:

```text
document_extract_status()
```

### Очистить cache extracted text

```text
Clean the document extraction cache.
```

Ожидаемый flow агента:

```text
document_extract_cleanup(expired_only=true)
```

## Cache и приватность

Extracted Markdown хранится тут:

```text
~/.hermes/cache/document-extract/
```

| Режим | Preview по умолчанию | Имя output-файла | Source path в metadata | TTL по умолчанию |
|---|---:|---|---|---:|
| Normal | 500 символов | safe source stem + hash | виден | 7 дней |
| Sensitive | 0 символов | только hash | скрыт | 1 день |
| Cache disabled | настраивается | временный cached output | зависит от режима | 1 час |

Для ручной очистки используйте `document_extract_cleanup`. Истёкшие файлы также чистятся автоматически при запуске extraction.

## Ограничения

- Для OCR нужен системный Tesseract; одних Python-зависимостей недостаточно.
- Качество OCR зависит от установленных language data и качества изображения.
- MarkItDown — практичный Markdown extractor, но не идеальный layout-preserving converter.
- Сканированные PDF могут дать мало текста, потому что OCR сейчас image-based; для OCR-heavy документов используйте скриншоты/изображения страниц.
- Плагин не отправляет файлы во внешние API, но extracted Markdown хранится локально до очистки по TTL.

## Разработка

Локальная установка плагина:

```bash
cp -r . ~/.hermes/plugins/document_extract
hermes plugins enable document_extract
```

Базовые проверки:

```bash
python -m py_compile tools.py schemas.py __init__.py
python -m pytest tests -q
```

## Лицензия

Плагин распространяется под [MIT License](LICENSE).

Сторонние tools/libraries:

- MarkItDown — MIT
- Tesseract OCR — Apache-2.0
- Pillow — HPND-style open source license

См. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Credits

Идея: tak-to-norm  
Реализация: AI-assisted development with Hermes Agent  
Maintainer: tak-to-norm
