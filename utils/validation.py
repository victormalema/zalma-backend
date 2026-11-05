"""
utils/validation.py
Small input-cleaning helpers. The frontend escapes output, but the backend should
also refuse obviously hostile or malformed input (defence in depth).
"""
import re
from urllib.parse import urlparse

_EMAIL_RE = re.compile(r"^[A-Za-z0-9._%+\-]+@[A-Za-z0-9\-]+(\.[A-Za-z0-9\-]+)*\.[A-Za-z]{2,}$")
_CONTROL_RE = re.compile(r"[\x00-\x1f\x7f]")


class ValidationError(ValueError):
    pass


def valid_email(email: str) -> bool:
    return bool(email) and len(email) <= 254 and bool(_EMAIL_RE.match(email))


def clean_name(name, max_len: int = 80):
    """Display name: no control characters, no < > (HTML), trimmed, length-capped.
    Returns None for empty input. Raises ValidationError for hostile characters."""
    if name is None:
        return None
    name = _CONTROL_RE.sub("", str(name)).strip()
    if not name:
        return None
    if "<" in name or ">" in name:
        raise ValidationError("Name can't contain < or > characters")
    if len(name) > max_len:
        raise ValidationError(f"Name must be {max_len} characters or fewer")
    return name


def clean_phone(phone, max_len: int = 20):
    if phone is None or str(phone).strip() == "":
        return None
    phone = str(phone).strip()
    if len(phone) > max_len or not re.fullmatch(r"[0-9+\-() ]+", phone):
        raise ValidationError("Enter a valid phone number")
    return phone


def clean_https_url(value, max_len: int = 500, label: str = "link"):
    """Only plain https URLs (blocks javascript:, data:, http:, huge strings)."""
    value = str(value or "").strip()
    if not value:
        raise ValidationError(f"A {label} is required")
    if len(value) > max_len:
        raise ValidationError(f"The {label} is too long")
    if _CONTROL_RE.search(value) or " " in value:
        raise ValidationError(f"Enter a valid {label}")
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.netloc or "@" in parsed.netloc:
        raise ValidationError(f"The {label} must be a full https:// address")
    return value
