from django.contrib import admin

from evaluations.models import (
    Assessment,
    Claim,
    Deal,
    FactorScore,
    Founder,
    FundProfile,
    MarketProfile,
    ProductProfile,
    SectorBenchmark,
    SourceDocument,
    TeamProfile,
    TractionProfile,
)


class FounderInline(admin.TabularInline):
    model = Founder
    extra = 0


class FactorScoreInline(admin.TabularInline):
    model = FactorScore
    extra = 0


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("company_name", "sector", "status", "evaluation_mode", "owner", "updated_at")
    list_filter = ("sector", "status", "evaluation_mode")
    search_fields = ("company_name",)
    inlines = [FounderInline, FactorScoreInline]


@admin.register(FundProfile)
class FundProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "weight_team",
        "weight_market",
        "weight_product",
        "weight_traction",
        "weight_terms",
    )


@admin.register(SectorBenchmark)
class SectorBenchmarkAdmin(admin.ModelAdmin):
    list_display = (
        "sector",
        "tam_floor_usd",
        "pre_money_low_usd",
        "pre_money_high_usd",
        "round_size_low_usd",
        "round_size_high_usd",
    )


admin.site.register(TeamProfile)
admin.site.register(MarketProfile)
admin.site.register(ProductProfile)
admin.site.register(TractionProfile)
admin.site.register(SourceDocument)
admin.site.register(Assessment)
admin.site.register(Claim)
