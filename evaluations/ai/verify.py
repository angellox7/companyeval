"""A claim counts only when its excerpt is copied from the cited source."""

from evaluations.constants import CATEGORY_LABELS, SOURCE_LABELS


def normalize_text(value):
    return " ".join((value or "").split()).casefold()


def excerpt_in_source(excerpt, source_text):
    needle = normalize_text(excerpt)
    haystack = normalize_text(source_text)
    if not needle or not haystack:
        return False
    return needle in haystack


def _clean_claim(claim):
    if not isinstance(claim, dict):
        return None
    category = (claim.get("category") or "").strip()
    source = (claim.get("source") or "").strip()
    excerpt = (claim.get("excerpt") or "").strip()
    text = (claim.get("text") or "").strip()
    locator = (claim.get("locator") or "").strip()[:80]
    if category not in CATEGORY_LABELS or source not in SOURCE_LABELS:
        return None
    if not text or not excerpt:
        return None
    return {
        "category": category,
        "source": source,
        "excerpt": excerpt,
        "text": text,
        "locator": locator,
    }


def verify_payload(payload, sources_by_kind):
    """Return verified claims (at most two per category), dropped claims, and the against-argument."""
    verified = []
    unverified = []
    per_category = {key: 0 for key in CATEGORY_LABELS}
    for raw in payload.get("claims") or []:
        claim = _clean_claim(raw)
        if claim is None:
            text = ""
            if isinstance(raw, dict):
                text = (raw.get("text") or "").strip()
            if text:
                unverified.append(
                    {
                        "text": text,
                        "source": (raw.get("source") or "").strip(),
                        "excerpt": (raw.get("excerpt") or "").strip(),
                    }
                )
            continue
        if per_category[claim["category"]] >= 2:
            continue
        source = sources_by_kind.get(claim["source"])
        body = source.body if source is not None else ""
        if not excerpt_in_source(claim["excerpt"], body):
            unverified.append(
                {
                    "text": claim["text"],
                    "source": claim["source"],
                    "excerpt": claim["excerpt"],
                }
            )
            continue
        per_category[claim["category"]] += 1
        verified.append(claim)

    against = payload.get("strongest_against") or {}
    against_ok = False
    against_clean = {
        "text": "",
        "source": "",
        "excerpt": "",
        "locator": "",
    }
    if isinstance(against, dict):
        source_kind = (against.get("source") or "").strip()
        excerpt = (against.get("excerpt") or "").strip()
        text = (against.get("text") or "").strip()
        locator = (against.get("locator") or "").strip()[:80]
        source = sources_by_kind.get(source_kind)
        body = source.body if source is not None else ""
        if (
            text
            and source_kind in SOURCE_LABELS
            and excerpt_in_source(excerpt, body)
        ):
            against_ok = True
            against_clean = {
                "text": text,
                "source": source_kind,
                "excerpt": excerpt,
                "locator": locator,
            }
    return verified, unverified, against_clean, against_ok
