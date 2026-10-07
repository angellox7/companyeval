"""Shape a stored assessment into the one-page partner memo."""

from evaluations.constants import CATEGORIES
from evaluations.models import Assessment


def memo_sections(deal, report):
    assessment = (
        Assessment.objects.filter(deal=deal).prefetch_related("claims").first()
    )
    if assessment is None:
        return None
    grouped = {key: [] for key, _label, _weight in CATEGORIES}
    for claim in assessment.claims.all():
        grouped.setdefault(claim.category, []).append(claim)

    sections = []
    footnotes = []
    number = 1
    categories = {category.key: category for category in report.evaluation.categories}
    for key, label, _weight in CATEGORIES:
        category = categories.get(key)
        claims = []
        for claim in grouped.get(key, []):
            footnotes.append(
                {
                    "number": number,
                    "citation": claim.citation,
                    "excerpt": claim.excerpt,
                }
            )
            claims.append({"number": number, "claim": claim})
            number += 1
        sections.append(
            {
                "key": key,
                "label": label,
                "running_display": category.running_display if category else "—",
                "progress_label": category.progress_label if category else "Not scored",
                "claims": claims,
            }
        )
    against_number = None
    if assessment.against_verified:
        against_number = number
        footnotes.append(
            {
                "number": against_number,
                "citation": assessment.against_citation,
                "excerpt": assessment.against_excerpt,
            }
        )
    return {
        "assessment": assessment,
        "sections": sections,
        "footnotes": footnotes,
        "against_number": against_number,
    }
