from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from evaluations.forms import DealForm
from evaluations.models import Deal, FundProfile, MarketProfile, SectorBenchmark, SourceDocument


class DealFlowTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("investor", password="secret123")
        self.client.login(username="investor", password="secret123")

    def _score_fields(self, keys, value="5"):
        data = {}
        for key in keys:
            data[f"scores-score_{key}"] = value
        return data

    def test_pipeline_requires_login(self):
        self.client.logout()
        response = self.client.get(reverse("evaluations:pipeline"))
        self.assertRedirects(response, "/accounts/login/?next=/")

    def test_create_deal_score_it_and_show_the_composite(self):
        response = self.client.post(
            reverse("evaluations:deal_create"),
            {
                "company_name": "Northwind",
                "one_liner": "Inventory for independent grocers",
                "website": "https://northwind.example",
                "sector": "b2b_saas",
                "location": "Chicago",
                "year_founded": "2024",
                "status": "researching",
                "evaluation_mode": "manual",
            },
        )
        deal = Deal.objects.get(company_name="Northwind")
        self.assertRedirects(response, reverse("evaluations:deal_detail", args=[deal.pk]))

        team = self.client.post(
            reverse("evaluations:team_section", args=[deal.pk]),
            {
                "years_known": "4",
                "skill_split": "balanced",
                "vesting": "yes",
                "equity_health": "healthy",
                "founders-TOTAL_FORMS": "1",
                "founders-INITIAL_FORMS": "0",
                "founders-MIN_NUM_FORMS": "0",
                "founders-MAX_NUM_FORMS": "12",
                "founders-0-name": "Ada Lovelace",
                "founders-0-role": "CEO",
                "founders-0-is_technical": "on",
                "founders-0-years_in_domain": "8",
                "founders-0-full_time": "on",
                **self._score_fields(
                    ["domain_expertise", "resilience", "founder_dynamics"]
                ),
            },
        )
        self.assertRedirects(team, reverse("evaluations:deal_detail", args=[deal.pk]))

        market = self.client.post(
            reverse("evaluations:market_section", args=[deal.pk]),
            {
                "tam_usd": "2000000000",
                "growing": "yes",
                "structure": "room_for_several",
                "why_now": "Wholesale ordering moved online.",
                **self._score_fields(["tam_growth", "entrant_room", "why_now"]),
            },
        )
        self.assertRedirects(market, reverse("evaluations:deal_detail", args=[deal.pk]))

        product = self.client.post(
            reverse("evaluations:product_section", args=[deal.pk]),
            {
                "value_prop": "must_have",
                "product_stage": "mvp_live",
                "moat_types": ["proprietary_tech"],
                **self._score_fields(["value_prop", "product_stage", "moat"]),
            },
        )
        self.assertRedirects(product, reverse("evaluations:deal_detail", args=[deal.pk]))

        traction = self.client.post(
            reverse("evaluations:traction_section", args=[deal.pk]),
            {
                "arr_usd": "120000",
                "lois": "2",
                **self._score_fields(["engagement", "revenue_pipeline", "capital_efficiency"]),
            },
        )
        self.assertRedirects(traction, reverse("evaluations:deal_detail", args=[deal.pk]))

        terms = self.client.post(
            reverse("evaluations:terms_section", args=[deal.pk]),
            {
                "round_type": "safe",
                "raise_amount_usd": "2500000",
                "valuation_usd": "10000000",
                "lead_status": "lead_committed",
                "committed_percent": "60",
                **self._score_fields(["valuation", "round_construction"]),
            },
            follow=True,
        )
        self.assertContains(terms, 'data-composite="100"')
        self.assertContains(terms, "Strong pursue")
        self.assertContains(terms, "Ada Lovelace")

        pipeline = self.client.get(reverse("evaluations:pipeline"))
        self.assertContains(pipeline, "Northwind")
        self.assertContains(pipeline, "Strong pursue")
        self.assertContains(
            pipeline,
            reverse("evaluations:deal_edit", args=[deal.pk]),
        )

    def test_other_users_deal_is_hidden(self):
        other = User.objects.create_user("other", password="secret123")
        Deal.objects.create(
            owner=other,
            company_name="Hidden",
            sector="consumer",
        )
        detail = self.client.get(
            reverse("evaluations:deal_detail", args=[Deal.objects.get(company_name="Hidden").pk])
        )
        self.assertEqual(detail.status_code, 404)
        pipeline = self.client.get(reverse("evaluations:pipeline"))
        self.assertNotContains(pipeline, "Hidden")

    def test_owner_can_delete_a_deal_from_the_pipeline(self):
        deal = Deal.objects.create(
            owner=self.user,
            company_name="Northwind",
            sector="b2b_saas",
        )
        response = self.client.post(
            reverse("evaluations:deal_delete", args=[deal.pk]),
            follow=True,
        )
        self.assertRedirects(response, reverse("evaluations:pipeline"))
        self.assertFalse(Deal.objects.filter(pk=deal.pk).exists())
        self.assertContains(response, "Northwind deleted.")
        self.assertNotContains(response, "company-link")

    def test_other_users_deal_cannot_be_deleted(self):
        other = User.objects.create_user("other", password="secret123")
        deal = Deal.objects.create(
            owner=other,
            company_name="Hidden",
            sector="consumer",
        )
        response = self.client.post(reverse("evaluations:deal_delete", args=[deal.pk]))
        self.assertEqual(response.status_code, 404)
        self.assertTrue(Deal.objects.filter(pk=deal.pk).exists())

    def test_weights_must_sum_to_100(self):
        response = self.client.post(
            reverse("evaluations:fund_settings"),
            {
                "weight_team": "40",
                "weight_market": "10",
                "weight_product": "10",
                "weight_traction": "10",
                "weight_terms": "10",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "currently 80")
        profile = FundProfile.objects.get(user=self.user)
        self.assertEqual(profile.weight_team, 30)

        saved = self.client.post(
            reverse("evaluations:fund_settings"),
            {
                "weight_team": "40",
                "weight_market": "20",
                "weight_product": "20",
                "weight_traction": "10",
                "weight_terms": "10",
            },
        )
        self.assertRedirects(saved, reverse("evaluations:fund_settings"))
        profile.refresh_from_db()
        self.assertEqual(
            profile.weight_map(),
            {
                "team": 40,
                "market": 20,
                "product": 20,
                "traction": 10,
                "terms": 10,
            },
        )

    def test_benchmark_edit_changes_the_dashboard(self):
        deal = Deal.objects.create(
            owner=self.user,
            company_name="Bench Co",
            sector="b2b_saas",
        )
        MarketProfile.objects.create(deal=deal, tam_usd=1_000_000_000)
        before = self.client.get(reverse("evaluations:deal_detail", args=[deal.pk]))
        self.assertContains(before, "Meets the venture-scale floor")

        benches = list(SectorBenchmark.objects.in_display_order())
        data = {
            "benchmarks-TOTAL_FORMS": str(len(benches)),
            "benchmarks-INITIAL_FORMS": str(len(benches)),
            "benchmarks-MIN_NUM_FORMS": "0",
            "benchmarks-MAX_NUM_FORMS": "1000",
        }
        fields = [
            "tam_floor_usd",
            "pre_money_low_usd",
            "pre_money_high_usd",
            "round_size_low_usd",
            "round_size_high_usd",
            "arr_low_usd",
            "arr_high_usd",
            "notes",
        ]
        for index, bench in enumerate(benches):
            data[f"benchmarks-{index}-id"] = str(bench.pk)
            for field in fields:
                value = getattr(bench, field)
                if bench.sector == "b2b_saas" and field == "tam_floor_usd":
                    value = 5_000_000_000
                data[f"benchmarks-{index}-{field}"] = value
        updated = self.client.post(reverse("evaluations:benchmarks"), data)
        self.assertRedirects(updated, reverse("evaluations:benchmarks"))
        after = self.client.get(reverse("evaluations:deal_detail", args=[deal.pk]))
        self.assertContains(after, "Below the venture-scale floor")

    def test_sections_render_and_a_blank_founder_row_can_be_skipped(self):
        deal = Deal.objects.create(
            owner=self.user,
            company_name="Render Co",
            sector="fintech",
        )
        pages = [
            "deal_detail",
            "deal_edit",
            "team_section",
            "market_section",
            "product_section",
            "traction_section",
            "terms_section",
        ]
        for name in pages:
            response = self.client.get(reverse(f"evaluations:{name}", args=[deal.pk]))
            self.assertEqual(response.status_code, 200, name)
        for name in ("deal_create", "benchmarks", "fund_settings"):
            response = self.client.get(reverse(f"evaluations:{name}"))
            self.assertEqual(response.status_code, 200, name)

        saved = self.client.post(
            reverse("evaluations:team_section", args=[deal.pk]),
            {
                "years_known": "",
                "skill_split": "",
                "vesting": "",
                "equity_health": "",
                "founders-TOTAL_FORMS": "1",
                "founders-INITIAL_FORMS": "0",
                "founders-MIN_NUM_FORMS": "0",
                "founders-MAX_NUM_FORMS": "12",
                "founders-0-name": "",
                "founders-0-role": "",
                "founders-0-years_in_domain": "",
                **self._score_fields(["domain_expertise", "resilience", "founder_dynamics"], "4"),
            },
        )
        self.assertRedirects(saved, reverse("evaluations:deal_detail", args=[deal.pk]))
        self.assertEqual(deal.founders.count(), 0)
        detail = self.client.get(reverse("evaluations:deal_detail", args=[deal.pk]))
        self.assertContains(detail, "Partial")
        self.assertContains(detail, 'data-composite="24"')

    def test_deck_must_be_a_pdf(self):
        text = SimpleUploadedFile("deck.txt", b"hello", content_type="text/plain")
        form = DealForm(
            data={
                "company_name": "Northwind",
                "sector": "b2b_saas",
                "status": "researching",
                "evaluation_mode": "manual",
            },
            files={"deck": text},
        )
        self.assertFalse(form.is_valid())
        self.assertIn("deck", form.errors)

        pdf = SimpleUploadedFile(
            "deck.pdf",
            b"%PDF-1.4\n",
            content_type="application/pdf",
        )
        valid = DealForm(
            data={
                "company_name": "Northwind",
                "sector": "b2b_saas",
                "status": "researching",
                "evaluation_mode": "manual",
            },
            files={"deck": pdf},
        )
        self.assertTrue(valid.is_valid(), valid.errors)

    def test_editing_company_keeps_the_deck(self):
        pdf = SimpleUploadedFile(
            "deck.pdf",
            b"%PDF-1.4\n",
            content_type="application/pdf",
        )
        created = self.client.post(
            reverse("evaluations:deal_create"),
            {
                "company_name": "Northwind",
                "sector": "b2b_saas",
                "status": "researching",
                "evaluation_mode": "ai",
                "call_notes": "First call.",
                "deck": pdf,
            },
        )
        deal = Deal.objects.get(company_name="Northwind")
        self.assertRedirects(created, reverse("evaluations:deal_assessment", args=[deal.pk]))
        stored = deal.deck.name
        self.assertTrue(stored)

        saved = self.client.post(
            reverse("evaluations:deal_edit", args=[deal.pk]),
            {
                "company_name": "Northwind",
                "sector": "b2b_saas",
                "status": "researching",
                "evaluation_mode": "ai",
                "call_notes": "Updated notes.",
                "website": "https://northwind.example",
            },
        )
        self.assertRedirects(saved, reverse("evaluations:deal_assessment", args=[deal.pk]))
        deal.refresh_from_db()
        self.assertEqual(deal.deck.name, stored)
        self.assertEqual(deal.call_notes, "Updated notes.")

    def test_attached_deck_without_a_reading_asks_to_generate(self):
        pdf = SimpleUploadedFile(
            "deck.pdf",
            b"%PDF-1.4\n",
            content_type="application/pdf",
        )
        deal = Deal.objects.create(
            owner=self.user,
            company_name="Northwind",
            sector="b2b_saas",
            evaluation_mode="ai",
            deck=pdf,
        )
        SourceDocument.objects.create(deal=deal, kind="deck", body="", detail="")
        response = self.client.get(reverse("evaluations:deal_assessment", args=[deal.pk]))
        self.assertContains(response, "Attached. Generate the assessment to read it.")
        self.assertNotContains(response, "Not provided.")
