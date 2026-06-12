# Third-party notices

This plugin can use the following third-party tools and libraries.

## MarkItDown

- Project: <https://github.com/microsoft/markitdown>
- License: MIT
- Used for converting local documents and structured files to Markdown.

## Tesseract OCR

- Project: <https://github.com/tesseract-ocr/tesseract>
- License: Apache License 2.0
- Used for OCR on local image files.

## Tesseract language data

- Project: <https://github.com/tesseract-ocr/tessdata_fast>
- License: Apache License 2.0
- Used for optional OCR language data (`eng`, `rus`, `osd`).
- The setup script may download missing language data into the user's local `~/.hermes/tessdata` directory.

## Pillow

- Project: <https://python-pillow.org/>
- License: HPND-style open source license
- Used only to rotate images when Tesseract OSD detects rotated text.

This repository does not vendor MarkItDown, Tesseract binaries, Tesseract language data, or Pillow source code.
Dependencies are installed or downloaded into the user's local environment during setup.
