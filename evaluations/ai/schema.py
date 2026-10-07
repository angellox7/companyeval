"""JSON schema for the partner assessment. Strict mode requires every key."""

from evaluations.constants import (
    EQUITY_HEALTH,
    FACTOR_CHOICES,
    LEAD_STATUSES,
    MARKET_STRUCTURES,
    MOAT_TYPES,
    PRODUCT_STAGES,
    ROUND_TYPES,
    SKILL_SPLITS,
    SOURCE_KINDS,
    VALUE_PROPS,
    CATEGORIES,
)


def _enum(pairs):
    return [key for key, _label in pairs]


def _nullable_enum(pairs):
    return {
        "anyOf": [
            {"type": "string", "enum": _enum(pairs)},
            {"type": "null"},
        ]
    }


def _nullable_string():
    return {"type": ["string", "null"]}


def _nullable_int():
    return {"type": ["integer", "null"]}


def _nullable_number():
    return {"type": ["number", "null"]}


def _nullable_bool():
    return {"type": ["boolean", "null"]}


def _object(properties):
    return {
        "type": "object",
        "properties": properties,
        "required": list(properties),
        "additionalProperties": False,
    }


_CLAIM = _object(
    {
        "category": {"type": "string", "enum": [key for key, _label, _weight in CATEGORIES]},
        "text": {"type": "string"},
        "source": {"type": "string", "enum": _enum(SOURCE_KINDS)},
        "excerpt": {"type": "string"},
        "locator": {"type": "string"},
    }
)

_AGAINST = _object(
    {
        "text": {"type": "string"},
        "source": {"type": "string", "enum": _enum(SOURCE_KINDS)},
        "excerpt": {"type": "string"},
        "locator": {"type": "string"},
    }
)

ASSESSMENT_SCHEMA = _object(
    {
        "one_liner": _nullable_string(),
        "location": _nullable_string(),
        "year_founded": _nullable_int(),
        "founders": {
            "type": "array",
            "items": _object(
                {
                    "name": {"type": "string"},
                    "role": _nullable_string(),
                    "is_technical": _nullable_bool(),
                    "years_in_domain": _nullable_number(),
                    "full_time": _nullable_bool(),
                }
            ),
        },
        "team": _object(
            {
                "years_known": _nullable_number(),
                "skill_split": _nullable_enum(SKILL_SPLITS),
                "vesting_in_place": _nullable_bool(),
                "equity_health": _nullable_enum(EQUITY_HEALTH),
            }
        ),
        "market": _object(
            {
                "tam_usd": _nullable_int(),
                "sam_usd": _nullable_int(),
                "som_usd": _nullable_int(),
                "market_growing": _nullable_bool(),
                "structure": _nullable_enum(MARKET_STRUCTURES),
                "why_now": _nullable_string(),
                "macro_trends": _nullable_string(),
            }
        ),
        "product": _object(
            {
                "value_prop": _nullable_enum(VALUE_PROPS),
                "product_stage": _nullable_enum(PRODUCT_STAGES),
                "moat_types": {
                    "type": "array",
                    "items": {"type": "string", "enum": _enum(MOAT_TYPES)},
                },
                "moat_notes": _nullable_string(),
            }
        ),
        "traction": _object(
            {
                "wau": _nullable_int(),
                "mau": _nullable_int(),
                "retention_note": _nullable_string(),
                "arr_usd": _nullable_int(),
                "lois": _nullable_int(),
                "pilots": _nullable_int(),
                "waitlist": _nullable_int(),
                "monthly_burn_usd": _nullable_int(),
                "capital_raised_usd": _nullable_int(),
                "milestones_note": _nullable_string(),
            }
        ),
        "terms": _object(
            {
                "round_type": _nullable_enum(ROUND_TYPES),
                "raise_amount_usd": _nullable_int(),
                "valuation_usd": _nullable_int(),
                "lead_status": _nullable_enum(LEAD_STATUSES),
                "committed_percent": _nullable_int(),
            }
        ),
        "scores": {
            "type": "array",
            "items": _object(
                {
                    "factor_key": {"type": "string", "enum": [key for key, _label in FACTOR_CHOICES]},
                    "score": {"type": "integer"},
                    "note": {"type": "string"},
                }
            ),
        },
        "claims": {"type": "array", "items": _CLAIM},
        "strongest_against": _AGAINST,
    }
)


DECK_PAGES_SCHEMA = _object(
    {
        "pages": {
            "type": "array",
            "items": _object(
                {
                    "page": {"type": "integer"},
                    "text": {"type": "string"},
                }
            ),
        },
    }
)
