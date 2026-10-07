"""OpenAI structured output for a seed assessment. Import the SDK only when generating."""

import os

from django.conf import settings

from evaluations.ai.schema import ASSESSMENT_SCHEMA, DECK_PAGES_SCHEMA
from evaluations.constants import CATEGORIES, FACTORS
from evaluations.formatting import format_usd

MAX_SOURCE_CHARS = 20_000

DECK_READ_PROMPT = """Copy the words visible on each page of this pitch deck.
Include words inside charts, tables, and screenshots.
Do not summarize, interpret, or score.
Return one entry per page, in order. page is the page number. text is the words on that page.
If a page has no words, use an empty string for its text.
"""

SYSTEM_PROMPT = """You are a seed-stage investment analyst writing for fund partners.
Use only the source texts in the user message. Do not use outside knowledge.
When a figure or fact is not in those sources, leave it null or use an empty string.
Score each factor from 1 to 5. 3 means a typical seed company in this sector. 1 is well below that bar. 5 is exceptional.
Benchmark bands are context for the valuation score only. Do not cite them as a source.
Every claim must quote a verbatim excerpt copied from the cited source. The excerpt must appear in that source, not a paraphrase.
Write at most two claims for each category.
The strongest argument against investing is required. It must also quote a verbatim excerpt.
If the objection is missing evidence, quote what the source does say and state what that passage fails to show.
source is one of: deck, website, founder_bios, call_notes.
For a deck, set locator to the page marker such as "p. 3" when the excerpt comes from that page. Otherwise leave locator as an empty string.
"""


def _clip(text):
    text = text or ""
    if len(text) <= MAX_SOURCE_CHARS:
        return text
    return text[:MAX_SOURCE_CHARS] + "\n\n[Source text shortened for the prompt.]"


def _factor_lines():
    lines = []
    for key, label, _weight in CATEGORIES:
        names = ", ".join(f"{factor_key} ({factor_label})" for factor_key, factor_label in FACTORS[key])
        lines.append(f"{label} ({key}): {names}")
    return "\n".join(lines)


def _benchmark_lines(benchmark):
    if benchmark is None:
        return "No sector benchmark is saved."
    return (
        f"TAM floor {format_usd(benchmark.tam_floor_usd)}. "
        f"Pre-money or cap {format_usd(benchmark.pre_money_low_usd)} to {format_usd(benchmark.pre_money_high_usd)}. "
        f"Round size {format_usd(benchmark.round_size_low_usd)} to {format_usd(benchmark.round_size_high_usd)}. "
        f"ARR {format_usd(benchmark.arr_low_usd)} to {format_usd(benchmark.arr_high_usd)}. "
        "Use these only to judge the valuation score. Do not cite them as a source."
    )


def build_user_prompt(deal, sources, benchmark):
    blocks = [
        f"Company: {deal.company_name}",
        f"Sector: {deal.get_sector_display()}",
        f"Website URL: {deal.website or 'not provided'}",
        "",
        "Factors to score:",
        _factor_lines(),
        "",
        "Sector benchmark context:",
        _benchmark_lines(benchmark),
        "",
        "Sources:",
    ]
    for kind, document in sources.items():
        blocks.append(f"\n--- {kind} ---\n{_clip(document.body)}")
    return "\n".join(blocks)


def format_deck_pages(pages):
    if not isinstance(pages, list):
        return ""
    chunks = []
    for page in pages:
        if not isinstance(page, dict):
            continue
        number = page.get("page")
        if isinstance(number, bool) or not isinstance(number, int) or number < 1:
            continue
        text = str(page.get("text") or "").strip()
        chunks.append(f"[Page {number}]\n{text}")
    return "\n\n".join(chunks).strip()


def transcribe_deck(filename, pdf_bytes):
    import base64
    import json

    from openai import OpenAI

    name = os.path.basename(filename or "") or "deck.pdf"
    encoded = base64.b64encode(pdf_bytes).decode("ascii")
    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=120)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": DECK_READ_PROMPT},
                    {
                        "type": "file",
                        "file": {
                            "filename": name,
                            "file_data": f"data:application/pdf;base64,{encoded}",
                        },
                    },
                ],
            }
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "deck_pages",
                "strict": True,
                "schema": DECK_PAGES_SCHEMA,
            },
        },
    )
    content = response.choices[0].message.content or ""
    payload = json.loads(content)
    pages = payload.get("pages") if isinstance(payload, dict) else None
    return format_deck_pages(pages)


def request_assessment(deal, sources, benchmark):
    from openai import OpenAI

    client = OpenAI(api_key=settings.OPENAI_API_KEY, timeout=90)
    response = client.chat.completions.create(
        model=settings.OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": build_user_prompt(deal, sources, benchmark)},
        ],
        response_format={
            "type": "json_schema",
            "json_schema": {
                "name": "seed_assessment",
                "strict": True,
                "schema": ASSESSMENT_SCHEMA,
            },
        },
    )
    content = response.choices[0].message.content or ""
    import json

    return json.loads(content)
