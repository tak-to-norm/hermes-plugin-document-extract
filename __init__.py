"""Hermes plugin: document_extract.

Registers native document extraction tools under the existing `file` toolset.
No ordinary skill is installed; tool schemas carry the behavior guidance.
"""
from __future__ import annotations

try:
    from .schemas import (
        DOCUMENT_EXTRACT_BATCH_SCHEMA,
        DOCUMENT_EXTRACT_CLEANUP_SCHEMA,
        DOCUMENT_EXTRACT_SCHEMA,
        DOCUMENT_EXTRACT_STATUS_SCHEMA,
    )
    from .tools import (
        handle_document_extract,
        handle_document_extract_batch,
        handle_document_extract_cleanup,
        handle_document_extract_status,
    )
except ImportError:  # pragma: no cover - allows pytest/dev checks from repo root
    from schemas import (  # type: ignore
        DOCUMENT_EXTRACT_BATCH_SCHEMA,
        DOCUMENT_EXTRACT_CLEANUP_SCHEMA,
        DOCUMENT_EXTRACT_SCHEMA,
        DOCUMENT_EXTRACT_STATUS_SCHEMA,
    )
    from tools import (  # type: ignore
        handle_document_extract,
        handle_document_extract_batch,
        handle_document_extract_cleanup,
        handle_document_extract_status,
    )


def register(ctx) -> None:
    """Register document extraction tools with Hermes Agent."""
    ctx.register_tool(
        name="document_extract",
        toolset="file",
        schema=DOCUMENT_EXTRACT_SCHEMA,
        handler=handle_document_extract,
        emoji="📄",
        description="Convert a local document/image to cached Markdown before reading it.",
    )
    ctx.register_tool(
        name="document_extract_batch",
        toolset="file",
        schema=DOCUMENT_EXTRACT_BATCH_SCHEMA,
        handler=handle_document_extract_batch,
        emoji="🗂️",
        description="Batch-convert a folder or list of documents/images to cached Markdown.",
    )
    ctx.register_tool(
        name="document_extract_status",
        toolset="file",
        schema=DOCUMENT_EXTRACT_STATUS_SCHEMA,
        handler=handle_document_extract_status,
        emoji="🧪",
        description="Check document extraction dependencies and cache status.",
    )
    ctx.register_tool(
        name="document_extract_cleanup",
        toolset="file",
        schema=DOCUMENT_EXTRACT_CLEANUP_SCHEMA,
        handler=handle_document_extract_cleanup,
        emoji="🧹",
        description="Clean the document extraction cache.",
    )
