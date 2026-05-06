from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

ALLOWED_MIME_TYPES = frozenset(
    {
        "application/pdf",
        "image/jpeg",
        "image/png",
        "image/tiff",
    }
)

MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024  # 50 MB
MAX_SESSION_SIZE_BYTES = 200 * 1024 * 1024  # 200 MB

_SAFE_FILENAME_PATTERN = re.compile(r"^[\w\-. ()]+$", re.UNICODE)
_PATH_TRAVERSAL_PATTERN = re.compile(r"(^|[\\/])\.\.($|[\\/])")


@dataclass(frozen=True, slots=True)
class ValidationResult:
    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_mime_type(mime_type: str) -> list[str]:
    """Return error messages if the MIME type is not allowed."""
    if mime_type not in ALLOWED_MIME_TYPES:
        return [f"MIME type '{mime_type}' is not allowed. Accepted: {', '.join(sorted(ALLOWED_MIME_TYPES))}"]
    return []


def validate_file_size(size_bytes: int) -> list[str]:
    """Return error messages if the file exceeds the per-file limit."""
    if size_bytes > MAX_FILE_SIZE_BYTES:
        mb = size_bytes / (1024 * 1024)
        return [f"File size {mb:.1f} MB exceeds the 50 MB limit."]
    if size_bytes < 0:
        return ["File size cannot be negative."]
    return []


def validate_session_size(current_total_bytes: int, new_file_bytes: int) -> list[str]:
    """Return error messages if the session total would exceed the limit."""
    total = current_total_bytes + new_file_bytes
    if total > MAX_SESSION_SIZE_BYTES:
        mb = total / (1024 * 1024)
        return [f"Session total {mb:.1f} MB would exceed the 200 MB limit."]
    return []


def sanitize_filename(filename: str) -> tuple[str, list[str]]:
    """Sanitize a filename and return (safe_name, errors).

    Strips path components, rejects traversal attempts, and validates characters.
    """
    errors: list[str] = []
    stripped = os.path.basename(filename)
    if not stripped:
        return "", ["Filename is empty after sanitization."]

    if _PATH_TRAVERSAL_PATTERN.search(filename):
        errors.append("Filename contains path traversal sequences.")

    if not _SAFE_FILENAME_PATTERN.match(stripped):
        errors.append(f"Filename '{stripped}' contains disallowed characters.")

    return stripped, errors


def validate_file(
    filename: str,
    mime_type: str,
    size_bytes: int,
    current_session_bytes: int = 0,
) -> ValidationResult:
    """Run all validations on a single file upload."""
    errors: list[str] = []

    _, name_errors = sanitize_filename(filename)
    errors.extend(name_errors)
    errors.extend(validate_mime_type(mime_type))
    errors.extend(validate_file_size(size_bytes))
    errors.extend(validate_session_size(current_session_bytes, size_bytes))

    return ValidationResult(valid=len(errors) == 0, errors=errors)


__all__ = [
    "ALLOWED_MIME_TYPES",
    "MAX_FILE_SIZE_BYTES",
    "MAX_SESSION_SIZE_BYTES",
    "ValidationResult",
    "sanitize_filename",
    "validate_file",
    "validate_file_size",
    "validate_mime_type",
    "validate_session_size",
]
