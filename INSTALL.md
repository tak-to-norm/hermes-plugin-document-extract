# Install

## From GitHub

```bash
hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable
python -m pip install "markitdown[pdf,docx,pptx,xlsx,xls]>=0.1.6" "Pillow>=10.0.0"
```

Install Tesseract for image OCR:

- Windows: `winget install --id tesseract-ocr.tesseract --accept-source-agreements --accept-package-agreements`
- macOS: `brew install tesseract tesseract-lang`
- Ubuntu/Debian: `sudo apt-get install tesseract-ocr tesseract-ocr-eng tesseract-ocr-rus`

Restart Hermes:

```text
/reset
```

## Local development install

Copy or symlink this folder to:

```text
~/.hermes/plugins/document_extract/
```

Enable:

```bash
hermes plugins enable document_extract
```

Check:

```bash
hermes plugins list
```

Ask Hermes:

```text
Check document_extract status.
```
