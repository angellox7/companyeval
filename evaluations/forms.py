from datetime import date

from django import forms
from django.forms import inlineformset_factory, modelformset_factory

from evaluations.constants import MOAT_TYPES
from evaluations.models import (
    Deal,
    Founder,
    FundProfile,
    MarketProfile,
    ProductProfile,
    SectorBenchmark,
    TeamProfile,
    TractionProfile,
)


def _relabel_blank(field, label):
    field.choices = [("", label)] + [choice for choice in field.choices if choice[0] != ""]


class DealForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            "evaluation_mode",
            "company_name",
            "one_liner",
            "website",
            "sector",
            "location",
            "year_founded",
            "status",
            "deck",
            "founder_bios",
            "call_notes",
        ]
        widgets = {
            "evaluation_mode": forms.RadioSelect,
            "deck": forms.FileInput(attrs={"accept": "application/pdf,.pdf"}),
            "founder_bios": forms.Textarea(attrs={"rows": 6}),
            "call_notes": forms.Textarea(attrs={"rows": 6}),
        }
        labels = {
            "evaluation_mode": "Evaluation",
            "company_name": "Company",
            "one_liner": "One-liner",
            "year_founded": "Year founded",
            "founder_bios": "Founder bios",
            "call_notes": "First-call notes",
        }
        help_texts = {
            "evaluation_mode": (
                "AI-assisted is the default. It reads the deck, website, founder bios, "
                "and first-call notes. Manual is the scorecard you fill in yourself."
            ),
            "founder_bios": "Paste bios. The AI assessment quotes them when you generate.",
            "call_notes": "Notes from the first call. The AI assessment quotes them when you generate.",
        }

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("evaluation_mode") != "ai":
            return cleaned
        has_deck = bool(cleaned.get("deck"))
        has_website = bool((cleaned.get("website") or "").strip())
        has_bios = bool((cleaned.get("founder_bios") or "").strip())
        has_notes = bool((cleaned.get("call_notes") or "").strip())
        if not any((has_deck, has_website, has_bios, has_notes)):
            raise forms.ValidationError(
                "Add a deck, website, founder bios, or first-call notes."
            )
        return cleaned

    def clean_year_founded(self):
        year = self.cleaned_data.get("year_founded")
        if year is None:
            return year
        this_year = date.today().year
        if year < 1900 or year > this_year:
            raise forms.ValidationError(
                f"Enter a founding year between 1900 and {this_year}."
            )
        return year


class TeamProfileForm(forms.ModelForm):
    vesting = forms.ChoiceField(
        choices=[("", "Unknown"), ("yes", "Yes"), ("no", "No")],
        required=False,
        label="Vesting in place",
    )

    class Meta:
        model = TeamProfile
        fields = ["years_known", "skill_split", "equity_health"]
        labels = {
            "years_known": "Years co-founders have known each other",
            "skill_split": "Skill split",
            "equity_health": "Equity split",
        }
        widgets = {
            "years_known": forms.NumberInput(attrs={"step": "0.5", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel_blank(self.fields["skill_split"], "Not set")
        _relabel_blank(self.fields["equity_health"], "Not set")
        current = self.instance.vesting_in_place
        if current is True:
            self.initial["vesting"] = "yes"
        elif current is False:
            self.initial["vesting"] = "no"

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.vesting_in_place = {"yes": True, "no": False}.get(self.cleaned_data["vesting"])
        if commit:
            profile.save()
        return profile


class FounderForm(forms.ModelForm):
    class Meta:
        model = Founder
        fields = ["name", "role", "is_technical", "years_in_domain", "full_time"]
        labels = {
            "is_technical": "Technical founder",
            "years_in_domain": "Years in the domain",
            "full_time": "Full-time",
        }
        widgets = {
            "years_in_domain": forms.NumberInput(attrs={"step": "0.5", "min": "0"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields["full_time"].initial = False
            self.fields["is_technical"].initial = False


FounderFormSet = inlineformset_factory(
    Deal,
    Founder,
    form=FounderForm,
    extra=1,
    can_delete=True,
    max_num=12,
)


class MarketProfileForm(forms.ModelForm):
    growing = forms.ChoiceField(
        choices=[("", "Unknown"), ("yes", "Yes"), ("no", "No")],
        required=False,
        label="Market expanding",
    )

    class Meta:
        model = MarketProfile
        fields = ["tam_usd", "sam_usd", "som_usd", "structure", "why_now", "macro_trends"]
        labels = {
            "tam_usd": "TAM (USD)",
            "sam_usd": "SAM (USD)",
            "som_usd": "SOM (USD)",
            "structure": "Market structure",
            "why_now": "Why now",
            "macro_trends": "Macro trends",
        }
        widgets = {
            "why_now": forms.Textarea(attrs={"rows": 4}),
            "macro_trends": forms.Textarea(attrs={"rows": 3}),
        }
        help_texts = {
            "tam_usd": "Total addressable market in US dollars.",
        }

    field_order = [
        "tam_usd",
        "sam_usd",
        "som_usd",
        "growing",
        "structure",
        "why_now",
        "macro_trends",
    ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel_blank(self.fields["structure"], "Not set")
        current = self.instance.market_growing
        if current is True:
            self.initial["growing"] = "yes"
        elif current is False:
            self.initial["growing"] = "no"

    def save(self, commit=True):
        profile = super().save(commit=False)
        profile.market_growing = {"yes": True, "no": False}.get(self.cleaned_data["growing"])
        if commit:
            profile.save()
        return profile


class ProductProfileForm(forms.ModelForm):
    moat_types = forms.MultipleChoiceField(
        choices=MOAT_TYPES,
        widget=forms.CheckboxSelectMultiple,
        required=False,
        label="Moats",
    )

    class Meta:
        model = ProductProfile
        fields = ["value_prop", "product_stage", "moat_types", "moat_notes"]
        labels = {
            "value_prop": "Value proposition",
            "product_stage": "Product stage",
            "moat_notes": "Moat notes",
        }
        widgets = {
            "moat_notes": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel_blank(self.fields["value_prop"], "Not set")
        _relabel_blank(self.fields["product_stage"], "Not set")
        if self.instance.pk and self.instance.moat_types:
            self.initial["moat_types"] = list(self.instance.moat_types)

    def clean_moat_types(self):
        selected = self.cleaned_data.get("moat_types") or []
        if "none" in selected and len(selected) > 1:
            raise forms.ValidationError("None cannot be combined with other moats.")
        return selected


class TractionProfileForm(forms.ModelForm):
    class Meta:
        model = TractionProfile
        fields = [
            "wau",
            "mau",
            "retention_note",
            "arr_usd",
            "lois",
            "pilots",
            "waitlist",
            "monthly_burn_usd",
            "capital_raised_usd",
            "milestones_note",
        ]
        labels = {
            "wau": "Weekly active users",
            "mau": "Monthly active users",
            "retention_note": "Retention",
            "arr_usd": "ARR (USD)",
            "lois": "Letters of intent",
            "pilots": "Pilots",
            "waitlist": "Waitlist",
            "monthly_burn_usd": "Monthly burn (USD)",
            "capital_raised_usd": "Capital raised (USD)",
            "milestones_note": "Milestones versus capital",
        }
        widgets = {
            "retention_note": forms.Textarea(attrs={"rows": 3}),
            "milestones_note": forms.Textarea(attrs={"rows": 3}),
        }


class TermsForm(forms.ModelForm):
    class Meta:
        model = Deal
        fields = [
            "round_type",
            "raise_amount_usd",
            "valuation_usd",
            "lead_status",
            "committed_percent",
        ]
        labels = {
            "round_type": "Instrument",
            "raise_amount_usd": "Amount raising (USD)",
            "valuation_usd": "Pre-money or cap (USD)",
            "lead_status": "Lead",
            "committed_percent": "Percent of the round committed",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        _relabel_blank(self.fields["round_type"], "Not set")
        _relabel_blank(self.fields["lead_status"], "Not set")


class CategoryScoreForm(forms.Form):
    def __init__(self, *args, factors, existing=None, **kwargs):
        self.factors = list(factors)
        super().__init__(*args, **kwargs)
        existing = existing or {}
        for key, label in self.factors:
            self.fields[f"score_{key}"] = forms.TypedChoiceField(
                label=label,
                choices=[("", "Unscored")] + [(str(number), str(number)) for number in range(1, 6)],
                coerce=int,
                required=False,
                empty_value=None,
                widget=forms.RadioSelect,
            )
            self.fields[f"note_{key}"] = forms.CharField(
                label=f"Note on {label.lower()}",
                required=False,
                widget=forms.Textarea(attrs={"rows": 2}),
            )
            current = existing.get(key)
            if current is not None:
                self.initial[f"score_{key}"] = str(current.score)
                self.initial[f"note_{key}"] = current.note

    def clean(self):
        cleaned = super().clean()
        for key, label in self.factors:
            score = cleaned.get(f"score_{key}")
            note = (cleaned.get(f"note_{key}") or "").strip()
            if note and score is None:
                self.add_error(f"score_{key}", "Choose a score to save this note.")
        return cleaned

    def score_rows(self):
        return [
            {
                "key": key,
                "label": label,
                "score": self[f"score_{key}"],
                "note": self[f"note_{key}"],
            }
            for key, label in self.factors
        ]


class FundSettingsForm(forms.ModelForm):
    class Meta:
        model = FundProfile
        fields = [
            "weight_team",
            "weight_market",
            "weight_product",
            "weight_traction",
            "weight_terms",
        ]
        labels = {
            "weight_team": "Team",
            "weight_market": "Market",
            "weight_product": "Product",
            "weight_traction": "Traction",
            "weight_terms": "Deal terms",
        }
        help_texts = {field: "Percent" for field in fields}


class BenchmarkForm(forms.ModelForm):
    class Meta:
        model = SectorBenchmark
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
        labels = {
            "tam_floor_usd": "TAM floor (USD)",
            "pre_money_low_usd": "Pre-money or cap, low (USD)",
            "pre_money_high_usd": "Pre-money or cap, high (USD)",
            "round_size_low_usd": "Round size, low (USD)",
            "round_size_high_usd": "Round size, high (USD)",
            "arr_low_usd": "ARR, low (USD)",
            "arr_high_usd": "ARR, high (USD)",
            "notes": "Notes",
        }
        widgets = {
            "notes": forms.Textarea(attrs={"rows": 2}),
        }


BenchmarkFormSet = modelformset_factory(
    SectorBenchmark,
    form=BenchmarkForm,
    extra=0,
    can_delete=False,
)
