"""Assemble a deal's score, flags, and benchmark comparison."""

from dataclasses import dataclass

from evaluations.flags import collect_flags, worst_flag
from evaluations.formatting import format_usd
from evaluations.scoring import band_position, floor_position, score_factors


@dataclass
class BenchmarkRow:
    label: str
    value_display: str
    band_display: str
    position: str
    position_label: str


@dataclass
class SnapshotItem:
    label: str
    value: str


@dataclass
class Report:
    deal: object
    evaluation: object
    flags: list
    worst_flag: object
    benchmark_rows: list
    benchmark_missing: bool
    snapshot: list


def _range_row(label, value, low, high):
    position = band_position(value, low, high)
    labels = {
        "below": "Below the band",
        "in_band": "Inside the band",
        "above": "Above the band",
    }
    if value is None:
        position_label = "Not entered"
        position = ""
    else:
        position_label = labels.get(position, "")
    return BenchmarkRow(
        label=label,
        value_display=format_usd(value),
        band_display=f"{format_usd(low)}–{format_usd(high)}",
        position=position or "",
        position_label=position_label,
    )


def benchmark_rows(deal, benchmark):
    market = getattr(deal, "market_profile", None)
    traction = getattr(deal, "traction_profile", None)
    tam = market.tam_usd if market is not None else None
    arr = traction.arr_usd if traction is not None else None
    tam_position = floor_position(tam, benchmark.tam_floor_usd)
    if tam is None:
        tam_label = "Not entered"
        tam_position = ""
    elif tam_position == "below":
        tam_label = "Below the venture-scale floor"
    else:
        tam_label = "Meets the venture-scale floor"
    return [
        BenchmarkRow(
            label="TAM",
            value_display=format_usd(tam),
            band_display=f"Floor {format_usd(benchmark.tam_floor_usd)}",
            position=tam_position or "",
            position_label=tam_label,
        ),
        _range_row(
            "Valuation or cap",
            deal.valuation_usd,
            benchmark.pre_money_low_usd,
            benchmark.pre_money_high_usd,
        ),
        _range_row(
            "Round size",
            deal.raise_amount_usd,
            benchmark.round_size_low_usd,
            benchmark.round_size_high_usd,
        ),
        _range_row(
            "ARR",
            arr,
            benchmark.arr_low_usd,
            benchmark.arr_high_usd,
        ),
    ]


def build_snapshot(deal):
    items = []
    founders = list(deal.founders.all())
    if founders:
        items.append(SnapshotItem("Founders", ", ".join(founder.name for founder in founders)))
    product = getattr(deal, "product_profile", None)
    if product is not None and product.product_stage:
        items.append(SnapshotItem("Product", product.get_product_stage_display()))
    market = getattr(deal, "market_profile", None)
    if market is not None and market.tam_usd is not None:
        items.append(SnapshotItem("TAM", format_usd(market.tam_usd)))
    if deal.raise_amount_usd is not None:
        items.append(SnapshotItem("Raising", format_usd(deal.raise_amount_usd)))
    if deal.valuation_usd is not None:
        items.append(SnapshotItem("Valuation or cap", format_usd(deal.valuation_usd)))
    if deal.lead_status:
        items.append(SnapshotItem("Lead", deal.get_lead_status_display()))
    return items


def build_report(deal, weights, benchmark):
    scores = {row.factor_key: row.score for row in deal.scores.all()}
    evaluation = score_factors(scores, weights)
    flags = collect_flags(deal, benchmark)
    return Report(
        deal=deal,
        evaluation=evaluation,
        flags=flags,
        worst_flag=worst_flag(flags),
        benchmark_rows=benchmark_rows(deal, benchmark) if benchmark is not None else [],
        benchmark_missing=benchmark is None,
        snapshot=build_snapshot(deal),
    )
