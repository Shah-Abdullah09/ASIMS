"""Reading the text of an uploaded document for the automatic document check.

PDFs with a text layer are read with pypdf; images (JPG, PNG) with the Tesseract OCR engine through pytesseract.
Tesseract is a separate program: when it is not installed, images are reported as "unavailable" instead of
failing, so the rest of ASIMS works without it."""
from dataclasses import dataclass

READ, NO_TEXT, UNAVAILABLE, FAILED = 'read', 'no_text', 'unavailable', 'failed'


@dataclass
class Reading:
    status: str
    text: str = ''


def engine_available():
    """True when the Tesseract program can be run."""
    try:
        import pytesseract
        pytesseract.get_tesseract_version()
        return True
    except Exception:  # not installed, not on PATH, or not runnable
        return False


def _read_pdf(fileobj):
    from pypdf import PdfReader
    reader = PdfReader(fileobj)
    return '\n'.join(page.extract_text() or '' for page in reader.pages)


def _read_image(fileobj):
    import pytesseract
    from PIL import Image
    with Image.open(fileobj) as image:
        return pytesseract.image_to_string(image.convert('L'), lang='eng')


def read_text(field_file, content_type):
    """The text of a stored file (a Django FieldFile) as a Reading."""
    try:
        with field_file.open('rb') as fileobj:
            if content_type == 'application/pdf':
                text = _read_pdf(fileobj)
            else:
                if not engine_available():
                    return Reading(UNAVAILABLE)
                text = _read_image(fileobj)
    except Exception:  # a damaged file must not break the check of the others
        return Reading(FAILED)
    text = text.strip()
    return Reading(READ, text) if text else Reading(NO_TEXT)
