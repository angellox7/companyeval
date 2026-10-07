from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Case, When

from evaluations.constants import (
    DEAL_STATUSES,
    DEFAULT_WEIGHTS,
    EQUITY_HEALTH,
    EVALUATION_MODES,
    FACTOR_CHOICES,
    LEAD_STATUSES,
    MARKET_STRUCTURES,
    MOAT_TYPES,
    PRODUCT_STAGES,
    ROUND_TYPES,
    SECTORS,
    SKILL_SPLITS,
    SOURCE_KINDS,
    SOURCE_LABELS,
    VALUE_PROPS,
)
from evaluations.validators import validate_pdf


def _non_negative():
    return [MinValueValidator(0)]


class SectorBenchmarkQuerySet(models.QuerySet):
    def in_display_order(self):
        order = [key for key, _label in SECTORS]
        return self.order_by(
            Case(*[When(sector=key, then=position) for position, key in enumerate(order)])
        )


class FundProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="fund_profile",
    )
    weight_team = models.PositiveSmallIntegerField(
        default=DEFAULT_WEIGHTS["team"],
        validators=[MaxValueValidator(100)],
    )
    weight_market = models.PositiveSmallIntegerField(
        default=DEFAULT_WEIGHTS["market"],
        validators=[MaxValueValidator(100)],
    )
    weight_product = models.PositiveSmallIntegerField(
        default=DEFAULT_WEIGHTS["product"],
        validators=[MaxValueValidator(100)],
    )
    weight_traction = models.PositiveSmallIntegerField(
        default=DEFAULT_WEIGHTS["traction"],
        validators=[MaxValueValidator(100)],
    )
    weight_terms = models.PositiveSmallIntegerField(
        default=DEFAULT_WEIGHTS["terms"],
        validators=[MaxValueValidator(100)],
    )

    def __str__(self):
        return f"Weights for {self.user}"

    def weight_map(self):
        return {
            "team": self.weight_team,
            "market": self.weight_market,
            "product": self.weight_product,
            "traction": self.weight_traction,
            "terms": self.weight_terms,
        }

    def clean(self):
        super().clean()
        total = sum(self.weight_map().values())
        if total != 100:
            raise ValidationError(f"Weights must sum to 100 (currently {total}).")


class SectorBenchmark(models.Model):
    sector = models.CharField(max_length=32, unique=True, choices=SECTORS)
    tam_floor_usd = models.BigIntegerField(validators=_non_negative())
    pre_money_low_usd = models.BigIntegerField(validators=_non_negative())
    pre_money_high_usd = models.BigIntegerField(validators=_non_negative())
    round_size_low_usd = models.BigIntegerField(validators=_non_negative())
    round_size_high_usd = models.BigIntegerField(validators=_non_negative())
    arr_low_usd = models.BigIntegerField(validators=_non_negative())
    arr_high_usd = models.BigIntegerField(validators=_non_negative())
    notes = models.TextField(blank=True)

    objects = SectorBenchmarkQuerySet.as_manager()

    class Meta:
        ordering = ["sector"]

    def __str__(self):
        return self.get_sector_display()

    def clean(self):
        super().clean()
        pairs = [
            ("pre_money_low_usd", "pre_money_high_usd", "Pre-money low cannot exceed high."),
            ("round_size_low_usd", "round_size_high_usd", "Round size low cannot exceed high."),
            ("arr_low_usd", "arr_high_usd", "ARR low cannot exceed high."),
        ]
        errors = {}
        for low_key, high_key, message in pairs:
            low = getattr(self, low_key)
            high = getattr(self, high_key)
            if low is not None and high is not None and low > high:
                errors[high_key] = message
        if errors:
            raise ValidationError(errors)


class Deal(models.Model):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="deals",
    )
    company_name = models.CharField(max_length=200)
    one_liner = models.CharField(max_length=300, blank=True)
    website = models.URLField(blank=True)
    sector = models.CharField(max_length=32, choices=SECTORS)
    location = models.CharField(max_length=200, blank=True)
    year_founded = models.PositiveSmallIntegerField(null=True, blank=True)
    status = models.CharField(
        max_length=32,
        choices=DEAL_STATUSES,
        default="researching",
    )
    evaluation_mode = models.CharField(
        max_length=16,
        choices=EVALUATION_MODES,
        default="ai",
    )
    founder_bios = models.TextField(blank=True)
    call_notes = models.TextField(blank=True)
    deck = models.FileField(
        upload_to="decks/",
        blank=True,
        validators=[validate_pdf],
    )
    round_type = models.CharField(max_length=32, choices=ROUND_TYPES, blank=True)
    raise_amount_usd = models.BigIntegerField(
        null=True,
        blank=True,
        validators=_non_negative(),
    )
    valuation_usd = models.BigIntegerField(
        null=True,
        blank=True,
        validators=_non_negative(),
        help_text="Pre-money valuation, or the valuation cap on a SAFE or note.",
    )
    lead_status = models.CharField(max_length=32, choices=LEAD_STATUSES, blank=True)
    committed_percent = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MaxValueValidator(100)],
        help_text="Share of the round already committed, including the lead.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-updated_at", "-id"]

    def __str__(self):
        return self.company_name


class Founder(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="founders")
    name = models.CharField(max_length=200)
    role = models.CharField(max_length=200, blank=True)
    is_technical = models.BooleanField(default=False)
    years_in_domain = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
    )
    full_time = models.BooleanField(default=False)

    class Meta:
        ordering = ["id"]

    def __str__(self):
        return self.name


class TeamProfile(models.Model):
    deal = models.OneToOneField(Deal, on_delete=models.CASCADE, related_name="team_profile")
    years_known = models.DecimalField(
        max_digits=4,
        decimal_places=1,
        null=True,
        blank=True,
    )
    skill_split = models.CharField(max_length=32, choices=SKILL_SPLITS, blank=True)
    vesting_in_place = models.BooleanField(null=True, blank=True)
    equity_health = models.CharField(max_length=32, choices=EQUITY_HEALTH, blank=True)

    def __str__(self):
        return f"Team for {self.deal}"


class MarketProfile(models.Model):
    deal = models.OneToOneField(
        Deal,
        on_delete=models.CASCADE,
        related_name="market_profile",
    )
    tam_usd = models.BigIntegerField(null=True, blank=True, validators=_non_negative())
    sam_usd = models.BigIntegerField(null=True, blank=True, validators=_non_negative())
    som_usd = models.BigIntegerField(null=True, blank=True, validators=_non_negative())
    market_growing = models.BooleanField(null=True, blank=True)
    structure = models.CharField(max_length=32, choices=MARKET_STRUCTURES, blank=True)
    why_now = models.TextField(blank=True)
    macro_trends = models.TextField(blank=True)

    def __str__(self):
        return f"Market for {self.deal}"


class ProductProfile(models.Model):
    deal = models.OneToOneField(
        Deal,
        on_delete=models.CASCADE,
        related_name="product_profile",
    )
    value_prop = models.CharField(max_length=32, choices=VALUE_PROPS, blank=True)
    product_stage = models.CharField(max_length=32, choices=PRODUCT_STAGES, blank=True)
    moat_types = models.JSONField(default=list, blank=True)
    moat_notes = models.TextField(blank=True)

    def __str__(self):
        return f"Product for {self.deal}"


class TractionProfile(models.Model):
    deal = models.OneToOneField(
        Deal,
        on_delete=models.CASCADE,
        related_name="traction_profile",
    )
    wau = models.PositiveIntegerField(null=True, blank=True)
    mau = models.PositiveIntegerField(null=True, blank=True)
    retention_note = models.TextField(blank=True)
    arr_usd = models.BigIntegerField(null=True, blank=True, validators=_non_negative())
    lois = models.PositiveIntegerField(null=True, blank=True)
    pilots = models.PositiveIntegerField(null=True, blank=True)
    waitlist = models.PositiveIntegerField(null=True, blank=True)
    monthly_burn_usd = models.BigIntegerField(
        null=True,
        blank=True,
        validators=_non_negative(),
    )
    capital_raised_usd = models.BigIntegerField(
        null=True,
        blank=True,
        validators=_non_negative(),
    )
    milestones_note = models.TextField(blank=True)

    def __str__(self):
        return f"Traction for {self.deal}"


class FactorScore(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="scores")
    factor_key = models.CharField(max_length=64, choices=FACTOR_CHOICES)
    score = models.PositiveSmallIntegerField()
    note = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["deal", "factor_key"],
                name="unique_deal_factor_score",
            ),
            models.CheckConstraint(
                check=models.Q(score__gte=1, score__lte=5),
                name="factor_score_between_1_and_5",
            ),
        ]

    def __str__(self):
        return f"{self.factor_key} {self.score} for {self.deal}"


class SourceDocument(models.Model):
    deal = models.ForeignKey(Deal, on_delete=models.CASCADE, related_name="source_documents")
    kind = models.CharField(max_length=32, choices=SOURCE_KINDS)
    body = models.TextField(blank=True)
    detail = models.TextField(blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["deal", "kind"],
                name="unique_deal_source_kind",
            ),
        ]
        ordering = ["kind"]

    def __str__(self):
        return f"{SOURCE_LABELS.get(self.kind, self.kind)} for {self.deal}"


class Assessment(models.Model):
    deal = models.OneToOneField(Deal, on_delete=models.CASCADE, related_name="assessment")
    model_name = models.CharField(max_length=120, blank=True)
    generated_at = models.DateTimeField(auto_now=True)
    against_text = models.TextField(blank=True)
    against_source = models.CharField(max_length=32, choices=SOURCE_KINDS, blank=True)
    against_excerpt = models.TextField(blank=True)
    against_locator = models.CharField(max_length=80, blank=True)
    against_verified = models.BooleanField(default=False)
    unverified = models.JSONField(default=list, blank=True)

    def __str__(self):
        return f"Assessment for {self.deal}"

    @property
    def against_citation(self):
        return citation_label(self.against_source, self.against_locator)


class Claim(models.Model):
    assessment = models.ForeignKey(
        Assessment,
        on_delete=models.CASCADE,
        related_name="claims",
    )
    category = models.CharField(max_length=32)
    body = models.TextField()
    source_kind = models.CharField(max_length=32, choices=SOURCE_KINDS)
    excerpt = models.TextField()
    locator = models.CharField(max_length=80, blank=True)
    position = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return f"{self.category} claim for {self.assessment.deal}"

    @property
    def citation(self):
        return citation_label(self.source_kind, self.locator)


def citation_label(kind, locator):
    base = SOURCE_LABELS.get(kind, kind or "Source")
    locator = (locator or "").strip()
    if locator:
        return f"{base}, {locator}"
    return base


def get_fund_profile(user):
    profile, _created = FundProfile.objects.get_or_create(user=user)
    return profile
