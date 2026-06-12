from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import schemas  # noqa: E402
import tools  # noqa: E402


def test_schemas_have_expected_tools():
    names = {
        schemas.DOCUMENT_EXTRACT_SCHEMA["name"],
        schemas.DOCUMENT_EXTRACT_BATCH_SCHEMA["name"],
        schemas.DOCUMENT_EXTRACT_STATUS_SCHEMA["name"],
        schemas.DOCUMENT_EXTRACT_CLEANUP_SCHEMA["name"],
    }
    assert names == {
        "document_extract",
        "document_extract_batch",
        "document_extract_status",
        "document_extract_cleanup",
    }


def test_text_extract_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    src = tmp_path / "note.txt"
    src.write_text("Hello Hermes document extract", encoding="utf-8")

    payload = json.loads(tools.handle_document_extract({"path": str(src), "preview_chars": 0}))
    assert payload["success"] is True
    assert payload["method"] == "text-copy"
    md_path = Path(payload["markdown_path"])
    assert md_path.exists()
    assert "Hello Hermes document extract" in md_path.read_text(encoding="utf-8")


def test_sensitive_redacts_source(tmp_path, monkeypatch):
    monkeypatch.setenv("HERMES_HOME", str(tmp_path / "hermes-home"))
    src = tmp_path / "private.txt"
    src.write_text("secret-ish text", encoding="utf-8")

    payload = json.loads(tools.handle_document_extract({"path": str(src), "sensitive": True}))
    assert payload["success"] is True
    assert payload["source"] == "[redacted]"
    assert payload["preview"] == ""
    assert "private" not in Path(payload["markdown_path"]).name
