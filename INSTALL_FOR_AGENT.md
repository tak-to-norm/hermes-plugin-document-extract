# Agent handoff

This file is kept for compatibility with older local copies. New users should read [INSTALL.md](INSTALL.md).

Important constraints:

- Do not edit Hermes core files.
- Do not install this as a normal Hermes skill.
- Install it as a Hermes plugin.
- The plugin registers tools under the existing `file` toolset.

Recommended install:

```bash
hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable
python -m pip install -r requirements.txt
```

For OCR, install Tesseract separately for your operating system.
