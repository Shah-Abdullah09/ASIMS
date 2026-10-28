"""Upload locations. Files are saved through Django's storage API (settings.STORAGES['default']),
so switching from local media to S3 only needs a settings change."""
import os
import uuid


def system_file_name(original_name):
    """Replace the uploaded name with a random one, keeping only a lowercase extension.
    The upload views pass a name whose extension comes from the detected file type."""
    ext = os.path.splitext(original_name)[1].lower()
    return f'{uuid.uuid4().hex}{ext}'


def scholarship_document_path(instance, filename):
    app = instance.application
    return f'scholarships/{app.student_id}/{app.pk}/{instance.slot}/{system_file_name(filename)}'


def declaration_scan_path(instance, filename):
    app = instance.application
    return f'scholarships/{app.student_id}/{app.pk}/declarations/{system_file_name(filename)}'


def award_letter_path(instance, filename):
    app = instance.application
    return f'scholarships/{app.student_id}/{app.pk}/award-letter/{system_file_name(filename)}'
