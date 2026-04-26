"""
agents/document_parser.py
========================
File parsing utilities for Document Verification Agent.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from llama_parse import LlamaParse


def _get_llamaparse():
    """Lazy import of LlamaParse to avoid heavy imports when not needed."""
    from llama_parse import LlamaParse
    return LlamaParse


def parse_file(raw_file: Any) -> str:
    """
    Parse a file into Markdown text using LlamaParse.
    Falls back to plain text read if LlamaParse is unavailable
    or the file is already a text/markdown file.
    """
    filepath = Path(raw_file.file_path)

    # Plain text / markdown fallback (no API call needed)
    if filepath.suffix.lower() in {".txt", ".md"}:
        return filepath.read_text(encoding="utf-8", errors="replace")

    # Attempt LlamaParse for PDF / image files
    llamaparse_key = os.getenv("LLAMA_CLOUD_API_KEY")
    if not llamaparse_key:
        # Fallback for development/testing
        return f"[MOCK] Parsed content for {raw_file.filename}"

    try:
        LlamaParse = _get_llamaparse()
        parser = LlamaParse(
            api_key=llamaparse_key,
            result_type="markdown",
            verbose=False,
        )
        documents = parser.load_data(str(filepath))
        return "\n\n".join(doc.text for doc in documents)
    except Exception as exc:
        # Log error but don't crash - return placeholder
        return f"[PARSE_FAILED] Could not parse {raw_file.filename}: {exc}"