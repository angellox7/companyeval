from decimal import Decimal

from django.contrib.auth.models import User
from django.test import TestCase

from evaluations.flags import collect_flags, worst_flag
from evaluations.models import (
    Deal,
    FactorScore,
    Founder,
    MarketProfile,
    ProductProfile,
    SectorBenchmark,
    TeamProfile,
    TractionProfile,
)


class FlagTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("investor", password="pw")
        self.deal = Deal.objects.create(
            owner=self.user,
            company_name="Acme",
            sector="b2b_saas",
        )

    def flags(self):
        deal = Deal.objects.prefetch_related("scores", "founders").get(pk=self.deal.pk)
        benchmark = SectorBenchmark.objects.filter(sector=deal.sector).first()
        return collect_flags(deal, benchmark)

    def codes(self):
        return {flag.code for flag in self.flags()}

    def test_benchmarks_are_seeded(self):
        self.assertEqual(SectorBenchmark.objects.count(), 8)

    def test_blank_deal_has_no_flags(self):
        self.assertEqual(self.codes(), set())

    def test_factor_score_of_one_is_high(self):
        FactorScore.objects.create(deal=self.deal, factor_key="domain_expertise", score=1)
        flags = self.flags()
        self.assertIn("factor_low", {flag.code for flag in flags})
        self.assertTrue(any("Domain expertise" in flag.message for flag in flags))
        self.assertNotIn("category_high", {flag.code for flag in flags})

    def test_complete_category_at_two_is_high(self):
        for key in ("domain_expertise", "resilience", "founder_dynamics"):
            FactorScore.objects.create(deal=self.deal, factor_key=key, score=2)
        self.assertIn("category_high", self.codes())
        self.assertNotIn("category_watch", self.codes())
        self.assertNotIn("factor_low", self.codes())

    def test_complete_category_between_two_and_three_is_watch(self):
        FactorScore.objects.create(deal=self.deal, factor_key="domain_expertise", score=2)
        FactorScore.objects.create(deal=self.deal, factor_key="resilience", score=3)
        FactorScore.objects.create(deal=self.deal, factor_key="founder_dynamics", score=3)
        codes = self.codes()
        self.assertIn("category_watch", codes)
        self.assertNotIn("category_high", codes)

    def test_complete_category_at_three_has_no_category_flag(self):
        for key in ("domain_expertise", "resilience", "founder_dynamics"):
            FactorScore.objects.create(deal=self.deal, factor_key=key, score=3)
        self.assertEqual(self.codes(), set())

    def test_tam_below_floor(self):
        benchmark = SectorBenchmark.objects.get(sector="b2b_saas")
        MarketProfile.objects.create(deal=self.deal, tam_usd=benchmark.tam_floor_usd - 1)
        self.assertIn("tam_below_floor", self.codes())

    def test_tam_at_floor_is_clear(self):
        benchmark = SectorBenchmark.objects.get(sector="b2b_saas")
        MarketProfile.objects.create(deal=self.deal, tam_usd=benchmark.tam_floor_usd)
        self.assertNotIn("tam_below_floor", self.codes())

    def test_valuation_above_band(self):
        benchmark = SectorBenchmark.objects.get(sector="b2b_saas")
        self.deal.valuation_usd = benchmark.pre_money_high_usd + 1
        self.deal.save()
        self.assertIn("valuation_above_band", self.codes())

    def test_valuation_at_high_end_is_clear(self):
        benchmark = SectorBenchmark.objects.get(sector="b2b_saas")
        self.deal.valuation_usd = benchmark.pre_money_high_usd
        self.deal.save()
        self.assertNotIn("valuation_above_band", self.codes())

    def test_idea_without_pipeline_is_flagged(self):
        ProductProfile.objects.create(deal=self.deal, product_stage="idea")
        self.assertIn("no_validation", self.codes())

    def test_deck_only_without_pipeline_is_flagged(self):
        ProductProfile.objects.create(deal=self.deal, product_stage="deck_only")
        self.assertIn("no_validation", self.codes())

    def test_a_letter_of_intent_clears_the_validation_flag(self):
        ProductProfile.objects.create(deal=self.deal, product_stage="idea")
        TractionProfile.objects.create(deal=self.deal, lois=1)
        self.assertNotIn("no_validation", self.codes())

    def test_a_pilot_or_waitlist_clears_the_validation_flag(self):
        ProductProfile.objects.create(deal=self.deal, product_stage="idea")
        TractionProfile.objects.create(deal=self.deal, pilots=2)
        self.assertNotIn("no_validation", self.codes())
        TractionProfile.objects.filter(deal=self.deal).update(pilots=0, waitlist=3)
        self.assertNotIn("no_validation", self.codes())

    def test_live_mvp_without_pipeline_is_clear(self):
        ProductProfile.objects.create(deal=self.deal, product_stage="mvp_live")
        self.assertNotIn("no_validation", self.codes())

    def test_deep_tech_without_a_technical_founder(self):
        self.deal.sector = "deep_tech"
        self.deal.save()
        Founder.objects.create(deal=self.deal, name="Ada", is_technical=False)
        self.assertIn("no_technical_founder", self.codes())

    def test_deep_tech_with_a_technical_founder_is_clear(self):
        self.deal.sector = "deep_tech"
        self.deal.save()
        Founder.objects.create(deal=self.deal, name="Grace", is_technical=True)
        self.assertNotIn("no_technical_founder", self.codes())

    def test_deep_tech_with_no_founders_entered_is_clear(self):
        self.deal.sector = "deep_tech"
        self.deal.save()
        self.assertNotIn("no_technical_founder", self.codes())

    def test_short_founder_history(self):
        TeamProfile.objects.create(deal=self.deal, years_known=Decimal("0.5"))
        self.assertIn("short_founder_history", self.codes())

    def test_one_year_together_is_clear(self):
        TeamProfile.objects.create(deal=self.deal, years_known=Decimal("1"))
        self.assertNotIn("short_founder_history", self.codes())

    def test_missing_vesting(self):
        TeamProfile.objects.create(deal=self.deal, vesting_in_place=False)
        self.assertIn("no_vesting", self.codes())

    def test_unknown_vesting_is_clear(self):
        TeamProfile.objects.create(deal=self.deal, vesting_in_place=None)
        self.assertNotIn("no_vesting", self.codes())

    def test_no_lead(self):
        self.deal.lead_status = "no_lead"
        self.deal.save()
        self.assertIn("no_lead", self.codes())

    def test_blank_lead_is_clear(self):
        self.assertNotIn("no_lead", self.codes())

    def test_no_moat(self):
        ProductProfile.objects.create(deal=self.deal, moat_types=["none"])
        self.assertIn("no_moat", self.codes())

    def test_blank_moat_is_clear(self):
        ProductProfile.objects.create(deal=self.deal, moat_types=[])
        self.assertNotIn("no_moat", self.codes())

    def test_burn_before_a_product(self):
        ProductProfile.objects.create(deal=self.deal, product_stage="idea")
        TractionProfile.objects.create(deal=self.deal, monthly_burn_usd=25000)
        self.assertIn("burn_before_product", self.codes())

    def test_burn_with_a_live_mvp_is_clear(self):
        ProductProfile.objects.create(deal=self.deal, product_stage="mvp_live")
        TractionProfile.objects.create(deal=self.deal, monthly_burn_usd=25000)
        self.assertNotIn("burn_before_product", self.codes())

    def test_zero_burn_on_an_idea_is_clear(self):
        ProductProfile.objects.create(deal=self.deal, product_stage="deck_only")
        TractionProfile.objects.create(deal=self.deal, monthly_burn_usd=0)
        self.assertNotIn("burn_before_product", self.codes())

    def test_worst_flag_prefers_high(self):
        for key in ("domain_expertise", "resilience", "founder_dynamics"):
            FactorScore.objects.create(
                deal=self.deal,
                factor_key=key,
                score=2 if key != "founder_dynamics" else 3,
            )
        flags = self.flags()
        self.assertEqual(worst_flag(flags).severity, "watch")
        flagged = self.flags()
        flagged.append(
            type(flagged[0])(
                severity="high",
                code="no_lead",
                message="The round has no lead.",
            )
        )
        self.assertEqual(worst_flag(flagged).severity, "high")
