"""Write a verified model payload onto the existing scorecard and assessment."""

from datetime import date
from decimal import Decimal, InvalidOperation

from django.db import transaction

from evaluations.ai.verify import verify_payload
from evaluations.constants import (
    EQUITY_HEALTH,
    FACTOR_CATEGORY,
    LEAD_STATUSES,
    MARKET_STRUCTURES,
    MOAT_TYPES,
    PRODUCT_STAGES,
    ROUND_TYPES,
    SKILL_SPLITS,
    VALUE_PROPS,
)
from evaluations.models import (
    Assessment,
    Claim,
    FactorScore,
    Founder,
    MarketProfile,
    ProductProfile,
    TeamProfile,
    TractionProfile,
)


def _choice(value, pairs):
    allowed = {key for key, _label in pairs}
    if value in allowed:
        return value
    return ""


def _text(value, limit=None):
    if value is None:
        return ""
    text = str(value).strip()
    if limit is not None:
        return text[:limit]
    return text


def _money(value):
    if value is None or value is False:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < 0:
        return None
    return number


def _count(value):
    number = _money(value)
    return number


def _decimal(value):
    if value is None or value == "":
        return None
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None
    if number < 0 or number > 99:
        return None
    return number.quantize(Decimal("0.1"))


def _bool(value):
    if value is True or value is False:
        return value
    return None


def _year(value):
    number = _money(value)
    if number is None or number < 1900 or number > date.today().year:
        return None
    return number


def _percent(value):
    number = _money(value)
    if number is None or number > 100:
        return None
    return number


def _score(value):
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if 1 <= number <= 5:
        return number
    return None


def _apply_facts(deal, payload):
    deal.one_liner = _text(payload.get("one_liner"), 300)
    deal.location = _text(payload.get("location"), 200)
    deal.year_founded = _year(payload.get("year_founded"))

    terms = payload.get("terms") or {}
    deal.round_type = _choice(terms.get("round_type"), ROUND_TYPES)
    deal.raise_amount_usd = _money(terms.get("raise_amount_usd"))
    deal.valuation_usd = _money(terms.get("valuation_usd"))
    deal.lead_status = _choice(terms.get("lead_status"), LEAD_STATUSES)
    deal.committed_percent = _percent(terms.get("committed_percent"))
    deal.save()

    team_data = payload.get("team") or {}
    team, _created = TeamProfile.objects.get_or_create(deal=deal)
    team.years_known = _decimal(team_data.get("years_known"))
    team.skill_split = _choice(team_data.get("skill_split"), SKILL_SPLITS)
    team.vesting_in_place = _bool(team_data.get("vesting_in_place"))
    team.equity_health = _choice(team_data.get("equity_health"), EQUITY_HEALTH)
    team.save()

    market_data = payload.get("market") or {}
    market, _created = MarketProfile.objects.get_or_create(deal=deal)
    market.tam_usd = _money(market_data.get("tam_usd"))
    market.sam_usd = _money(market_data.get("sam_usd"))
    market.som_usd = _money(market_data.get("som_usd"))
    market.market_growing = _bool(market_data.get("market_growing"))
    market.structure = _choice(market_data.get("structure"), MARKET_STRUCTURES)
    market.why_now = _text(market_data.get("why_now"))
    market.macro_trends = _text(market_data.get("macro_trends"))
    market.save()

    product_data = payload.get("product") or {}
    product, _created = ProductProfile.objects.get_or_create(deal=deal)
    product.value_prop = _choice(product_data.get("value_prop"), VALUE_PROPS)
    product.product_stage = _choice(product_data.get("product_stage"), PRODUCT_STAGES)
    allowed_moats = {key for key, _label in MOAT_TYPES}
    moats = [item for item in (product_data.get("moat_types") or []) if item in allowed_moats]
    if "none" in moats:
        moats = ["none"]
    product.moat_types = moats
    product.moat_notes = _text(product_data.get("moat_notes"))
    product.save()

    traction_data = payload.get("traction") or {}
    traction, _created = TractionProfile.objects.get_or_create(deal=deal)
    traction.wau = _count(traction_data.get("wau"))
    traction.mau = _count(traction_data.get("mau"))
    traction.retention_note = _text(traction_data.get("retention_note"))
    traction.arr_usd = _money(traction_data.get("arr_usd"))
    traction.lois = _count(traction_data.get("lois"))
    traction.pilots = _count(traction_data.get("pilots"))
    traction.waitlist = _count(traction_data.get("waitlist"))
    traction.monthly_burn_usd = _money(traction_data.get("monthly_burn_usd"))
    traction.capital_raised_usd = _money(traction_data.get("capital_raised_usd"))
    traction.milestones_note = _text(traction_data.get("milestones_note"))
    traction.save()

    deal.founders.all().delete()
    for founder in payload.get("founders") or []:
        if not isinstance(founder, dict):
            continue
        name = _text(founder.get("name"), 200)
        if not name:
            continue
        Founder.objects.create(
            deal=deal,
            name=name,
            role=_text(founder.get("role"), 200),
            is_technical=bool(founder.get("is_technical")),
            years_in_domain=_decimal(founder.get("years_in_domain")),
            full_time=bool(founder.get("full_time")),
        )


def _apply_scores(deal, payload, verified_categories):
    deal.scores.all().delete()
    seen = set()
    for row in payload.get("scores") or []:
        if not isinstance(row, dict):
            continue
        factor_key = row.get("factor_key")
        category = FACTOR_CATEGORY.get(factor_key)
        score = _score(row.get("score"))
        if category not in verified_categories or score is None or factor_key in seen:
            continue
        seen.add(factor_key)
        FactorScore.objects.create(
            deal=deal,
            factor_key=factor_key,
            score=score,
            note=_text(row.get("note")),
        )


@transaction.atomic
def apply_assessment(deal, payload, sources_by_kind, model_name):
    verified, unverified, against, against_ok = verify_payload(payload, sources_by_kind)
    verified_categories = {claim["category"] for claim in verified}
    _apply_facts(deal, payload)
    _apply_scores(deal, payload, verified_categories)
    Assessment.objects.filter(deal=deal).delete()
    assessment = Assessment.objects.create(
        deal=deal,
        model_name=model_name or "",
        against_text=against["text"] if against_ok else "",
        against_source=against["source"] if against_ok else "",
        against_excerpt=against["excerpt"] if against_ok else "",
        against_locator=against["locator"] if against_ok else "",
        against_verified=against_ok,
        unverified=unverified,
    )
    for position, claim in enumerate(verified):
        Claim.objects.create(
            assessment=assessment,
            category=claim["category"],
            body=claim["text"],
            source_kind=claim["source"],
            excerpt=claim["excerpt"],
            locator=claim["locator"],
            position=position,
        )
    return assessment
