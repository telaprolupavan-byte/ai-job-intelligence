from __future__ import annotations

import hashlib

from apps.api.services.resume_ai.deterministic import normalize_text


def compute_content_fingerprint(text: str) -> str:
    """Deterministic content identity for a resume version.

    Based only on normalized extracted text, never on filename, so that
    the same resume content uploaded under a different filename is still
    recognized as the same content.
    """
    normalized = normalize_text(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
