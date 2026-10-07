"""Shared choices, factor definitions, and working benchmark defaults."""

MAX_DECK_BYTES = 20 * 1024 * 1024

SECTORS = [
    ("b2b_saas", "B2B SaaS"),
    ("marketplace", "Marketplace"),
    ("consumer", "Consumer"),
    ("fintech", "Fintech"),
    ("healthtech", "Healthtech"),
    ("deep_tech", "Deep tech"),
    ("climate", "Climate"),
    ("other", "Other"),
]

DEAL_STATUSES = [
    ("researching", "Researching"),
    ("in_diligence", "In diligence"),
    ("passed", "Passed"),
    ("investing", "Investing"),
]

ROUND_TYPES = [
    ("safe", "SAFE"),
    ("convertible", "Convertible note"),
    ("priced", "Priced round"),
]

LEAD_STATUSES = [
    ("no_lead", "No lead"),
    ("lead_soft", "Lead soft-circled"),
    ("lead_committed", "Lead committed"),
]

SKILL_SPLITS = [
    ("balanced", "Balanced technical and commercial"),
    ("technical_heavy", "Technical-heavy"),
    ("commercial_heavy", "Commercial-heavy"),
    ("unclear", "Unclear"),
]

EQUITY_HEALTH = [
    ("healthy", "Healthy"),
    ("concern", "Concern"),
    ("unknown", "Unknown"),
]

MARKET_STRUCTURES = [
    ("winner_take_most", "Winner-take-most"),
    ("room_for_several", "Room for several players"),
    ("unclear", "Unclear"),
]

VALUE_PROPS = [
    ("must_have", "Must-have"),
    ("strong", "Strong"),
    ("nice_to_have", "Nice-to-have"),
    ("unclear", "Unclear"),
]

PRODUCT_STAGES = [
    ("idea", "Idea"),
    ("deck_only", "Deck only"),
    ("private_beta", "Private beta"),
    ("mvp_live", "Live MVP"),
    ("revenue_live", "Live with revenue"),
]

MOAT_TYPES = [
    ("proprietary_tech", "Proprietary tech"),
    ("data_loop", "Data loop"),
    ("network_effects", "Network effects"),
    ("switching_costs", "Switching costs"),
    ("regulatory", "Regulatory"),
    ("none", "None"),
]

EARLY_PRODUCT_STAGES = ("idea", "deck_only")
DEEP_TECH_SECTOR = "deep_tech"

# (key, label, default weight). Weights are percents and must sum to 100.
CATEGORIES = [
    ("team", "Team", 30),
    ("market", "Market", 25),
    ("product", "Product", 20),
    ("traction", "Traction", 15),
    ("terms", "Deal terms", 10),
]

FACTORS = {
    "team": [
        ("domain_expertise", "Domain expertise"),
        ("resilience", "Resilience and grit"),
        ("founder_dynamics", "Founder dynamics"),
    ],
    "market": [
        ("tam_growth", "Venture-scale TAM and growth"),
        ("entrant_room", "Room for a new entrant"),
        ("why_now", "Why now"),
    ],
    "product": [
        ("value_prop", "Must-have versus nice-to-have"),
        ("product_stage", "Product stage"),
        ("moat", "Moat"),
    ],
    "traction": [
        ("engagement", "Engagement and retention"),
        ("revenue_pipeline", "Revenue or pipeline"),
        ("capital_efficiency", "Capital efficiency"),
    ],
    "terms": [
        ("valuation", "Valuation versus the sector band"),
        ("round_construction", "Round construction"),
    ],
}

FACTOR_CHOICES = [
    (key, label)
    for factors in FACTORS.values()
    for key, label in factors
]

FACTOR_LABELS = dict(FACTOR_CHOICES)

FACTOR_CATEGORY = {
    factor_key: category
    for category, factors in FACTORS.items()
    for factor_key, _label in factors
}

CATEGORY_LABELS = {key: label for key, label, _weight in CATEGORIES}

EVALUATION_MODES = [
    ("ai", "AI-assisted"),
    ("manual", "Manual"),
]

SOURCE_KINDS = [
    ("deck", "Deck"),
    ("website", "Website"),
    ("founder_bios", "Founder bios"),
    ("call_notes", "First-call notes"),
]

SOURCE_LABELS = dict(SOURCE_KINDS)

DEFAULT_WEIGHTS = {key: weight for key, _label, weight in CATEGORIES}

WORKING_DEFAULT_NOTE = (
    "Working default for a first screen, not a live market feed. "
    "Edit this row to match the bar you actually use."
)


def _benchmark(
    sector,
    tam_floor,
    pre_low,
    pre_high,
    round_low,
    round_high,
    arr_low,
    arr_high,
):
    return {
        "sector": sector,
        "tam_floor_usd": tam_floor,
        "pre_money_low_usd": pre_low,
        "pre_money_high_usd": pre_high,
        "round_size_low_usd": round_low,
        "round_size_high_usd": round_high,
        "arr_low_usd": arr_low,
        "arr_high_usd": arr_high,
        "notes": WORKING_DEFAULT_NOTE,
    }


# Illustrative seed bands in US dollars. The benchmarks page is where these live
# after install; change them there rather than treating this list as market data.
DEFAULT_BENCHMARKS = [
    _benchmark("b2b_saas", 1_000_000_000, 8_000_000, 15_000_000, 2_000_000, 4_000_000, 0, 500_000),
    _benchmark("marketplace", 1_000_000_000, 8_000_000, 16_000_000, 2_000_000, 5_000_000, 0, 1_000_000),
    _benchmark("consumer", 1_000_000_000, 6_000_000, 12_000_000, 1_500_000, 4_000_000, 0, 500_000),
    _benchmark("fintech", 1_000_000_000, 8_000_000, 18_000_000, 2_000_000, 5_000_000, 0, 750_000),
    _benchmark("healthtech", 1_000_000_000, 8_000_000, 16_000_000, 2_000_000, 5_000_000, 0, 500_000),
    _benchmark("deep_tech", 1_000_000_000, 10_000_000, 20_000_000, 2_000_000, 6_000_000, 0, 250_000),
    _benchmark("climate", 1_000_000_000, 8_000_000, 16_000_000, 2_000_000, 5_000_000, 0, 500_000),
    _benchmark("other", 1_000_000_000, 6_000_000, 15_000_000, 1_500_000, 4_000_000, 0, 500_000),
]

SCREEN_STRONG = "Strong pursue"
SCREEN_DEEPER = "Worth a deeper look"
SCREEN_MIXED = "Mixed"
SCREEN_PASS = "Lean pass"

SECTION_URL_NAMES = {
    "team": "evaluations:team_section",
    "market": "evaluations:market_section",
    "product": "evaluations:product_section",
    "traction": "evaluations:traction_section",
    "terms": "evaluations:terms_section",
}
