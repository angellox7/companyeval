from io import BytesIO
from unittest.mock import patch

from django.contrib.auth.models import User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from pypdf import PdfReader

from evaluations.ai.apply import apply_assessment
from evaluations.ai.client import format_deck_pages
from evaluations.ai.extract import ExtractError, extract_pdf, fetch_website, html_to_text
from evaluations.ai.generate import TEXT_LAYER_DETAIL
from evaluations.ai.verify import excerpt_in_source, verify_payload
from evaluations.models import Deal, FactorScore, SourceDocument


NOTES = (
    "Ada has spent eight years in grocery wholesale and the co-founders "
    "have worked together since 2019."
)


class ExcerptTests(SimpleTestCase):
    def test_accepts_a_real_excerpt(self):
        self.assertTrue(
            excerpt_in_source(
                "Ada   has spent EIGHT years in grocery wholesale",
                NOTES,
            )
        )

    def test_rejects_a_sentence_that_is_not_in_the_source(self):
        self.assertFalse(excerpt_in_source("They have 10 million in ARR", NOTES))

    def test_rejects_an_empty_excerpt(self):
        self.assertFalse(excerpt_in_source("  ", NOTES))


class VerifyPayloadTests(SimpleTestCase):
    def test_keeps_two_claims_and_drops_an_unsourced_one(self):
        source = type("Doc", (), {"body": NOTES})()
        payload = {
            "claims": [
                {
                    "category": "team",
                    "text": "The founders know grocery wholesale firsthand.",
                    "source": "call_notes",
                    "excerpt": "eight years in grocery wholesale",
                    "locator": "",
                },
                {
                    "category": "team",
                    "text": "The co-founders have a shared history.",
                    "source": "call_notes",
                    "excerpt": "worked together since 2019",
                    "locator": "",
                },
                {
                    "category": "team",
                    "text": "A third sourced sentence stays off the page.",
                    "source": "call_notes",
                    "excerpt": "grocery wholesale",
                    "locator": "",
                },
                {
                    "category": "market",
                    "text": "They have 10 million in ARR.",
                    "source": "call_notes",
                    "excerpt": "They have 10 million in ARR",
                    "locator": "",
                },
            ],
            "strongest_against": {
                "text": "Invented objection.",
                "source": "call_notes",
                "excerpt": "Series A metrics are missing",
                "locator": "",
            },
        }
        verified, unverified, against, against_ok = verify_payload(
            payload,
            {"call_notes": source},
        )
        self.assertEqual(len(verified), 2)
        self.assertEqual(verified[0]["category"], "team")
        self.assertFalse(against_ok)
        self.assertEqual(against["text"], "")
        self.assertTrue(any("10 million" in item["text"] for item in unverified))
        self.assertFalse(any("third sourced" in item["text"] for item in unverified))


class _FakeResponse:
    def __init__(self, body, final_url):
        self._body = body
        self._final_url = final_url
        self.headers = type("H", (), {"get_content_charset": lambda self: "utf-8"})()

    def read(self, _limit):
        return self._body

    def geturl(self):
        return self._final_url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class ExtractTests(SimpleTestCase):
    def test_html_drops_scripts(self):
        text = html_to_text("<html><p>Hello <b>team</b></p><script>secret()</script></html>")
        self.assertIn("Hello", text)
        self.assertIn("team", text)
        self.assertNotIn("secret", text)

    def test_html_keeps_meta_description_and_json_sentences(self):
        html = """
        <html><head>
          <meta name="description" content="Get an Airbnb for every kind of trip with 8 million vacation rentals.">
          <meta property="og:description" content="Get an Airbnb for every kind of trip with 8 million vacation rentals.">
          <script type="application/json">
            {"flag": "m13_search_input_services_enabled",
             "line": "Hosts earn extra income by sharing their homes with guests."}
          </script>
          <script>secret()</script>
        </head>
        <body><p>Hello team</p></body></html>
        """
        text = html_to_text(html)
        self.assertIn("8 million vacation rentals", text)
        self.assertEqual(text.count("8 million vacation rentals"), 1)
        self.assertIn("Hosts earn extra income by sharing their homes with guests.", text)
        self.assertIn("Hello", text)
        self.assertNotIn("secret", text)
        self.assertNotIn("m13_search_input_services_enabled", text)
        self.assertTrue(text.startswith("Get an Airbnb"))

    def test_website_must_be_http(self):
        with self.assertRaises(ExtractError):
            fetch_website("file:///etc/passwd")

    @patch("evaluations.ai.extract.urlopen")
    def test_fetch_website_reads_text(self, urlopen):
        urlopen.return_value = _FakeResponse(
            b"<html><body><p>Wholesale ordering</p></body></html>",
            "https://northwind.example",
        )
        text, truncated = fetch_website("https://northwind.example")
        self.assertIn("https://northwind.example", text)
        self.assertIn("Wholesale ordering", text)
        self.assertFalse(truncated)

    @patch("evaluations.ai.extract.urlopen")
    def test_fetch_website_follows_same_host_company_pages(self, urlopen):
        pages = {
            "https://northwind.example": b"""<html><body>
                <p>Wholesale ordering</p>
                <a href="/about">About</a>
                <a href="https://other.example/about">About</a>
                <a href="/pricing">Pricing</a>
                <a href="/blog">Blog</a>
            </body></html>""",
            "https://northwind.example/about": (
                b"<html><body><p>The founding team spent a decade in grocery wholesale.</p></body></html>"
            ),
            "https://northwind.example/pricing": (
                b"<html><body><p>Pricing starts at forty dollars a month for independent grocers.</p></body></html>"
            ),
        }

        def fake_open(request, timeout):
            self.assertEqual(timeout, 15)
            url = request.full_url
            if url not in pages:
                raise AssertionError(url)
            return _FakeResponse(pages[url], url)

        urlopen.side_effect = fake_open
        text, truncated = fetch_website("https://northwind.example")
        self.assertIn("https://northwind.example\nWholesale ordering", text)
        self.assertIn("https://northwind.example/about", text)
        self.assertIn("founding team spent a decade", text)
        self.assertIn("https://northwind.example/pricing", text)
        self.assertIn("forty dollars a month", text)
        self.assertNotIn("other.example", text)
        self.assertNotIn("https://northwind.example/blog", text)
        self.assertFalse(truncated)
        self.assertEqual(urlopen.call_count, 3)

    @patch("evaluations.ai.extract.urlopen")
    def test_fetch_website_skips_a_company_page_that_fails(self, urlopen):
        from urllib.error import HTTPError

        home = b'<html><body><p>Wholesale ordering</p><a href="/about">About</a><a href="/team">Team</a></body></html>'
        team = b"<html><body><p>Two founders split product and sales.</p></body></html>"

        def fake_open(request, timeout):
            url = request.full_url
            if url.endswith("/about"):
                raise HTTPError(url, 500, "err", hdrs=None, fp=None)
            if url.endswith("/team"):
                return _FakeResponse(team, url)
            return _FakeResponse(home, "https://northwind.example")

        urlopen.side_effect = fake_open
        text, truncated = fetch_website("https://northwind.example")
        self.assertIn("Wholesale ordering", text)
        self.assertIn("Two founders split product and sales.", text)
        self.assertNotIn("https://northwind.example/about", text)
        self.assertFalse(truncated)

    @patch("evaluations.ai.extract.urlopen")
    def test_fetch_website_stops_after_four_company_pages(self, urlopen):
        links = "".join(
            f'<a href="/{name}">{name}</a>'
            for name in ("about", "company", "product", "pricing", "customers", "story")
        )
        home = f"<html><body><p>Wholesale ordering</p>{links}</body></html>".encode()

        def fake_open(request, timeout):
            url = request.full_url
            if url == "https://northwind.example":
                return _FakeResponse(home, url)
            return _FakeResponse(b"<html><body><p>More company detail for this page.</p></body></html>", url)

        urlopen.side_effect = fake_open
        text, _truncated = fetch_website("https://northwind.example")
        self.assertIn("https://northwind.example/about", text)
        self.assertIn("https://northwind.example/pricing", text)
        self.assertNotIn("https://northwind.example/customers", text)
        self.assertNotIn("https://northwind.example/story", text)
        self.assertEqual(urlopen.call_count, 5)

    @patch("pypdf.PdfReader")
    def test_extract_pdf_keeps_page_markers(self, reader_cls):
        page = type("Page", (), {"extract_text": lambda self: "The market is large."})()
        reader_cls.return_value = type("Reader", (), {"pages": [page]})()
        body = extract_pdf(object())
        self.assertIn("[Page 1]", body)
        self.assertIn("The market is large.", body)


class ApplyAssessmentTests(TestCase):
    def test_scores_require_a_verified_claim_in_that_category(self):
        user = User.objects.create_user("investor2", password="secret123")
        deal = Deal.objects.create(
            owner=user,
            company_name="Northwind",
            sector="b2b_saas",
            evaluation_mode="ai",
            call_notes=NOTES,
        )
        SourceDocument.objects.create(deal=deal, kind="call_notes", body=NOTES)
        payload = {
            "one_liner": "Inventory for grocers",
            "founders": [{"name": "Ada Lovelace", "role": "CEO", "is_technical": True, "full_time": True}],
            "team": {"years_known": 5, "skill_split": "balanced", "vesting_in_place": True, "equity_health": "healthy"},
            "market": {},
            "product": {},
            "traction": {},
            "terms": {"round_type": "safe", "valuation_usd": 10000000},
            "scores": [
                {"factor_key": "domain_expertise", "score": 4, "note": ""},
                {"factor_key": "resilience", "score": 4, "note": ""},
                {"factor_key": "founder_dynamics", "score": 4, "note": ""},
                {"factor_key": "tam_growth", "score": 5, "note": ""},
            ],
            "claims": [
                {
                    "category": "team",
                    "text": "The founders know grocery wholesale firsthand.",
                    "source": "call_notes",
                    "excerpt": "eight years in grocery wholesale",
                    "locator": "",
                },
                {
                    "category": "market",
                    "text": "They have 10 million in ARR.",
                    "source": "call_notes",
                    "excerpt": "They have 10 million in ARR",
                    "locator": "",
                },
            ],
            "strongest_against": {
                "text": "The notes cover founder history and do not describe a product in market.",
                "source": "call_notes",
                "excerpt": "worked together since 2019",
                "locator": "",
            },
        }
        sources = {row.kind: row for row in deal.source_documents.all()}
        assessment = apply_assessment(deal, payload, sources, "gpt-test")
        self.assertTrue(assessment.against_verified)
        self.assertEqual(
            set(FactorScore.objects.filter(deal=deal).values_list("factor_key", flat=True)),
            {"domain_expertise", "resilience", "founder_dynamics"},
        )
        self.assertEqual(deal.founders.get().name, "Ada Lovelace")
        deal.refresh_from_db()
        self.assertEqual(deal.valuation_usd, 10000000)


@override_settings(OPENAI_API_KEY="test-key", OPENAI_MODEL="gpt-test")
class AssessmentViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("investor", password="secret123")
        self.client.login(username="investor", password="secret123")

    def test_ai_create_requires_a_source(self):
        response = self.client.post(
            reverse("evaluations:deal_create"),
            {
                "evaluation_mode": "ai",
                "company_name": "Empty",
                "sector": "b2b_saas",
                "status": "researching",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Add a deck, website, founder bios, or first-call notes.")

    def test_missing_api_key_does_not_crash(self):
        deal = Deal.objects.create(
            owner=self.user,
            company_name="Keyed",
            sector="b2b_saas",
            evaluation_mode="ai",
            call_notes=NOTES,
        )
        with override_settings(OPENAI_API_KEY=""):
            response = self.client.post(
                reverse("evaluations:deal_generate", args=[deal.pk]),
                follow=True,
            )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OPENAI_API_KEY")

    @patch("evaluations.ai.generate.request_assessment")
    def test_generate_shows_the_against_argument_and_a_citation(self, request_assessment):
        request_assessment.return_value = {
            "one_liner": "Inventory for grocers",
            "founders": [{"name": "Ada Lovelace", "role": "CEO", "is_technical": True}],
            "scores": [
                {"factor_key": "domain_expertise", "score": 5, "note": ""},
                {"factor_key": "resilience", "score": 5, "note": ""},
                {"factor_key": "founder_dynamics", "score": 5, "note": ""},
                {"factor_key": "tam_growth", "score": 5, "note": ""},
            ],
            "claims": [
                {
                    "category": "team",
                    "text": "The founders know grocery wholesale firsthand.",
                    "source": "call_notes",
                    "excerpt": "eight years in grocery wholesale",
                    "locator": "",
                },
                {
                    "category": "market",
                    "text": "They have 10 million in ARR.",
                    "source": "call_notes",
                    "excerpt": "They have 10 million in ARR",
                    "locator": "",
                },
            ],
            "strongest_against": {
                "text": "The notes cover founder history and do not describe a product in market.",
                "source": "call_notes",
                "excerpt": "worked together since 2019",
                "locator": "",
            },
        }
        created = self.client.post(
            reverse("evaluations:deal_create"),
            {
                "evaluation_mode": "ai",
                "company_name": "Northwind",
                "sector": "b2b_saas",
                "status": "researching",
                "call_notes": NOTES,
            },
        )
        deal = Deal.objects.get(company_name="Northwind")
        self.assertRedirects(created, reverse("evaluations:deal_assessment", args=[deal.pk]))
        response = self.client.post(
            reverse("evaluations:deal_generate", args=[deal.pk]),
            follow=True,
        )
        self.assertContains(response, "Strongest argument against investing")
        self.assertContains(response, "do not describe a product in market")
        self.assertContains(response, "First-call notes")
        self.assertContains(response, "eight years in grocery wholesale")
        self.assertContains(response, "Unverified")
        self.assertFalse(FactorScore.objects.filter(deal=deal, factor_key="tam_growth").exists())
        request_assessment.assert_called_once()

    @patch("evaluations.ai.generate.request_assessment")
    @patch("evaluations.ai.generate.transcribe_deck")
    def test_generate_quotes_the_deck_transcript(self, transcribe_deck, request_assessment):
        transcript = "[Page 1]\nBook rooms with locals, rather than hotels."
        transcribe_deck.return_value = transcript
        request_assessment.return_value = {
            "one_liner": "Book rooms with locals",
            "scores": [{"factor_key": "tam_growth", "score": 4, "note": ""}],
            "claims": [
                {
                    "category": "market",
                    "text": "Travelers can book rooms with locals instead of hotels.",
                    "source": "deck",
                    "excerpt": "Book rooms with locals, rather than hotels.",
                    "locator": "p. 1",
                }
            ],
            "strongest_against": {
                "text": "The deck describes a booking idea and does not show revenue.",
                "source": "deck",
                "excerpt": "Book rooms with locals, rather than hotels.",
                "locator": "p. 1",
            },
        }
        deal = Deal.objects.create(
            owner=self.user,
            company_name="Airbed",
            sector="marketplace",
            evaluation_mode="ai",
            deck=SimpleUploadedFile("deck.pdf", b"%PDF-1.4\n", content_type="application/pdf"),
        )
        response = self.client.post(
            reverse("evaluations:deal_generate", args=[deal.pk]),
            follow=True,
        )
        self.assertContains(response, "Book rooms with locals, rather than hotels.")
        self.assertContains(response, "Travelers can book rooms with locals instead of hotels.")
        transcribe_deck.assert_called_once()
        _deal, sources, _benchmark = request_assessment.call_args.args
        self.assertEqual(sources["deck"].body, transcript)
        self.assertNotIn("call_notes", sources)

    @patch("evaluations.ai.generate.extract_pdf", return_value="[Page 2]\nPrice is an important concern.")
    @patch("evaluations.ai.generate.transcribe_deck", return_value="")
    @patch("evaluations.ai.generate.request_assessment")
    def test_empty_page_reading_falls_back_to_pdf_text(
        self, request_assessment, transcribe_deck, extract_pdf
    ):
        request_assessment.return_value = {
            "scores": [],
            "claims": [],
            "strongest_against": {
                "text": "Price is called out as a customer concern.",
                "source": "deck",
                "excerpt": "Price is an important concern.",
                "locator": "p. 2",
            },
        }
        deal = Deal.objects.create(
            owner=self.user,
            company_name="Airbed",
            sector="marketplace",
            evaluation_mode="ai",
            deck=SimpleUploadedFile("deck.pdf", b"%PDF-1.4\n", content_type="application/pdf"),
        )
        self.client.post(reverse("evaluations:deal_generate", args=[deal.pk]), follow=True)
        document = deal.source_documents.get(kind="deck")
        self.assertIn("Price is an important concern.", document.body)
        self.assertEqual(document.detail, TEXT_LAYER_DETAIL)
        transcribe_deck.assert_called_once()
        extract_pdf.assert_called_once()


class FormatDeckPagesTests(SimpleTestCase):
    def test_formats_page_markers_and_skips_bad_rows(self):
        body = format_deck_pages(
            [
                {"page": 1, "text": " Book rooms with locals. "},
                {"page": 0, "text": "skip"},
                "not a page",
                {"page": 2, "text": ""},
            ]
        )
        self.assertEqual(body, "[Page 1]\nBook rooms with locals.\n\n[Page 2]")


def _verified_payload():
    return {
        "one_liner": "Inventory for grocers",
        "founders": [{"name": "Ada Lovelace", "role": "CEO", "is_technical": True, "full_time": True}],
        "terms": {"round_type": "safe", "valuation_usd": 10000000},
        "scores": [
            {"factor_key": "domain_expertise", "score": 4, "note": ""},
            {"factor_key": "resilience", "score": 4, "note": ""},
            {"factor_key": "founder_dynamics", "score": 4, "note": ""},
        ],
        "claims": [
            {
                "category": "team",
                "text": "The founders know grocery wholesale firsthand.",
                "source": "call_notes",
                "excerpt": "eight years in grocery wholesale",
                "locator": "",
            },
            {
                "category": "market",
                "text": "They have 10 million in ARR.",
                "source": "call_notes",
                "excerpt": "They have 10 million in ARR",
                "locator": "",
            },
        ],
        "strongest_against": {
            "text": "The notes cover founder history and do not describe a product in market.",
            "source": "call_notes",
            "excerpt": "worked together since 2019",
            "locator": "",
        },
    }


class AssessmentPdfTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("investor-pdf", password="secret123")
        self.client.login(username="investor-pdf", password="secret123")

    def _deal(self, **extra):
        fields = {
            "owner": self.user,
            "company_name": "Northwind",
            "sector": "b2b_saas",
            "evaluation_mode": "ai",
            "call_notes": NOTES,
        }
        fields.update(extra)
        return Deal.objects.create(**fields)

    def test_download_contains_the_memo_text(self):
        deal = self._deal()
        SourceDocument.objects.create(deal=deal, kind="call_notes", body=NOTES)
        apply_assessment(
            deal,
            _verified_payload(),
            {row.kind: row for row in deal.source_documents.all()},
            "gpt-test",
        )
        page = self.client.get(reverse("evaluations:deal_assessment", args=[deal.pk]))
        self.assertContains(page, "Download PDF")
        self.assertContains(page, f"{len(NOTES)} characters stored.")
        response = self.client.get(reverse("evaluations:deal_assessment_pdf", args=[deal.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn("Northwind-assessment.pdf", response["Content-Disposition"])
        body = b"".join(response.streaming_content)
        self.assertTrue(body.startswith(b"%PDF"))
        reader = PdfReader(BytesIO(body))
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        self.assertIn("Northwind", text)
        self.assertIn("do not describe a product in market", text)
        self.assertIn("First-call notes", text)
        self.assertNotIn("10 million in ARR", text)

    def test_missing_assessment_is_not_found(self):
        deal = self._deal(company_name="Empty")
        response = self.client.get(reverse("evaluations:deal_assessment_pdf", args=[deal.pk]))
        self.assertEqual(response.status_code, 404)

    def test_manual_deal_is_not_found(self):
        deal = self._deal(company_name="Manual Co", evaluation_mode="manual")
        response = self.client.get(reverse("evaluations:deal_assessment_pdf", args=[deal.pk]))
        self.assertEqual(response.status_code, 404)
