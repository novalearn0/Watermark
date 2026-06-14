import os
import re
from config import MAX_FILE_SIZE_BYTES

ALLOWED_VIDEO_MIMES = {
    "video/mp4", "video/x-matroska", "video/webm",
    "video/avi", "video/quicktime", "video/x-msvideo",
    "video/x-flv", "video/3gpp", "video/mpeg",
}
ALLOWED_IMAGE_MIMES = {
    "image/jpeg", "image/png", "image/webp",
}
ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def is_valid_file_size(size_bytes: int) -> bool:
    return 0 < size_bytes <= MAX_FILE_SIZE_BYTES


def is_valid_video(mime_type: str | None) -> bool:
    if not mime_type:
        return False
    return mime_type.lower() in ALLOWED_VIDEO_MIMES


def is_valid_image(mime_type: str | None, filename: str | None = None) -> bool:
    if mime_type and mime_type.lower() in ALLOWED_IMAGE_MIMES:
        return True
    if filename:
        ext = os.path.splitext(filename)[1].lower()
        return ext in ALLOWED_IMAGE_EXTENSIONS
    return False


def sanitize_path(base_dir: str, filename: str) -> str:
    """Prevent path traversal attacks."""
    filename = os.path.basename(filename)
    filename = re.sub(r"[^\w\.\-]", "_", filename)
    full = os.path.realpath(os.path.join(base_dir, filename))
    base = os.path.realpath(base_dir)
    if not full.startswith(base):
        raise ValueError(f"Path traversal detected: {filename}")
    return full


def sanitize_text(text: str, max_len: int = 200) -> str:
    """Strip shell-dangerous characters from watermark text."""
    text = text.strip()[:max_len]
    # Allow printable unicode but remove shell metacharacters
    text = re.sub(r"[`$\\;|&><]", "", text)
    return text


def validate_opacity(val: float) -> float:
    return max(0.1, min(1.0, val))


def validate_size(val: float) -> float:
    return max(0.05, min(0.9, val))


def validate_speed(val: float) -> float:
    return max(10.0, min(500.0, val))


def validate_font_size(val: int) -> int:
    return max(10, min(200, val))
