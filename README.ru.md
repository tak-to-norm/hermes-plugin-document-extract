<p align="center">
  <img src="assets/logo.png" alt="Логотип Hermes Document Extract Plugin" width="160" />
</p>

<h1 align="center">Hermes Document Extract Plugin</h1>

<p align="center">
  Локальное извлечение документов и изображений для Hermes Agent: файлы → кэшированный Markdown → текст для агента.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
  <a href="README.md">English README</a>
</p>

> Сделано под native plugin system [Hermes Agent](https://github.com/NousResearch/hermes-agent). Это community plugin, а не официальный плагин Nous Research / Hermes Agent.

## Интеграция с Hermes Agent

Hermes Agent — open-source framework для AI-агентов с инструментами. Этот плагин добавляет извлечение документов как native Hermes tools, чтобы агент мог сам вызывать их, когда пользователь просит посмотреть локальный PDF, Office-документ, таблицу, презентацию, архив или изображение.

Плагин устанавливается через `hermes plugins install`, регистрируется в существующий toolset `file` и работает в обычных CLI/gateway-сессиях Hermes после `/reset` или перезапуска.

## Что делает плагин

`hermes-plugin-document-extract` добавляет Hermes tools, которые конвертируют локальные документы и изображения в Markdown перед тем, как агент их читает.

```text
PDF / DOCX / изображение          папка / список файлов
        ↓                                ↓
document_extract                 document_extract_batch
        ↓                                ↓
~/.hermes/cache/document-extract/*.md / manifest
        ↓
Hermes читает Markdown через read_file
```

Это уменьшает расход контекста, не заставляет агента читать бинарные файлы напрямую и ускоряет повторную обработку за счёт повторного использования кэша.

## Зачем нужен этот плагин

AI-агенты всё чаще работают с локальными знаниями: PDF, сканами, скриншотами, презентациями, таблицами и заметками. Проблема в том, что такие файлы обычно бинарные, тяжёлые и дорогие для прямого чтения в контексте модели.

`hermes-plugin-document-extract` даёт Hermes Agent простой local-first путь:

- превращать документы и изображения в кэшированный Markdown;
- возвращать `markdown_path`, а не весь текст документа в диалог;
- читать только те разделы, которые реально нужны агенту;
- переиспользовать результаты извлечения при повторных запросах;
- держать OCR и обработку документов локально по умолчанию.

Это особенно полезно для `llm-wiki`, research-папок, личных архивов и любых workflow, где важны расход контекста и приватность.

## Сценарий для llm-wiki

Идея плагина выросла из практической задачи `llm-wiki`: пользователи часто собирают PDF, сканы, скриншоты, презентации и офисные документы, но агенту не стоит загружать исходные файлы напрямую в контекст модели.

`hermes-plugin-document-extract` сначала превращает такие файлы в кэшированный Markdown. После этого Hermes может искать и читать только нужные фрагменты Markdown при создании или использовании `llm-wiki`.

Пример flow:

1. Сложить исходные файлы в inbox-папку `llm-wiki`.
2. Запустить `document_extract_batch` по этой папке.
3. Использовать возвращённые `markdown_path` как чистые Markdown-входы.
4. Читать только нужные sections, а не тратить контекст на документы целиком.

## Инструменты

| Tool | Когда использовать | Что возвращает |
|---|---|---|
| `document_extract` | Один файл: PDF, DOCX, XLSX, PPTX, изображение и т.д. | `markdown_path`, metadata, warnings |
| `document_extract_batch` | Папка или список файлов | `manifest_path` + результаты по каждому файлу |
| `document_extract_status` | Диагностика установки | Статус MarkItDown/Tesseract/Pillow/кэша |
| `document_extract_cleanup` | Очистка извлечённого текста | Количество/размер удалённых файлов, dry-run |

Все инструменты доступны через существующий Hermes toolset `file`. Отдельный видимый toolset или skill не устанавливается.

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
| PNG / JPG / WEBP / TIFF / BMP | Tesseract OCR | По умолчанию `rus+eng`; orientation detection может автоматически развернуть изображение, если установлен Pillow. |

## Установка

### Рекомендуемый вариант: setup-скрипт

```bash
hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable
cd ~/.hermes/plugins/document_extract
bash scripts/setup.sh
```

Скрипт спросит, какой режим установить:

```text
1) Basic — только документы: PDF/DOCX/XLSX/PPTX/HTML/TXT через MarkItDown
2) Full  — Basic + OCR изображений/скриншотов через Tesseract (eng/rus/osd)
```

Он определяет Windows/macOS/Linux, находит Python-окружение Hermes, ставит Python-зависимости именно туда, проверяет MarkItDown/Pillow, а в Full-режиме проверяет или устанавливает Tesseract и готовит языковые данные OCR в `~/.hermes/tessdata`.

Non-interactive режим:

```bash
bash scripts/setup.sh --basic -y
bash scripts/setup.sh --full -y
```

Full-режим может запросить права package manager/admin, если Tesseract ещё не установлен.

### Самый простой вариант: попросить агента

Можно просто отправить ссылку на этот репозиторий Hermes Agent и попросить установить плагин:

```text
Install this Hermes plugin in Full mode and verify it works:
https://github.com/tak-to-norm/hermes-plugin-document-extract
```

Агент должен установить плагин, запустить `bash scripts/setup.sh --full`, проверить `document_extract_status`, а затем попросить сделать `/reset` или перезапустить gateway.

### Перезапуск Hermes

CLI:

```text
/reset
```

Gateway:

```bash
hermes gateway restart
```

### Ручная установка

Ручная установка — не основной путь. Если setup-скрипт не сработал, запустите его с явным режимом и посмотрите, какую именно недостающую зависимость он назвал:

```bash
bash scripts/setup.sh --basic
bash scripts/setup.sh --full
bash scripts/setup.sh --help
```

Если Tesseract уже установлен, но установка через package manager заблокирована, используйте:

```bash
bash scripts/setup.sh --full --skip-system-install
```

## Примеры

### Кратко пересказать PDF

Промпт пользователя:

```text
Summarize C:/Users/me/Documents/report.pdf in 5 bullets.
```

Ожидаемый ход действий агента:

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

Ожидаемый ход действий агента:

```text
document_extract_batch(path="C:/Users/me/Documents/inbox", recursive=false)
read_file(manifest_path)
```

### Приватный документ

```text
This contract is private. Extract only what you need and don't preview the text.
```

Ожидаемые параметры tool:

```text
document_extract(path="...", sensitive=true, preview_chars=0)
```

Sensitive mode скрывает source metadata, использует hash-only имена файлов, отключает preview по умолчанию и ставит более короткий TTL.

### Проверить установку

```text
Check whether document extraction and OCR are ready.
```

Ожидаемый ход действий агента:

```text
document_extract_status()
```

### Очистить кэш извлечённого текста

```text
Clean the document extraction cache.
```

Ожидаемый ход действий агента:

```text
document_extract_cleanup(expired_only=true)
```

## Кэш и приватность

Извлечённый Markdown хранится тут:

```text
~/.hermes/cache/document-extract/
```

| Режим | Preview по умолчанию | Имя output-файла | Source path в metadata | TTL по умолчанию |
|---|---:|---|---|---:|
| Обычный | 500 символов | safe source stem + hash | виден | 7 дней |
| Sensitive | 0 символов | только hash | скрыт | 1 день |
| Cache disabled | настраивается | временный cached output | зависит от режима | 1 час |

Для ручной очистки используйте `document_extract_cleanup`. Истёкшие файлы также чистятся автоматически при запуске extraction.

## Ограничения

- Для OCR нужен системный Tesseract; одних Python-зависимостей недостаточно.
- Качество OCR зависит от установленных языковых данных и качества изображения.
- MarkItDown — практичный Markdown extractor, но не идеальный layout-preserving converter.
- Сканированные PDF могут дать мало текста, потому что OCR сейчас image-based; для OCR-heavy документов используйте скриншоты/изображения страниц.
- Плагин не отправляет файлы во внешние API, но извлечённый Markdown хранится локально до очистки по TTL.

## Разработка

Обычным пользователям лучше ставить плагин из GitHub через `hermes plugins install`. Для локальной разработки клонируйте репозиторий и запускайте проверки из корня репозитория.

Если нужен `pytest`, установите dev-зависимости:

```bash
python -m pip install -r requirements-dev.txt
```

Базовые проверки:

```bash
python -m py_compile tools.py schemas.py __init__.py
python -m pytest tests -q
```

Не копируйте весь рабочий каталог в `~/.hermes/plugins/` для разработки: так можно случайно перенести `.git`, кэши, логи или локальные файлы. Для обычного использования ставьте через `hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable`.

## Лицензия

Плагин распространяется под [MIT License](LICENSE).

Сторонние инструменты/библиотеки:

- MarkItDown — MIT
- Tesseract OCR — Apache-2.0
- Языковые данные Tesseract — Apache-2.0
- Pillow — HPND-style open source license

См. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Благодарности

Идея: tak-to-norm  
Реализация: AI-assisted development with Hermes Agent  
Сопровождение: tak-to-norm
