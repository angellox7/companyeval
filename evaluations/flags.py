"""Fact and score flags. Computed on read, not stored."""

from dataclasses import dataclass

from evaluations.constants import (
    CATEGORIES,
    DEEP_TECH_SECTOR,
    EARLY_PRODUCT_STAGES,
    FACTORS,
)
from evaluations.formatting import format_usd


@dataclass(frozen=True)
class Flag:
    severity: str
    code: str
    message: str
    category: str = ""

    @property
    def severity_label(self):
        if self.severity == "high":
            return "High"
        return "Watch"


def worst_flag(flags):
    for flag in flags:
        if flag.severity == "high":
            return flag
    if flags:
        return flags[0]
    return None


def _profile(deal, name):
    return getattr(deal, name, None)


def _scores(deal):
    return {row.factor_key: row.score for row in deal.scores.all()}


def collect_flags(deal, benchmark):
    flags = []
    scores = _scores(deal)

    for category_key, category_label, _weight in CATEGORIES:
        factor_defs = FACTORS[category_key]
        values = []
        for factor_key, factor_label in factor_defs:
            score = scores.get(factor_key)
            values.append(score)
            if score == 1:
                flags.append(
                    Flag(
                        severity="high",
                        code="factor_low",
                        message=f"{factor_label} is scored 1.",
                        category=category_key,
                    )
                )
        if all(value is not None for value in values):
            average = sum(values) / len(values)
            if average <= 2:
                flags.append(
                    Flag(
                        severity="high",
                        code="category_high",
                        message=f"{category_label} averages {average:.1f}, at or below 2.",
                        category=category_key,
                    )
                )
            elif average < 3:
                flags.append(
                    Flag(
                        severity="watch",
                        code="category_watch",
                        message=(
                            f"{category_label} averages {average:.1f}, "
                            "below the typical seed bar of 3."
                        ),
                        category=category_key,
                    )
                )

    market = _profile(deal, "market_profile")
    if benchmark is not None and market is not None and market.tam_usd is not None:
        if market.tam_usd < benchmark.tam_floor_usd:
            flags.append(
                Flag(
                    severity="high",
                    code="tam_below_floor",
                    message=(
                        f"TAM is below the venture-scale floor for "
                        f"{benchmark.get_sector_display()} "
                        f"({format_usd(benchmark.tam_floor_usd)})."
                    ),
                    category="market",
                )
            )

    if benchmark is not None and deal.valuation_usd is not None:
        if deal.valuation_usd > benchmark.pre_money_high_usd:
            flags.append(
                Flag(
                    severity="high",
                    code="valuation_above_band",
                    message=(
                        f"Valuation is above the typical seed band for "
                        f"{benchmark.get_sector_display()} "
                        f"({format_usd(benchmark.pre_money_low_usd)}–"
                        f"{format_usd(benchmark.pre_money_high_usd)})."
                    ),
                    category="terms",
                )
            )

    product = _profile(deal, "product_profile")
    traction = _profile(deal, "traction_profile")
    if product is not None and product.product_stage in EARLY_PRODUCT_STAGES:
        lois = pilots = waitlist = 0
        if traction is not None:
            lois = traction.lois or 0
            pilots = traction.pilots or 0
            waitlist = traction.waitlist or 0
        if lois == 0 and pilots == 0 and waitlist == 0:
            flags.append(
                Flag(
                    severity="high",
                    code="no_validation",
                    message=(
                        "The product is still an idea or a deck, with no LOIs, "
                        "pilots, or waitlist."
                    ),
                    category="traction",
                )
            )

    founders = list(deal.founders.all())
    if (
        deal.sector == DEEP_TECH_SECTOR
        and founders
        and not any(founder.is_technical for founder in founders)
    ):
        flags.append(
            Flag(
                severity="high",
                code="no_technical_founder",
                message="No founder is marked technical in a deep tech company.",
                category="team",
            )
        )

    team = _profile(deal, "team_profile")
    if team is not None and team.years_known is not None and team.years_known < 1:
        flags.append(
            Flag(
                severity="high",
                code="short_founder_history",
                message="Co-founders have known each other for less than a year.",
                category="team",
            )
        )
    if team is not None and team.vesting_in_place is False:
        flags.append(
            Flag(
                severity="high",
                code="no_vesting",
                message="Vesting is not in place.",
                category="team",
            )
        )

    if deal.lead_status == "no_lead":
        flags.append(
            Flag(
                severity="high",
                code="no_lead",
                message="The round has no lead.",
                category="terms",
            )
        )

    if product is not None and product.moat_types and "none" in product.moat_types:
        flags.append(
            Flag(
                severity="high",
                code="no_moat",
                message="No moat is identified.",
                category="product",
            )
        )

    if (
        product is not None
        and product.product_stage in EARLY_PRODUCT_STAGES
        and traction is not None
        and traction.monthly_burn_usd
    ):
        flags.append(
            Flag(
                severity="high",
                code="burn_before_product",
                message=(
                    "The company is burning capital while the product is still "
                    "an idea or a deck."
                ),
                category="traction",
            )
        )

    flags.sort(key=lambda flag: (0 if flag.severity == "high" else 1, flag.code, flag.message))
    return flags
