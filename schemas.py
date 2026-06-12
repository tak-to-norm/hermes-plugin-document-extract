"""Tool schemas for the document_extract Hermes plugin."""
from __future__ import annotations

COMMON_EXTRACTION_PROPERTIES = {
    "ocr": {
        "type": "string",
        "enum": ["auto", "force", "off"],
        "default": "auto",
        "description": "OCR mode. auto/force OCR image files with Tesseract; off disables OCR.",
    },
    "languages": {
        "type": "string",
        "default": "rus+eng",
        "description": "Tesseract languages, e.g. rus+eng or eng. Used for image OCR.",
    },
    "psm": {
        "type": "integer",
        "default": 11,
        "description": "Tesseract page segmentation mode. 11 is good for screenshots/sparse text; 6 for block text.",
    },
    "orientation": {
        "type": "string",
        "enum": ["auto", "off"],
        "default": "auto",
        "description": "For image OCR, use Tesseract OSD to detect rotated text and auto-rotate when Pillow is available.",
    },
    "tessdata_dir": {
        "type": "string",
        "description": "Optional explicit Tesseract tessdata directory containing *.traineddata files.",
    },
    "max_file_mb": {
        "type": "number",
        "default": 100,
        "description": "Reject local files larger than this size.",
    },
    "preview_chars": {
        "type": "integer",
        "default": 500,
        "description": "Return only this many initial characters as preview. Use 0 for private/large documents.",
    },
    "sensitive": {
        "type": "boolean",
        "default": False,
        "description": "Privacy mode: no preview by default, hash-only output names, redacted source path in metadata, shorter default TTL.",
    },
    "cache": {
        "type": "boolean",
        "default": True,
        "description": "Reuse cached extraction when the same file and extraction settings are seen again.",
    },
    "ttl_days": {
        "type": "number",
        "description": "How long extracted Markdown should remain in Hermes cache. Default: 7 days, or 1 day in sensitive mode. 0 disables expiry.",
    },
}

DOCUMENT_EXTRACT_SCHEMA = {
    "name": "document_extract",
    "description": (
        "Use this BEFORE read_file when the user asks to read, summarize, analyze, "
        "inspect, translate, compare, or extract content from a local non-Markdown "
        "document or image. It converts the source into cached Markdown/text and "
        "returns markdown_path plus extraction metadata. Do not read PDF, DOCX, PPTX, "
        "XLSX, EPUB, HTML, or image files directly when this tool is available; call "
        "document_extract first, then read the returned markdown_path in chunks with read_file."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "Local file path to extract. Supports Windows paths like C:/... or D:/..., and MSYS paths like /c/Users/...",
            },
            **COMMON_EXTRACTION_PROPERTIES,
        },
        "required": ["path"],
        "additionalProperties": False,
    },
}

DOCUMENT_EXTRACT_BATCH_SCHEMA = {
    "name": "document_extract_batch",
    "description": (
        "Extract a folder or a list of local documents/images into cached Markdown files. "
        "Use this when the user asks to process a folder, inbox, or multiple documents. "
        "Provide either path, paths, or both. Returns a manifest_path and per-file markdown_path values."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "A local file or directory path to process.",
            },
            "paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Optional explicit list of local file paths to process.",
            },
            "recursive": {
                "type": "boolean",
                "default": False,
                "description": "When path is a directory, process files recursively.",
            },
            "include_unknown": {
                "type": "boolean",
                "default": False,
                "description": "Try MarkItDown on unknown extensions instead of skipping them.",
            },
            "max_files": {
                "type": "integer",
                "default": 50,
                "description": "Maximum number of files to process in one batch.",
            },
            **COMMON_EXTRACTION_PROPERTIES,
        },
        "additionalProperties": False,
        "anyOf": [{"required": ["path"]}, {"required": ["paths"]}],
    },
}

DOCUMENT_EXTRACT_STATUS_SCHEMA = {
    "name": "document_extract_status",
    "description": "Check document_extract plugin status: MarkItDown, Tesseract, OCR languages, Pillow, cache path and cache size.",
    "parameters": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
}

DOCUMENT_EXTRACT_CLEANUP_SCHEMA = {
    "name": "document_extract_cleanup",
    "description": "Clean the Hermes document extraction cache. Use for privacy cleanup or cache maintenance.",
    "parameters": {
        "type": "object",
        "properties": {
            "expired_only": {
                "type": "boolean",
                "default": True,
                "description": "Delete files whose metadata says they have expired. Use all=true for full cache deletion; expired_only=false only broadens cleanup when older_than_days is set.",
            },
            "older_than_days": {
                "type": "number",
                "description": "Also delete cache files older than this many days.",
            },
            "all": {
                "type": "boolean",
                "default": False,
                "description": "Delete all document-extract cache files.",
            },
            "dry_run": {
                "type": "boolean",
                "default": False,
                "description": "Report what would be deleted without deleting files.",
            },
        },
        "additionalProperties": False,
    },
}
