from django.core.exceptions import ValidationError

from evaluations.constants import MAX_DECK_BYTES


def validate_pdf(upload):
    if not upload:
        return
    name = getattr(upload, "name", "") or ""
    if not str(name).lower().endswith(".pdf"):
        raise ValidationError("Upload a PDF.")
    size = getattr(upload, "size", None)
    if size is not None and size > MAX_DECK_BYTES:
        raise ValidationError("PDF must be 20 MB or smaller.")
    read = getattr(upload, "read", None)
    if read is None:
        return
    header = upload.read(5)
    if hasattr(upload, "seek"):
        upload.seek(0)
    if header != b"%PDF-":
        raise ValidationError("That file is not a PDF.")
