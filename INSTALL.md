# Install

## Recommended setup

```bash
hermes plugins install tak-to-norm/hermes-plugin-document-extract --enable
cd ~/.hermes/plugins/document_extract
bash scripts/setup.sh
```

The setup script asks for one of two modes:

```text
1) Basic — documents only, no OCR
2) Full  — documents + image OCR with Tesseract
```

Non-interactive mode:

```bash
bash scripts/setup.sh --basic -y
bash scripts/setup.sh --full -y
```

Then restart the current Hermes session:

```text
/reset
```

For gateway users:

```bash
hermes gateway restart
```

## Agent-assisted install

You can also give this repo URL to Hermes Agent and ask:

```text
Install this Hermes plugin in Full mode and verify it works:
https://github.com/tak-to-norm/hermes-plugin-document-extract
```

The agent should install the plugin, run the setup script, verify `document_extract_status`, and then ask for `/reset` or gateway restart.

## Troubleshooting

```bash
bash scripts/setup.sh --help
```

If Tesseract is already installed but system package installation is blocked:

```bash
bash scripts/setup.sh --full --skip-system-install
```
