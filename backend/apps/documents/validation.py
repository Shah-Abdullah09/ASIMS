"""Checks every uploaded file by its real content, not by its name or the browser's claimed type."""
from django.conf import settings
from PIL import Image, UnidentifiedImageError
from rest_framework import serializers

# leading bytes ("magic numbers") of each accepted format -> (MIME type, extension)
SIGNATURES = [
    (b'%PDF-', ('application/pdf', 'pdf')),
    (b'\x89PNG\r\n\x1a\n', ('image/png', 'png')),
    (b'\xff\xd8\xff', ('image/jpeg', 'jpg')),
]
ALLOWED_LABEL = 'PDF, JPG or PNG'


def max_upload_bytes():
    return settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024


def inspect_upload(upload):
    """Return (content_type, extension) for a valid upload, or raise a ValidationError with a clear message."""
    if upload.size == 0:
        raise serializers.ValidationError('The file is empty.')
    if upload.size > max_upload_bytes():
        raise serializers.ValidationError(
            f'The file is {upload.size / (1024 * 1024):.1f} MB. The limit is {settings.MAX_UPLOAD_SIZE_MB} MB.')

    upload.seek(0)
    head = upload.read(16)
    upload.seek(0)
    detected = next((info for magic, info in SIGNATURES if head.startswith(magic)), None)
    if detected is None:
        raise serializers.ValidationError(f'Only {ALLOWED_LABEL} files are accepted. This file is a different type.')

    content_type, ext = detected
    if content_type.startswith('image/'):
        try:
            with Image.open(upload) as image:
                image.verify()  # catches files that only pretend to be images
        except (UnidentifiedImageError, OSError, SyntaxError):
            raise serializers.ValidationError('This image file is damaged or not a real image.')
        finally:
            upload.seek(0)
    return content_type, ext
