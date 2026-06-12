# Agent handoff

This file is kept for compatibility with older local copies. New users should read [README.md](README.md) or [INSTALL.md](INSTALL.md).

Important constraints:

- Do not edit Hermes core files.
- Do not install this as a normal Hermes skill.
- Install it as a Hermes plugin.
- The plugin registers tools under the existing `file` toolset.

Recommended install:

```bash
hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable
cd ~/.hermes/plugins/document_extract
bash scripts/setup.sh
```

For Full OCR setup without interaction:

```bash
bash scripts/setup.sh --full -y
```

Verify after restart/reset by calling:

```text
document_extract_status()
```
