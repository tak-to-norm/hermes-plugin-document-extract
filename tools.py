"""Native document extraction tools for Hermes Agent.

The plugin keeps the agent away from binary / non-text files by converting local
files into Markdown first, storing the result in a controlled Hermes cache, and
returning a path that can be read with the normal read_file tool.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any, Iterable

try:
    from tools.registry import tool_error, tool_result
except Exception:  # pragma: no cover - allows standalone smoke checks outside Hermes
    def tool_result(payload: dict) -> str:
        payload.setdefault("success", True)
        return json.dumps(payload, ensure_ascii=False)

    def tool_error(message: str, **extra: Any) -> str:
        payload = {"success": False, "error": message}
        payload.update(extra)
        return json.dumps(payload, ensure_ascii=False)


PLUGIN_VERSION = "0.1.0"
CACHE_SCHEMA_VERSION = "2"
DEFAULT_TTL_DAYS = 7.0
SENSITIVE_TTL_DAYS = 1.0
DISPOSABLE_TTL_DAYS = 1.0 / 24.0  # one hour

DOC_EXTENSIONS = {
    ".pdf", ".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls",
    ".html", ".htm", ".epub", ".csv", ".json", ".xml", ".yaml", ".yml", ".zip",
}
IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff", ".bmp"}
TEXT_EXTENSIONS = {".md", ".markdown", ".txt", ".text", ".rst", ".log"}
SUPPORTED_EXTENSIONS = DOC_EXTENSIONS | IMAGE_EXTENSIONS | TEXT_EXTENSIONS


class DocumentExtractError(RuntimeError):
    """User-facing extraction failure."""


def _now_utc() -> _dt.datetime:
    return _dt.datetime.now(_dt.timezone.utc).replace(microsecond=0)


def _iso(dt: _dt.datetime | None) -> str | None:
    return dt.isoformat() if dt else None


def _parse_iso(value: str | None) -> _dt.datetime | None:
    if not value:
        return None
    try:
        parsed = _dt.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=_dt.timezone.utc)
        return parsed
    except Exception:
        return None


def _normalize_path(raw: str) -> Path:
    """Normalize Windows/MSYS-ish paths without resolving nonexistent paths."""
    value = str(raw or "").strip().strip('"').strip("'")
    if not value:
        raise ValueError("path is required")

    # Git Bash / MSYS path: /c/Users/name/file.pdf -> C:/Users/name/file.pdf
    m = re.match(r"^/([a-zA-Z])/(.*)$", value)
    if m:
        value = f"{m.group(1).upper()}:/{m.group(2)}"

    value = os.path.expandvars(os.path.expanduser(value))
    return Path(value)


def _get_hermes_home() -> Path:
    """Return active Hermes home when available, otherwise ~/.hermes."""
    try:
        from hermes_constants import get_hermes_home  # type: ignore
        return Path(get_hermes_home()).expanduser()
    except Exception:
        env_home = os.getenv("HERMES_HOME")
        if env_home:
            return Path(env_home).expanduser()
        return Path.home() / ".hermes"


def _cache_root() -> Path:
    root = _get_hermes_home() / "cache" / "document-extract"
    root.mkdir(parents=True, exist_ok=True)
    (root / "extracted").mkdir(parents=True, exist_ok=True)
    (root / "manifests").mkdir(parents=True, exist_ok=True)
    return root


def _slugify_filename(value: str, fallback: str = "document", max_len: int = 80) -> str:
    stem = Path(value).stem or fallback
    stem = stem.encode("ascii", errors="ignore").decode("ascii")
    stem = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip(".-_")
    if not stem:
        stem = fallback
    return stem[:max_len]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _markitdown_available() -> bool:
    return importlib.util.find_spec("markitdown") is not None


def _markitdown_version() -> str | None:
    try:
        return importlib.metadata.version("markitdown")
    except Exception:
        return None


def _pillow_available() -> bool:
    return importlib.util.find_spec("PIL") is not None


def _tesseract_path() -> str | None:
    """Find Tesseract even when the current process PATH is stale after install."""
    found = shutil.which("tesseract")
    if found:
        return found

    env_cmd = os.getenv("TESSERACT_CMD")
    candidates = [
        Path(env_cmd) if env_cmd else None,
        Path("C:/Program Files/Tesseract-OCR/tesseract.exe"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tesseract.exe"),
    ]
    for candidate in candidates:
        if candidate and candidate.exists():
            return str(candidate)
    return None


def _candidate_tessdata_dirs() -> list[Path]:
    """Known places where Tesseract language data may live."""
    candidates: list[Path] = []
    env_prefix = os.getenv("TESSDATA_PREFIX")
    if env_prefix:
        prefix = Path(env_prefix).expanduser()
        candidates.extend([prefix, prefix / "tessdata"])

    hermes_home = _get_hermes_home()
    candidates.extend([
        hermes_home / "tessdata",
        Path.home() / ".hermes" / "tessdata",
        Path("C:/Program Files/Tesseract-OCR/tessdata"),
        Path("C:/Program Files (x86)/Tesseract-OCR/tessdata"),
    ])

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve(strict=False)).lower()
        if key not in seen and candidate.exists():
            unique.append(candidate)
            seen.add(key)
    return unique


def _resolve_tessdata_dir(languages: str, *, need_osd: bool = False, explicit: str | None = None) -> Path | None:
    """Pick a tessdata dir that contains all requested language files when possible."""
    if explicit:
        return _normalize_path(explicit)
    requested = {part.strip() for part in (languages or "").split("+") if part.strip()}
    if need_osd:
        requested.add("osd")
    if not requested:
        return None
    for directory in _candidate_tessdata_dirs():
        if all((directory / f"{lang}.traineddata").exists() for lang in requested):
            return directory
    return None


def _tesseract_available() -> bool:
    return _tesseract_path() is not None


def _run_command(cmd: list[str], *, timeout: int = 180) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        timeout=timeout,
    )


def _tesseract_version() -> str | None:
    path = _tesseract_path()
    if not path:
        return None
    try:
        proc = _run_command([path, "--version"], timeout=20)
        return (proc.stdout or proc.stderr or "").splitlines()[0].strip() or None
    except Exception:
        return None


def _parse_tesseract_langs(text: str) -> list[str]:
    langs: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.lower().startswith("list of available languages"):
            continue
        if re.match(r"^[A-Za-z0-9_+-]+$", line):
            langs.append(line)
    return langs


def _tesseract_languages(tessdata_dir: str | Path | None = None) -> list[str]:
    path = _tesseract_path()
    if not path:
        return []
    dirs: list[Path | None]
    if tessdata_dir:
        dirs = [_normalize_path(str(tessdata_dir))]
    else:
        dirs = [None] + _candidate_tessdata_dirs()

    langs: list[str] = []
    for directory in dirs:
        try:
            cmd = [path, "--list-langs"]
            if directory:
                cmd.extend(["--tessdata-dir", str(directory)])
            proc = _run_command(cmd, timeout=30)
            text = (proc.stdout or "") + "\n" + (proc.stderr or "")
            langs.extend(_parse_tesseract_langs(text))
        except Exception:
            continue
    return sorted(set(langs))


def _read_text_file(src: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return src.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return src.read_text(encoding="utf-8", errors="replace")


def _extract_with_markitdown(src: Path) -> tuple[str, list[str]]:
    warnings: list[str] = []
    if not _markitdown_available():
        raise DocumentExtractError(
            "MarkItDown is not installed. Install with: "
            "python -m pip install -r requirements.txt"
        )

    from markitdown import MarkItDown  # lazy dependency

    result = MarkItDown(enable_plugins=False).convert(str(src))
    text = getattr(result, "text_content", None) or getattr(result, "markdown", None)
    if text is None:
        text = str(result)
    text = text or ""

    if len(text.strip()) < 200 and src.suffix.lower() == ".pdf":
        warnings.append(
            "MarkItDown returned very little text for this PDF. It may be scanned; "
            "try OCR on page images or screenshots."
        )
    if not text.strip():
        warnings.append("Extraction returned empty text.")
    return text, warnings


def _detect_orientation(src: Path, tessdata_dir: str | Path | None = None) -> tuple[dict[str, Any], list[str]]:
    """Use Tesseract OSD to detect orientation. Non-fatal on failure."""
    warnings: list[str] = []
    tesseract = _tesseract_path()
    if not tesseract:
        return {}, ["Tesseract is not installed; orientation detection skipped."]

    try:
        cmd = [tesseract, str(src), "stdout", "-l", "osd", "--psm", "0"]
        if tessdata_dir:
            cmd.extend(["--tessdata-dir", str(tessdata_dir)])
        proc = _run_command(cmd, timeout=60)
    except Exception as exc:
        return {}, [f"Tesseract OSD failed: {type(exc).__name__}: {exc}"]

    text = ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()
    if proc.returncode != 0:
        msg = text[:500] or f"exit code {proc.returncode}"
        return {}, [f"Tesseract OSD did not return orientation: {msg}"]

    def find_int(label: str) -> int | None:
        m = re.search(rf"{re.escape(label)}\s*:\s*(-?\d+)", text, flags=re.I)
        return int(m.group(1)) if m else None

    orientation_degrees = find_int("Orientation in degrees")
    rotate = find_int("Rotate")
    script_match = re.search(r"Script\s*:\s*([^\n\r]+)", text, flags=re.I)
    script = script_match.group(1).strip() if script_match else None
    confidence_match = re.search(r"Orientation confidence\s*:\s*([0-9.]+)", text, flags=re.I)
    confidence = float(confidence_match.group(1)) if confidence_match else None

    return {
        "orientation_degrees": orientation_degrees,
        "rotate": rotate,
        "script": script,
        "orientation_confidence": confidence,
    }, warnings


def _rotate_image(src: Path, rotate_degrees: int) -> tuple[Path, list[str]]:
    warnings: list[str] = []
    if rotate_degrees % 360 == 0:
        return src, warnings
    if not _pillow_available():
        return src, ["Pillow is not installed; orientation was detected but image was not auto-rotated."]

    from PIL import Image  # lazy dependency

    tmp = tempfile.NamedTemporaryFile(prefix="hermes-ocr-rotated-", suffix=src.suffix or ".png", delete=False)
    tmp_path = Path(tmp.name)
    tmp.close()
    try:
        with Image.open(src) as img:
            # Tesseract's "Rotate" value is the clockwise correction. Pillow's
            # positive rotate is counter-clockwise, so use the negative value.
            rotated = img.rotate(-int(rotate_degrees), expand=True)
            rotated.save(tmp_path)
        return tmp_path, warnings
    except Exception as exc:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return src, [f"Image auto-rotation failed: {type(exc).__name__}: {exc}"]


def _extract_with_tesseract(
    src: Path,
    *,
    languages: str,
    psm: int,
    orientation: str,
    tessdata_dir: str | None,
) -> tuple[str, list[str], dict[str, Any]]:
    warnings: list[str] = []
    orientation_info: dict[str, Any] = {}
    tesseract = _tesseract_path()
    if not tesseract:
        raise DocumentExtractError(
            "Tesseract is not installed or not on PATH. Install it from your OS package manager."
        )

    ocr_src = src
    resolved_tessdata_dir = _resolve_tessdata_dir(languages or "rus+eng", need_osd=(orientation == "auto"), explicit=tessdata_dir)
    rotated_tmp: Path | None = None
    if orientation == "auto":
        orientation_info, osd_warnings = _detect_orientation(src, resolved_tessdata_dir)
        warnings.extend(osd_warnings)
        rotate = int(orientation_info.get("rotate") or 0)
        if rotate % 360:
            ocr_src, rotate_warnings = _rotate_image(src, rotate)
            warnings.extend(rotate_warnings)
            if ocr_src != src:
                rotated_tmp = ocr_src
                orientation_info["auto_rotated"] = True
            else:
                orientation_info["auto_rotated"] = False

    cmd = [tesseract, str(ocr_src), "stdout", "-l", languages or "rus+eng", "--psm", str(int(psm or 11))]
    if resolved_tessdata_dir:
        cmd.extend(["--tessdata-dir", str(resolved_tessdata_dir)])

    try:
        proc = _run_command(cmd, timeout=180)
    finally:
        if rotated_tmp:
            try:
                rotated_tmp.unlink(missing_ok=True)
            except Exception:
                pass

    if proc.returncode != 0:
        stderr = (proc.stderr or "").strip()
        raise DocumentExtractError(f"Tesseract failed with exit code {proc.returncode}: {stderr[:1000]}")

    text = proc.stdout or ""
    stderr = (proc.stderr or "").strip()
    if stderr:
        warnings.append(stderr[:1000])
    if len(text.strip()) < 20:
        warnings.append("OCR returned very little text; the image may contain little readable text or OCR quality is poor.")

    available = set(_tesseract_languages(resolved_tessdata_dir))
    requested = {part.strip() for part in (languages or "").split("+") if part.strip()}
    missing = sorted(requested - available) if available else []
    if missing:
        warnings.append(f"Requested Tesseract language data not found: {', '.join(missing)}")
    if resolved_tessdata_dir:
        orientation_info.setdefault("tessdata_dir", str(resolved_tessdata_dir))

    return text, warnings, orientation_info


def _coerce_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = default
    return max(low, min(high, parsed))


def _coerce_float(value: Any, default: float, low: float, high: float) -> float:
    try:
        parsed = float(value)
    except Exception:
        parsed = default
    return max(low, min(high, parsed))


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}


def _json_value(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False)


def _build_frontmatter(metadata: dict[str, Any]) -> str:
    keys = [
        "document_extract_version", "created_at", "expires_at", "source_name", "source_path",
        "source_extension", "source_sha256", "source_size_bytes", "method", "cache_key",
        "sensitive", "warnings", "orientation",
    ]
    lines = ["---"]
    for key in keys:
        if key in metadata:
            lines.append(f"{key}: {_json_value(metadata[key])}")
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def _wrap_markdown(*, body: str, metadata: dict[str, Any]) -> str:
    source_name = metadata.get("source_name") or "[redacted]"
    warning_block = ""
    warnings = metadata.get("warnings") or []
    if warnings:
        warning_block = "\n\n## Extraction warnings\n\n" + "\n".join(f"- {w}" for w in warnings) + "\n"
    return (
        _build_frontmatter(metadata)
        + f"# Extracted content: {source_name}\n\n"
        + f"- Method: `{metadata.get('method')}`\n"
        + f"- Extracted at: `{metadata.get('created_at')}`\n"
        + warning_block
        + "\n## Content\n\n"
        + f"{body.strip()}\n"
    )


def _cache_key_for(src: Path, *, source_hash: str, args: dict[str, Any], sensitive: bool) -> str:
    parts = {
        "schema": CACHE_SCHEMA_VERSION,
        "source_sha256": source_hash,
        "suffix": src.suffix.lower(),
        "ocr": str(args.get("ocr") or "auto"),
        "languages": str(args.get("languages") or "rus+eng"),
        "psm": args.get("psm", 11),
        "orientation": str(args.get("orientation") or "auto"),
        "sensitive": bool(sensitive),
    }
    raw = json.dumps(parts, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _output_paths(src: Path, *, cache_key: str, sensitive: bool) -> tuple[Path, Path]:
    root = _cache_root() / "extracted" / cache_key[:2]
    root.mkdir(parents=True, exist_ok=True)
    if sensitive:
        name = f"document_{cache_key[:16]}.md"
    else:
        name = f"{_slugify_filename(src.name)}_{cache_key[:16]}.md"
    md_path = root / name
    meta_path = md_path.with_suffix(md_path.suffix + ".json")
    return md_path, meta_path


def _metadata_expired(metadata: dict[str, Any]) -> bool:
    expires_at = _parse_iso(metadata.get("expires_at"))
    return bool(expires_at and expires_at <= _now_utc())


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _preview_from_file(path: Path, chars: int) -> str:
    if chars <= 0:
        return ""
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        return fh.read(chars)


def _payload_from_cache(md_path: Path, meta_path: Path, *, preview_chars: int) -> dict[str, Any] | None:
    metadata = _load_json(meta_path)
    if not metadata or _metadata_expired(metadata) or not md_path.exists():
        return None
    return {
        "success": True,
        "cache_hit": True,
        "source": metadata.get("source_path", "[redacted]"),
        "source_extension": metadata.get("source_extension"),
        "method": metadata.get("method"),
        "markdown_path": str(md_path),
        "metadata_path": str(meta_path),
        "chars": int(metadata.get("markdown_chars") or md_path.stat().st_size),
        "text_chars": int(metadata.get("text_chars") or 0),
        "size_mb": round(float(metadata.get("source_size_bytes") or 0) / 1024 / 1024, 3),
        "warnings": metadata.get("warnings", []),
        "preview": _preview_from_file(md_path, preview_chars),
        "expires_at": metadata.get("expires_at"),
        "next_step": "Read markdown_path with read_file in chunks; do not read the original non-Markdown file directly.",
        "dependencies": _dependency_status(),
    }


def _extract_one(args: dict[str, Any], *, run_cleanup: bool = True) -> dict[str, Any]:
    try:
        src = _normalize_path(args.get("path", ""))
    except Exception as exc:
        raise DocumentExtractError(str(exc)) from exc

    if not src.exists():
        raise DocumentExtractError(f"File not found: {src}")
    if not src.is_file():
        raise DocumentExtractError(f"Path is not a file: {src}")

    cache_root = _cache_root()
    if run_cleanup:
        _cleanup_cache(cache_root, expired_only=True, dry_run=False)

    max_file_mb = _coerce_float(args.get("max_file_mb"), 100.0, 0.1, 5000.0)
    size_bytes = src.stat().st_size
    if size_bytes > max_file_mb * 1024 * 1024:
        raise DocumentExtractError(f"File is too large: {size_bytes / 1024 / 1024:.1f} MB > {max_file_mb:.1f} MB")

    suffix = src.suffix.lower()
    sensitive = _coerce_bool(args.get("sensitive"), False)
    cache_enabled = _coerce_bool(args.get("cache"), True)
    ocr = str(args.get("ocr") or "auto").lower().strip()
    languages = str(args.get("languages") or "rus+eng").strip() or "rus+eng"
    psm = _coerce_int(args.get("psm"), 11, 0, 13)
    orientation = str(args.get("orientation") or "auto").lower().strip()
    if orientation not in {"auto", "off"}:
        orientation = "auto"
    preview_default = 0 if sensitive else 500
    preview_chars = _coerce_int(args.get("preview_chars"), preview_default, 0, 20000)
    tessdata_dir = args.get("tessdata_dir") or None

    ttl_arg = args.get("ttl_days")
    if ttl_arg is None:
        ttl_days = SENSITIVE_TTL_DAYS if sensitive else (DEFAULT_TTL_DAYS if cache_enabled else DISPOSABLE_TTL_DAYS)
    else:
        ttl_days = _coerce_float(ttl_arg, DEFAULT_TTL_DAYS, 0.0, 3650.0)
    now = _now_utc()
    expires_at = None if ttl_days <= 0 else now + _dt.timedelta(days=ttl_days)

    source_hash = _sha256_file(src)
    cache_key = _cache_key_for(src, source_hash=source_hash, args=args, sensitive=sensitive)
    md_path, meta_path = _output_paths(src, cache_key=cache_key, sensitive=sensitive)

    if cache_enabled:
        cached = _payload_from_cache(md_path, meta_path, preview_chars=preview_chars)
        if cached:
            return cached

    method = "unknown"
    warnings: list[str] = []
    orientation_info: dict[str, Any] = {}

    if suffix in TEXT_EXTENSIONS:
        body = _read_text_file(src)
        method = "text-copy"
    elif suffix in IMAGE_EXTENSIONS:
        if ocr == "off":
            raise DocumentExtractError("This is an image file; OCR is disabled. Call with ocr='auto' or ocr='force'.")
        body, warnings, orientation_info = _extract_with_tesseract(
            src,
            languages=languages,
            psm=psm,
            orientation=orientation,
            tessdata_dir=tessdata_dir,
        )
        method = "tesseract"
    elif suffix in DOC_EXTENSIONS or not suffix:
        body, warnings = _extract_with_markitdown(src)
        method = "markitdown"
    else:
        body, warnings = _extract_with_markitdown(src)
        method = "markitdown-unknown-extension"
        warnings.append(f"Unknown extension {suffix!r}; attempted MarkItDown extraction.")

    metadata = {
        "document_extract_version": PLUGIN_VERSION,
        "cache_schema_version": CACHE_SCHEMA_VERSION,
        "created_at": _iso(now),
        "expires_at": _iso(expires_at),
        "source_name": "[redacted]" if sensitive else src.name,
        "source_path": "[redacted]" if sensitive else str(src),
        "source_extension": suffix,
        "source_sha256": source_hash,
        "source_size_bytes": size_bytes,
        "method": method,
        "cache_key": cache_key,
        "sensitive": sensitive,
        "warnings": warnings,
        "orientation": orientation_info,
        "text_chars": len(body or ""),
        "markdown_path": str(md_path),
        "metadata_path": str(meta_path),
    }
    markdown = _wrap_markdown(body=body, metadata=metadata)
    metadata["markdown_chars"] = len(markdown)

    md_path.write_text(markdown, encoding="utf-8")
    meta_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "success": True,
        "cache_hit": False,
        "source": metadata["source_path"],
        "source_extension": suffix,
        "method": method,
        "markdown_path": str(md_path),
        "metadata_path": str(meta_path),
        "chars": len(markdown),
        "text_chars": len(body or ""),
        "size_mb": round(size_bytes / 1024 / 1024, 3),
        "warnings": warnings,
        "orientation": orientation_info,
        "preview": markdown[:preview_chars] if preview_chars else "",
        "expires_at": metadata["expires_at"],
        "next_step": "Read markdown_path with read_file in chunks; do not read the original non-Markdown file directly.",
        "dependencies": _dependency_status(),
    }


def _dependency_status() -> dict[str, Any]:
    langs = _tesseract_languages()
    tessdata_dirs = [str(path) for path in _candidate_tessdata_dirs()]
    return {
        "markitdown_available": _markitdown_available(),
        "markitdown_version": _markitdown_version(),
        "tesseract_available": _tesseract_available(),
        "tesseract_path": _tesseract_path(),
        "tesseract_version": _tesseract_version(),
        "tesseract_languages": langs,
        "tessdata_dirs": tessdata_dirs,
        "recommended_ocr_languages_present": all(lang in langs for lang in ["eng", "rus", "osd"]) if langs else False,
        "pillow_available": _pillow_available(),
    }


def _is_within(path: Path, root: Path) -> bool:
    try:
        path.resolve(strict=False).relative_to(root.resolve(strict=False))
        return True
    except Exception:
        return False


def _remove_empty_dirs(root: Path) -> None:
    if not root.exists():
        return
    for directory in sorted([p for p in root.rglob("*") if p.is_dir()], key=lambda p: len(str(p)), reverse=True):
        try:
            directory.rmdir()
        except OSError:
            pass


def _delete_path(path: Path, root: Path, deleted: list[dict[str, Any]], *, dry_run: bool) -> None:
    if not path.exists() or not path.is_file() or not _is_within(path, root):
        return
    size = path.stat().st_size
    deleted.append({"path": str(path), "bytes": size})
    if not dry_run:
        path.unlink(missing_ok=True)


def _cleanup_cache(
    cache_root: Path,
    *,
    expired_only: bool = True,
    older_than_days: float | None = None,
    all_files: bool = False,
    dry_run: bool = False,
) -> dict[str, Any]:
    cache_root.mkdir(parents=True, exist_ok=True)
    now = _now_utc()
    cutoff = None if older_than_days is None else time.time() - (older_than_days * 86400)
    deleted: list[dict[str, Any]] = []
    considered: set[Path] = set()

    if all_files:
        for path in cache_root.rglob("*"):
            if path.is_file():
                _delete_path(path, cache_root, deleted, dry_run=dry_run)
        if not dry_run:
            _remove_empty_dirs(cache_root)
        return _cleanup_summary(deleted, dry_run=dry_run)

    for meta_path in cache_root.rglob("*.json"):
        metadata = _load_json(meta_path) or {}
        md_raw = metadata.get("markdown_path")
        md_path = Path(md_raw) if md_raw else None
        targets = [meta_path]
        if md_path and _is_within(md_path, cache_root):
            targets.append(md_path)
        expires_at = _parse_iso(metadata.get("expires_at"))
        expired = bool(expires_at and expires_at <= now)
        older = bool(cutoff and meta_path.stat().st_mtime <= cutoff)
        should_delete = expired or older or (not expired_only and older_than_days is None)
        if should_delete:
            for target in targets:
                considered.add(target)
                _delete_path(target, cache_root, deleted, dry_run=dry_run)

    # Also catch orphan markdown files when older_than_days is explicitly requested.
    if cutoff is not None:
        for path in cache_root.rglob("*.md"):
            if path not in considered and path.stat().st_mtime <= cutoff:
                _delete_path(path, cache_root, deleted, dry_run=dry_run)

    if not dry_run:
        _remove_empty_dirs(cache_root)
    return _cleanup_summary(deleted, dry_run=dry_run)


def _cleanup_summary(deleted: list[dict[str, Any]], *, dry_run: bool) -> dict[str, Any]:
    total_bytes = sum(int(item.get("bytes") or 0) for item in deleted)
    return {
        "success": True,
        "dry_run": dry_run,
        "deleted_count": len(deleted),
        "deleted_mb": round(total_bytes / 1024 / 1024, 3),
        "deleted": deleted[:200],
        "truncated": len(deleted) > 200,
    }


def _cache_stats(cache_root: Path) -> dict[str, Any]:
    file_count = 0
    total_bytes = 0
    expired_count = 0
    now = _now_utc()
    for path in cache_root.rglob("*"):
        if path.is_file():
            file_count += 1
            total_bytes += path.stat().st_size
            if path.suffix == ".json":
                metadata = _load_json(path) or {}
                expires_at = _parse_iso(metadata.get("expires_at"))
                if expires_at and expires_at <= now:
                    expired_count += 1
    return {
        "cache_path": str(cache_root),
        "file_count": file_count,
        "size_mb": round(total_bytes / 1024 / 1024, 3),
        "expired_metadata_count": expired_count,
    }


def _iter_batch_files(args: dict[str, Any]) -> list[Path]:
    items: list[str] = []
    if args.get("path"):
        items.append(str(args.get("path")))
    if args.get("paths"):
        items.extend(str(p) for p in args.get("paths") or [])
    if not items:
        raise DocumentExtractError("Provide path or paths for batch extraction.")

    recursive = _coerce_bool(args.get("recursive"), False)
    include_unknown = _coerce_bool(args.get("include_unknown"), False)
    files: list[Path] = []
    for item in items:
        p = _normalize_path(item)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            iterator: Iterable[Path] = p.rglob("*") if recursive else p.glob("*")
            for candidate in iterator:
                if not candidate.is_file():
                    continue
                if include_unknown or candidate.suffix.lower() in SUPPORTED_EXTENSIONS:
                    files.append(candidate)
        else:
            raise DocumentExtractError(f"Path not found: {p}")

    # Stable order and de-duplicate paths.
    unique: dict[str, Path] = {}
    for path in sorted(files, key=lambda x: str(x).lower()):
        unique[str(path.resolve(strict=False)).lower()] = path
    return list(unique.values())


def handle_document_extract(args: dict, **kw) -> str:
    """Convert a local document/image to cached Markdown and return its path."""
    try:
        return tool_result(_extract_one(args, run_cleanup=True))
    except Exception as exc:
        return tool_error(
            f"document_extract failed: {type(exc).__name__}: {exc}",
            setup_hint=(
                "Install Python dependencies with: python -m pip install -r requirements.txt. "
                "Install Tesseract OCR separately for image OCR."
            ),
        )


def handle_document_extract_status(args: dict | None = None, **kw) -> str:
    """Return dependency and cache status."""
    cache_root = _cache_root()
    payload = {
        "success": True,
        "plugin_version": PLUGIN_VERSION,
        "cache": _cache_stats(cache_root),
        "dependencies": _dependency_status(),
        "supported_extensions": sorted(SUPPORTED_EXTENSIONS),
        "notes": [
            "MarkItDown handles documents and structured files.",
            "Tesseract handles OCR for image files; install rus/eng language data if needed.",
        ],
    }
    return tool_result(payload)


def handle_document_extract_cleanup(args: dict | None = None, **kw) -> str:
    """Clean the document extraction cache."""
    args = args or {}
    cache_root = _cache_root()
    all_files = _coerce_bool(args.get("all"), False)
    expired_only = _coerce_bool(args.get("expired_only"), True)
    dry_run = _coerce_bool(args.get("dry_run"), False)
    older_than_days = args.get("older_than_days")
    older = None if older_than_days is None else _coerce_float(older_than_days, 0.0, 0.0, 3650.0)
    payload = _cleanup_cache(
        cache_root,
        expired_only=expired_only,
        older_than_days=older,
        all_files=all_files,
        dry_run=dry_run,
    )
    payload["cache_path"] = str(cache_root)
    return tool_result(payload)


def handle_document_extract_batch(args: dict, **kw) -> str:
    """Extract a folder or a list of files and return a manifest."""
    try:
        cache_root = _cache_root()
        _cleanup_cache(cache_root, expired_only=True, dry_run=False)
        max_files = _coerce_int(args.get("max_files"), 50, 1, 1000)
        files = _iter_batch_files(args)
        if len(files) > max_files:
            files = files[:max_files]
            truncated = True
        else:
            truncated = False

        results: list[dict[str, Any]] = []
        for path in files:
            item_args = dict(args)
            item_args["path"] = str(path)
            item_args.pop("paths", None)
            item_args.setdefault("preview_chars", 0)
            try:
                result = _extract_one(item_args, run_cleanup=False)
                results.append({
                    "success": True,
                    "source": result.get("source"),
                    "method": result.get("method"),
                    "markdown_path": result.get("markdown_path"),
                    "metadata_path": result.get("metadata_path"),
                    "text_chars": result.get("text_chars"),
                    "warnings": result.get("warnings", []),
                    "cache_hit": result.get("cache_hit", False),
                })
            except Exception as exc:
                results.append({"success": False, "source": str(path), "error": f"{type(exc).__name__}: {exc}"})

        manifest = {
            "created_at": _iso(_now_utc()),
            "count": len(results),
            "ok_count": sum(1 for r in results if r.get("success")),
            "failed_count": sum(1 for r in results if not r.get("success")),
            "truncated": truncated,
            "results": results,
        }
        manifest_key = hashlib.sha256(json.dumps(manifest, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:16]
        manifest_path = cache_root / "manifests" / f"batch_{int(time.time())}_{manifest_key}.json"
        manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        return tool_result({"success": True, "manifest_path": str(manifest_path), **manifest})
    except Exception as exc:
        return tool_error(f"document_extract_batch failed: {type(exc).__name__}: {exc}")
