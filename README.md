# Hermes Document Extract Plugin

[English](README.md) | [Русский](README.ru.md)

A lightweight **Hermes Agent** plugin that converts local documents and images into cached Markdown before the agent reads them.

It adds native Hermes tools for extracting PDFs, Office files, HTML/EPUB/table files, archives, and OCR text from images without loading binary files directly into the model context.

> Not an official Nous Research / Hermes Agent plugin.

## Why

Agents are good at reading text, not binary files. This plugin gives Hermes a safer flow:

```text
local document/image → document_extract → cached Markdown → read_file chunks → answer
```

That keeps context smaller, makes extraction repeatable, and avoids dumping whole documents into the conversation when only parts are needed.

## Tools provided

| Tool | What it does |
|---|---|
| `document_extract` | Extract one local file into cached Markdown and return `markdown_path`. |
| `document_extract_batch` | Extract a folder or list of files and return a manifest. |
| `document_extract_status` | Check MarkItDown, Tesseract, OCR languages, Pillow, and cache status. |
| `document_extract_cleanup` | Clean expired or all extracted Markdown cache files. |

All tools register under Hermes' existing `file` toolset. No separate visible toolset is created.

## Supported inputs

### Documents via MarkItDown

- PDF
- DOC / DOCX
- PPT / PPTX
- XLS / XLSX
- HTML / HTM
- EPUB
- CSV / JSON / XML / YAML
- ZIP and other MarkItDown-supported formats

### Images via Tesseract OCR

- PNG
- JPG / JPEG
- WEBP
- TIFF / TIF
- BMP

For images, the plugin can use Tesseract OSD (orientation and script detection) to detect rotated text and auto-rotate when Pillow is available.

## Features

- Local-first extraction; no API key required.
- Cached Markdown output in `~/.hermes/cache/document-extract/`.
- SHA-256 based cache reuse when the same file is processed again.
- TTL-based automatic cleanup.
- Manual cache cleanup tool.
- Privacy-oriented `sensitive` mode: no preview by default, hash-only output names, redacted source path metadata, shorter default TTL.
- Batch extraction for folders or explicit file lists.
- Dependency/status tool so the agent can self-diagnose missing OCR or languages.

## Installation

Install the plugin from GitHub:

```bash
hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable
```

Install Python dependencies in the same Python environment that runs Hermes:

```bash
python -m pip install "markitdown[pdf,docx,pptx,xlsx,xls]>=0.1.6" "Pillow>=10.0.0"
```

For image OCR, install Tesseract separately.

### Tesseract install examples

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

Verify OCR languages:

```bash
tesseract --version
tesseract --list-langs
```

Restart Hermes after installation:

```text
/reset
```

For Hermes gateway:

```bash
hermes gateway restart
```

## Manual local install

Copy this folder to:

```text
~/.hermes/plugins/document_extract/
```

Then enable:

```bash
hermes plugins enable document_extract
```

## Usage examples

Ask Hermes:

```text
Summarize this PDF: C:/Users/me/Documents/report.pdf
```

Expected flow:

1. Hermes calls `document_extract`.
2. The plugin extracts the file to Markdown in Hermes cache.
3. Hermes reads the returned `markdown_path` with `read_file`.
4. Hermes answers from the extracted text.

OCR example:

```text
Read the text from this screenshot: C:/Users/me/Desktop/screenshot.png
```

Batch example:

```text
Extract all documents in C:/Users/me/Documents/inbox and give me a short inventory.
```

Privacy example:

```text
This is a private document. Extract only what you need and do not preview the text.
```

Hermes can call `document_extract(..., sensitive=true)` for this case.

## Cache behavior

Extracted Markdown is stored under:

```text
~/.hermes/cache/document-extract/
```

Default TTL:

| Mode | Default TTL |
|---|---:|
| Normal | 7 days |
| Sensitive | 1 day |
| Cache disabled | 1 hour |

Use `document_extract_cleanup` to clean the cache manually.

## Pros and cons

| Pros | Cons |
|---|---|
| Local document processing | OCR requires system Tesseract installation |
| No API key required | OCR quality depends on installed language data |
| Saves context by returning paths, not whole documents | MarkItDown may not perfectly preserve every complex layout |
| Works with many common file types | Scanned PDFs may need page images/screenshots for OCR |
| Integrates cleanly with Hermes `file` toolset | Requires restart/reset after install |

## License

This plugin is released under the MIT License.

Third-party dependencies:

- MarkItDown — MIT
- Tesseract OCR — Apache-2.0
- Pillow — HPND-style open source license

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Credits

Idea: tak-to-norm  
Implementation: AI-assisted development with Hermes Agent  
Maintainer: tak-to-norm
