"""Weighted scorecard math.

A finished category contributes (its average / 5) times its weight.
Until every factor in the scorecard is scored, unscored factors count as zero
and the composite stays partial. The screen label is withheld until then.
"""

from dataclasses import dataclass

from evaluations.constants import (
    CATEGORIES,
    FACTORS,
    SCREEN_DEEPER,
    SCREEN_MIXED,
    SCREEN_PASS,
    SCREEN_STRONG,
)
from evaluations.formatting import format_score


@dataclass
class FactorView:
    key: str
    label: str
    score: int | None

    @property
    def score_display(self):
        if self.score is None:
            return "—"
        return str(self.score)


@dataclass
class CategoryView:
    key: str
    label: str
    weight: int
    factors: list
    running_average: float | None
    points: float
    scored_count: int

    @property
    def factor_count(self):
        return len(self.factors)

    @property
    def complete(self):
        return self.factor_count > 0 and self.scored_count == self.factor_count

    @property
    def bar_percent(self):
        if self.weight <= 0:
            return 0
        return round(self.points / self.weight * 100)

    @property
    def running_display(self):
        if self.running_average is None:
            return "—"
        return f"{format_score(self.running_average)} / 5"

    @property
    def points_display(self):
        return format_score(self.points) or "0"

    @property
    def progress_label(self):
        points = self.points_display
        if self.scored_count == 0:
            return "Not scored"
        if self.complete:
            return f"In the composite · {points} of {self.weight} points"
        return (
            f"{self.scored_count} of {self.factor_count} factors · "
            f"{points} of {self.weight} points in the composite"
        )


@dataclass
class Evaluation:
    categories: list
    composite: float | None
    complete: bool
    scored_count: int
    factor_count: int
    screen_label: str
    screen_slug: str

    @property
    def composite_display(self):
        if self.composite is None:
            return ""
        return format_score(self.composite) or ""

    @property
    def partial(self):
        return self.composite is not None and not self.complete


def screen_label_for(score):
    if score >= 75:
        return SCREEN_STRONG
    if score >= 60:
        return SCREEN_DEEPER
    if score >= 45:
        return SCREEN_MIXED
    return SCREEN_PASS


def screen_slug_for(label):
    return {
        SCREEN_STRONG: "strong",
        SCREEN_DEEPER: "deeper",
        SCREEN_MIXED: "mixed",
        SCREEN_PASS: "pass",
    }.get(label, "")


def band_position(value, low, high):
    if value is None or low is None or high is None:
        return None
    if value < low:
        return "below"
    if value > high:
        return "above"
    return "in_band"


def floor_position(value, floor):
    if value is None or floor is None:
        return None
    if value < floor:
        return "below"
    return "in_band"


def _category_points(scores, weight):
    count = len(scores)
    if count == 0 or weight <= 0:
        return 0.0
    entered = sum(score for score in scores if score is not None)
    return (entered / (5 * count)) * weight


def score_factors(scores_by_key, weights):
    categories = []
    scored_count = 0
    factor_count = 0
    for key, label, _default_weight in CATEGORIES:
        factor_defs = FACTORS[key]
        factor_views = []
        raw_scores = []
        for factor_key, factor_label in factor_defs:
            score = scores_by_key.get(factor_key)
            if score is not None:
                scored_count += 1
            raw_scores.append(score)
            factor_views.append(
                FactorView(key=factor_key, label=factor_label, score=score)
            )
        entered = [score for score in raw_scores if score is not None]
        running = sum(entered) / len(entered) if entered else None
        weight = int(weights.get(key, 0))
        categories.append(
            CategoryView(
                key=key,
                label=label,
                weight=weight,
                factors=factor_views,
                running_average=running,
                points=_category_points(raw_scores, weight),
                scored_count=len(entered),
            )
        )
        factor_count += len(factor_defs)

    if scored_count == 0:
        composite = None
    else:
        composite = sum(category.points for category in categories)

    complete = factor_count > 0 and scored_count == factor_count
    label = ""
    slug = ""
    if complete and composite is not None:
        shown = round(composite, 1)
        label = screen_label_for(shown)
        slug = screen_slug_for(label)

    return Evaluation(
        categories=categories,
        composite=composite,
        complete=complete,
        scored_count=scored_count,
        factor_count=factor_count,
        screen_label=label,
        screen_slug=slug,
    )
