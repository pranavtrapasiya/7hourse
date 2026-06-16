import os
import mimetypes
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_EXTENSIONS = ['.jpg', '.jpeg', '.png', '.webp']
ALLOWED_VIDEO_EXTENSIONS = ['.mp4', '.mov', '.webm', '.avi']
ALLOWED_IMAGE_MIMES = ['image/jpeg', 'image/png', 'image/webp']
ALLOWED_VIDEO_MIMES = ['video/mp4', 'video/quicktime', 'video/webm', 'video/x-msvideo']
MAX_IMAGE_SIZE_MB = 10
MAX_VIDEO_SIZE_MB = 150

# Executable / dangerous extensions to reject outright
DANGEROUS_EXTENSIONS = {
    '.exe', '.bat', '.cmd', '.com', '.msi', '.scr', '.pif', '.vbs', '.vbe',
    '.js', '.jse', '.wsf', '.wsh', '.ps1', '.ps2', '.psc1', '.psc2',
    '.sh', '.bash', '.csh', '.ksh', '.py', '.rb', '.pl', '.php', '.asp',
    '.aspx', '.jsp', '.jar', '.war', '.ear', '.dll', '.so', '.dylib',
    '.htaccess', '.htpasswd', '.svg', '.html', '.htm', '.xhtml', '.shtml',
}


def validate_image_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext in DANGEROUS_EXTENSIONS:
        raise ValidationError('This file type is not allowed for security reasons.')
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(
            f'Unsupported format. Allowed: {", ".join(ALLOWED_IMAGE_EXTENSIONS)}'
        )


def validate_image_mime(value):
    """Validate MIME type by reading file content, not just extension."""
    mime_type, _ = mimetypes.guess_type(value.name)
    if mime_type and mime_type not in ALLOWED_IMAGE_MIMES:
        raise ValidationError(
            f'Invalid image file type. Allowed: {", ".join(ALLOWED_IMAGE_MIMES)}'
        )


def validate_image_size(value):
    limit = MAX_IMAGE_SIZE_MB * 1024 * 1024
    if value.size > limit:
        raise ValidationError(f'Image must be under {MAX_IMAGE_SIZE_MB}MB.')


def validate_video_extension(value):
    ext = os.path.splitext(value.name)[1].lower()
    if ext in DANGEROUS_EXTENSIONS:
        raise ValidationError('This file type is not allowed for security reasons.')
    if ext not in ALLOWED_VIDEO_EXTENSIONS:
        raise ValidationError(
            f'Unsupported video format. Allowed: {", ".join(ALLOWED_VIDEO_EXTENSIONS)}'
        )


def validate_video_mime(value):
    """Validate MIME type by reading file content, not just extension."""
    mime_type, _ = mimetypes.guess_type(value.name)
    if mime_type and mime_type not in ALLOWED_VIDEO_MIMES:
        raise ValidationError(
            f'Invalid video file type. Allowed: {", ".join(ALLOWED_VIDEO_MIMES)}'
        )


def validate_video_size(value):
    limit = MAX_VIDEO_SIZE_MB * 1024 * 1024
    if value.size > limit:
        raise ValidationError(f'Video must be under {MAX_VIDEO_SIZE_MB}MB.')


def validate_mobile_number(value, country_code='+91'):
    """Validate mobile number: digits only; 10 digits for India (+91)."""
    digits = ''.join(c for c in str(value).strip() if c.isdigit())
    if not digits:
        raise ValidationError('Mobile number is required.')
    if country_code == '+91' and len(digits) != 10:
        raise ValidationError('Indian mobile numbers must be exactly 10 digits.')
    if len(digits) < 6 or len(digits) > 15:
        raise ValidationError('Mobile number must be between 6 and 15 digits.')
    return digits
