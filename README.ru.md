<p align="center">
  <img src="assets/logo.png" alt="Hermes Document Extract Plugin logo" width="160" />
</p>

<h1 align="center">Hermes Document Extract Plugin</h1>

<p align="center">
  Локальное извлечение документов и изображений для Hermes Agent: файлы → cached Markdown → текст для агента.
</p>

<p align="center">
  <a href="LICENSE"><img alt="License: MIT" src="https://img.shields.io/badge/License-MIT-blue.svg"></a>
  <a href="README.md">English README</a>
</p>

Лёгкий плагин для **Hermes Agent**, который конвертирует локальные документы и изображения в cached Markdown перед тем, как агент их читает.

Плагин добавляет native tools для PDF, Office-файлов, HTML/EPUB/таблиц, архивов и OCR текста с изображений — без прямого чтения бинарных файлов моделью.

> Сделано под native plugin system [Hermes Agent](https://github.com/NousResearch/hermes-agent). Community plugin; это не официальный плагин Nous Research / Hermes Agent.

## Интеграция с Hermes Agent

Hermes Agent — open-source AI agent framework с инструментами. Этот плагин добавляет document extraction как native Hermes tools, чтобы агент мог сам вызывать их, когда пользователь просит посмотреть локальный PDF, Office-документ, таблицу, презентацию, архив или изображение.

Плагин устанавливается через `hermes plugins install`, регистрируется в существующий toolset `file` и начинает работать в CLI/gateway после restart/reset.

## Зачем

Агенту лучше читать текст, а не бинарные файлы. Плагин даёт Hermes безопасный поток:

```text
локальный документ/изображение → document_extract → cached Markdown → read_file чанками → ответ
```

Так меньше расходуется контекст, extraction можно повторно использовать, и весь документ не попадает в разговор сразу.

## Инструменты

| Tool | Что делает |
|---|---|
| `document_extract` | Извлекает один локальный файл в cached Markdown и возвращает `markdown_path`. |
| `document_extract_batch` | Обрабатывает папку или список файлов и возвращает manifest. |
| `document_extract_status` | Проверяет MarkItDown, Tesseract, OCR-языки, Pillow и состояние cache. |
| `document_extract_cleanup` | Чистит expired или весь cache extracted Markdown. |

Все tools регистрируются в существующий Hermes toolset `file`. Отдельный видимый toolset не создаётся.

## Поддерживаемые форматы

### Документы через MarkItDown

- PDF
- DOC / DOCX
- PPT / PPTX
- XLS / XLSX
- HTML / HTM
- EPUB
- CSV / JSON / XML / YAML
- ZIP и другие форматы, поддерживаемые MarkItDown

### Изображения через Tesseract OCR

- PNG
- JPG / JPEG
- WEBP
- TIFF / TIF
- BMP

Для изображений плагин может использовать Tesseract OSD — определение ориентации и скрипта. Если текст повёрнут и доступен Pillow, изображение будет автоматически развёрнуто перед OCR.

## Возможности

- Локальная обработка, без API-ключей.
- Cached Markdown в `~/.hermes/cache/document-extract/`.
- Повторное использование extraction по SHA-256 файла.
- Автоочистка по TTL.
- Ручная очистка cache.
- Privacy mode `sensitive`: без preview по умолчанию, hash-only имена, redacted source path, короткий TTL.
- Batch extraction для папок и списков файлов.
- Status tool, чтобы агент сам видел недостающие зависимости/OCR-языки.

## Установка

Установить плагин с GitHub:

```bash
hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable
```

Установить Python-зависимости в то же окружение Python, где работает Hermes:

```bash
python -m pip install "markitdown[pdf,docx,pptx,xlsx,xls]>=0.1.6" "Pillow>=10.0.0"
```

Для OCR изображений отдельно нужен Tesseract.

### Установка Tesseract

Windows:

```bash
winget install --id tesseract-ocr.tesseract --accept-source-agreements --accept-package-agreements
```

macOS:

```bash
brew install tesseract tesseract-lang
```

Ubuntu / Debian:

```bash
sudo apt-get update
sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus
```

Проверка OCR-языков:

```bash
tesseract --version
tesseract --list-langs
```

После установки перезапустить Hermes:

```text
/reset
```

Для gateway:

```bash
hermes gateway restart
```

## Ручная локальная установка

Скопируйте папку плагина сюда:

```text
~/.hermes/plugins/document_extract/
```

Затем включите:

```bash
hermes plugins enable document_extract
```

## Примеры

Попросить Hermes:

```text
Кратко перескажи PDF: C:/Users/me/Documents/report.pdf
```

Ожидаемый поток:

1. Hermes вызывает `document_extract`.
2. Плагин извлекает файл в Markdown в Hermes cache.
3. Hermes читает `markdown_path` через `read_file`.
4. Hermes отвечает по extracted text.

OCR пример:

```text
Распознай текст на скриншоте: C:/Users/me/Desktop/screenshot.png
```

Batch пример:

```text
Обработай все документы в C:/Users/me/Documents/inbox и дай краткий список.
```

Privacy пример:

```text
Это приватный документ. Извлеки только нужное и не показывай preview текста.
```

В таком случае Hermes может вызвать `document_extract(..., sensitive=true)`.

## Cache

Extracted Markdown хранится тут:

```text
~/.hermes/cache/document-extract/
```

TTL по умолчанию:

| Режим | TTL |
|---|---:|
| Обычный | 7 дней |
| Sensitive | 1 день |
| Cache disabled | 1 час |

Для ручной очистки используется `document_extract_cleanup`.

## Плюсы и минусы

| Плюсы | Минусы |
|---|---|
| Локальная обработка документов | Для OCR нужно отдельно установить Tesseract |
| Не нужен API-ключ | Качество OCR зависит от установленных языков |
| Экономит контекст: возвращает путь, а не весь текст | MarkItDown не всегда идеально сохраняет сложный layout |
| Много поддерживаемых форматов | Сканированные PDF могут требовать OCR страниц/скриншотов |
| Чисто встраивается в Hermes `file` toolset | После установки нужен restart/reset |

## Лицензия

Плагин распространяется под MIT License.

Сторонние зависимости:

- MarkItDown — MIT
- Tesseract OCR — Apache-2.0
- Pillow — HPND-style open source license

См. [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Credits

Идея: tak-to-norm  
Реализация: AI-assisted development with Hermes Agent  
Maintainer: tak-to-norm
