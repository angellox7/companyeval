"""Collect the four sources, ask the model, and store a verified assessment."""

from io import BytesIO

from django.conf import settings

from evaluations.ai.apply import apply_assessment
from evaluations.ai.client import request_assessment, transcribe_deck
from evaluations.ai.extract import ExtractError, extract_pdf, fetch_website, pdf_has_text
from evaluations.constants import SOURCE_KINDS
from evaluations.models import SectorBenchmark, SourceDocument

TEXT_LAYER_DETAIL = "Read from the PDF text layer. The page reading returned no text."


class GenerationError(Exception):
    pass


def _save_source(deal, kind, body, detail):
    document, _created = SourceDocument.objects.update_or_create(
        deal=deal,
        kind=kind,
        defaults={"body": body or "", "detail": detail or ""},
    )
    return document


def _deck_text(deal):
    if not deal.deck:
        return "", ""
    try:
        with deal.deck.open("rb") as handle:
            pdf_bytes = handle.read()
    except Exception as exc:
        return "", f"The deck could not be read. {exc}"

    transcript = ""
    attempted = bool(settings.OPENAI_API_KEY)
    if attempted:
        try:
            transcript = transcribe_deck(deal.deck.name, pdf_bytes)
        except Exception:
            transcript = ""
    if pdf_has_text(transcript):
        return transcript, ""

    try:
        raw = extract_pdf(BytesIO(pdf_bytes))
    except Exception as exc:
        return "", f"The deck could not be read. {exc}"
    if not pdf_has_text(raw):
        return "", "This PDF has no extractable text."
    if attempted:
        return raw, TEXT_LAYER_DETAIL
    return raw, ""


def _website_text(deal):
    if not (deal.website or "").strip():
        return "", ""
    try:
        text, truncated = fetch_website(deal.website)
    except ExtractError as exc:
        return "", str(exc)
    except Exception:
        return "", "The website could not be read."
    detail = "The page was shortened to the first 1 MB." if truncated else ""
    return text, detail


def collect_sources(deal):
    texts = {
        "deck": _deck_text(deal),
        "website": _website_text(deal),
        "founder_bios": (deal.founder_bios or "", ""),
        "call_notes": (deal.call_notes or "", ""),
    }
    documents = {}
    for kind, _label in SOURCE_KINDS:
        body, detail = texts[kind]
        documents[kind] = _save_source(deal, kind, body, detail)
    return documents


def usable_sources(documents):
    return {
        kind: document
        for kind, document in documents.items()
        if (document.body or "").strip()
    }


def generate_assessment(deal):
    documents = collect_sources(deal)
    usable = usable_sources(documents)
    if not usable:
        raise GenerationError(
            "Add a deck, website, founder bios, or first-call notes with readable text before generating."
        )
    if not settings.OPENAI_API_KEY:
        raise GenerationError(
            "Set OPENAI_API_KEY in the environment or in a .env file in the project root."
        )
    benchmark = SectorBenchmark.objects.filter(sector=deal.sector).first()
    try:
        payload = request_assessment(deal, usable, benchmark)
    except GenerationError:
        raise
    except Exception as exc:
        raise GenerationError(f"The assessment could not be generated. {exc}") from exc
    if not isinstance(payload, dict):
        raise GenerationError("The assessment could not be generated. The model returned an unexpected response.")
    return apply_assessment(deal, payload, documents, settings.OPENAI_MODEL)
