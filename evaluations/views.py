import io

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.conf import settings as django_settings

from evaluations.ai.generate import GenerationError, generate_assessment
from evaluations.ai.pdf import assessment_filename, render_assessment_pdf
from evaluations.ai.present import memo_sections
from evaluations.constants import FACTORS, SOURCE_KINDS
from evaluations.forms import (
    BenchmarkFormSet,
    CategoryScoreForm,
    DealForm,
    FounderFormSet,
    FundSettingsForm,
    MarketProfileForm,
    ProductProfileForm,
    TeamProfileForm,
    TermsForm,
    TractionProfileForm,
)
from evaluations.models import (
    Deal,
    FactorScore,
    MarketProfile,
    ProductProfile,
    SectorBenchmark,
    SourceDocument,
    TeamProfile,
    TractionProfile,
    get_fund_profile,
)
from evaluations.report import build_report


def _deal_queryset():
    return Deal.objects.select_related(
        "team_profile",
        "market_profile",
        "product_profile",
        "traction_profile",
    ).prefetch_related("scores", "founders")


def _owned_deal(request, pk):
    return get_object_or_404(_deal_queryset(), pk=pk, owner=request.user)


def _existing_scores(deal):
    return {score.factor_key: score for score in deal.scores.all()}


def _save_scores(deal, score_form, factors):
    for key, _label in factors:
        value = score_form.cleaned_data[f"score_{key}"]
        note = (score_form.cleaned_data.get(f"note_{key}") or "").strip()
        if value is None:
            FactorScore.objects.filter(deal=deal, factor_key=key).delete()
        else:
            FactorScore.objects.update_or_create(
                deal=deal,
                factor_key=key,
                defaults={"score": value, "note": note},
            )
    Deal.objects.filter(pk=deal.pk).update(updated_at=timezone.now())


def _benchmarks_by_sector():
    return {row.sector: row for row in SectorBenchmark.objects.all()}


def _section_context(deal, section, title, form, score_form, **extra):
    context = {
        "deal": deal,
        "section": section,
        "title": title,
        "form": form,
        "score_form": score_form,
        "benchmark": SectorBenchmark.objects.filter(sector=deal.sector).first(),
    }
    context.update(extra)
    return context


@login_required
def pipeline(request):
    deals = _deal_queryset().filter(owner=request.user)
    weights = get_fund_profile(request.user).weight_map()
    benchmarks = _benchmarks_by_sector()
    reports = [build_report(deal, weights, benchmarks.get(deal.sector)) for deal in deals]
    return render(request, "evaluations/pipeline.html", {"reports": reports})


@login_required
@require_POST
def deal_delete(request, pk):
    deal = _owned_deal(request, pk)
    company_name = deal.company_name
    if deal.deck:
        deal.deck.delete(save=False)
    deal.delete()
    messages.success(request, f"{company_name} deleted.")
    return redirect("evaluations:pipeline")


@login_required
def deal_create(request):
    if request.method == "POST":
        form = DealForm(request.POST, request.FILES)
        if form.is_valid():
            deal = form.save(commit=False)
            deal.owner = request.user
            deal.save()
            messages.success(request, "Deal added.")
            if deal.evaluation_mode == "ai":
                return redirect("evaluations:deal_assessment", pk=deal.pk)
            return redirect("evaluations:deal_detail", pk=deal.pk)
    else:
        form = DealForm()
    return render(
        request,
        "evaluations/deal_form.html",
        {"form": form, "title": "New deal", "submit_label": "Create deal"},
    )


@login_required
def deal_edit(request, pk):
    deal = _owned_deal(request, pk)
    if request.method == "POST":
        form = DealForm(request.POST, request.FILES, instance=deal)
        if form.is_valid():
            form.save()
            if deal.evaluation_mode == "ai":
                messages.success(
                    request,
                    "Sources saved. Generate the assessment again to use them.",
                )
                return redirect("evaluations:deal_assessment", pk=deal.pk)
            messages.success(request, "Company details saved.")
            return redirect("evaluations:deal_detail", pk=deal.pk)
    else:
        form = DealForm(instance=deal)
    return render(
        request,
        "evaluations/deal_form.html",
        {
            "form": form,
            "deal": deal,
            "title": "Edit company",
            "submit_label": "Save company",
            "section": "edit",
        },
    )


@login_required
def deal_detail(request, pk):
    deal = _owned_deal(request, pk)
    weights = get_fund_profile(request.user).weight_map()
    benchmark = SectorBenchmark.objects.filter(sector=deal.sector).first()
    report = build_report(deal, weights, benchmark)
    return render(
        request,
        "evaluations/deal_detail.html",
        {"deal": deal, "report": report, "section": "overview"},
    )


def _assessment_report(request, deal):
    weights = get_fund_profile(request.user).weight_map()
    benchmark = SectorBenchmark.objects.filter(sector=deal.sector).first()
    report = build_report(deal, weights, benchmark)
    return report, memo_sections(deal, report)


def _assessment_page(request, deal):
    report, memo = _assessment_report(request, deal)
    kind_order = {key: index for index, (key, _label) in enumerate(SOURCE_KINDS)}
    sources = sorted(
        SourceDocument.objects.filter(deal=deal),
        key=lambda document: kind_order.get(document.kind, 99),
    )
    return render(
        request,
        "evaluations/assessment.html",
        {
            "deal": deal,
            "report": report,
            "section": "assessment",
            "memo": memo,
            "sources": sources,
            "openai_configured": bool(django_settings.OPENAI_API_KEY),
            "openai_model": django_settings.OPENAI_MODEL,
        },
    )


@login_required
def deal_assessment(request, pk):
    deal = _owned_deal(request, pk)
    return _assessment_page(request, deal)


@login_required
def deal_assessment_pdf(request, pk):
    deal = _owned_deal(request, pk)
    if deal.evaluation_mode != "ai":
        raise Http404("This deal uses the manual scorecard.")
    report, memo = _assessment_report(request, deal)
    if memo is None:
        raise Http404("No assessment yet.")
    # #region agent log
    try:
        import json
        import time

        with open(
            r"C:\Users\angel\Documents\Projects\companyeval\debug-a6cd56.log",
            "a",
            encoding="utf-8",
        ) as _handle:
            _handle.write(
                json.dumps(
                    {
                        "sessionId": "a6cd56",
                        "runId": "pre-fix",
                        "hypothesisId": "D",
                        "location": "views.py:deal_assessment_pdf",
                        "message": "assessment loaded, rendering pdf",
                        "data": {"deal_id": deal.pk, "memo_is_none": memo is None},
                        "timestamp": int(time.time() * 1000),
                    }
                )
                + "\n"
            )
    except Exception:
        pass
    # #endregion
    try:
        rendered = render_assessment_pdf(deal, report, memo)
    except Exception as exc:
        # #region agent log
        import traceback

        try:
            import json
            import time

            with open(
                r"C:\Users\angel\Documents\Projects\companyeval\debug-a6cd56.log",
                "a",
                encoding="utf-8",
            ) as _handle:
                _handle.write(
                    json.dumps(
                        {
                            "sessionId": "a6cd56",
                            "runId": "pre-fix",
                            "hypothesisId": "D",
                            "location": "views.py:deal_assessment_pdf",
                            "message": "render_assessment_pdf raised",
                            "data": {
                                "error_type": type(exc).__name__,
                                "error": str(exc),
                                "traceback": traceback.format_exc(),
                            },
                            "timestamp": int(time.time() * 1000),
                        }
                    )
                    + "\n"
                )
        except Exception:
            pass
        # #endregion
        raise
    payload = io.BytesIO(rendered)
    return FileResponse(
        payload,
        content_type="application/pdf",
        as_attachment=True,
        filename=assessment_filename(deal.company_name),
    )


@login_required
def deal_generate(request, pk):
    deal = _owned_deal(request, pk)
    if request.method != "POST":
        return redirect("evaluations:deal_assessment", pk=deal.pk)
    if deal.evaluation_mode != "ai":
        messages.error(request, "This deal uses the manual scorecard.")
        return redirect("evaluations:deal_detail", pk=deal.pk)
    try:
        generate_assessment(deal)
    except GenerationError as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Assessment generated.")
    return redirect("evaluations:deal_assessment", pk=deal.pk)


@login_required
def deal_deck(request, pk):
    deal = get_object_or_404(Deal, pk=pk, owner=request.user)
    if not deal.deck:
        raise Http404("No deck attached.")
    return FileResponse(
        deal.deck.open("rb"),
        content_type="application/pdf",
        as_attachment=False,
        filename=f"{deal.company_name}.pdf",
    )


@login_required
def team_section(request, pk):
    deal = _owned_deal(request, pk)
    profile, _created = TeamProfile.objects.get_or_create(deal=deal)
    factors = FACTORS["team"]
    if request.method == "POST":
        form = TeamProfileForm(request.POST, instance=profile)
        founder_formset = FounderFormSet(request.POST, instance=deal)
        score_form = CategoryScoreForm(
            request.POST,
            factors=factors,
            existing=_existing_scores(deal),
            prefix="scores",
        )
        form_valid = form.is_valid()
        founders_valid = founder_formset.is_valid()
        scores_valid = score_form.is_valid()
        if form_valid and founders_valid and scores_valid:
            with transaction.atomic():
                form.save()
                founder_formset.save()
                _save_scores(deal, score_form, factors)
            messages.success(request, "Team saved.")
            return redirect("evaluations:deal_detail", pk=deal.pk)
    else:
        form = TeamProfileForm(instance=profile)
        founder_formset = FounderFormSet(instance=deal)
        score_form = CategoryScoreForm(
            factors=factors,
            existing=_existing_scores(deal),
            prefix="scores",
        )
    return render(
        request,
        "evaluations/section.html",
        _section_context(
            deal,
            "team",
            "Team",
            form,
            score_form,
            founder_formset=founder_formset,
        ),
    )


def _profile_section(request, pk, *, section, title, form_class, profile_model, category):
    deal = _owned_deal(request, pk)
    profile, _created = profile_model.objects.get_or_create(deal=deal)
    factors = FACTORS[category]
    if request.method == "POST":
        form = form_class(request.POST, instance=profile)
        score_form = CategoryScoreForm(
            request.POST,
            factors=factors,
            existing=_existing_scores(deal),
            prefix="scores",
        )
        form_valid = form.is_valid()
        scores_valid = score_form.is_valid()
        if form_valid and scores_valid:
            with transaction.atomic():
                form.save()
                _save_scores(deal, score_form, factors)
            messages.success(request, f"{title} saved.")
            return redirect("evaluations:deal_detail", pk=deal.pk)
    else:
        form = form_class(instance=profile)
        score_form = CategoryScoreForm(
            factors=factors,
            existing=_existing_scores(deal),
            prefix="scores",
        )
    return render(
        request,
        "evaluations/section.html",
        _section_context(deal, section, title, form, score_form),
    )


@login_required
def market_section(request, pk):
    return _profile_section(
        request,
        pk,
        section="market",
        title="Market",
        form_class=MarketProfileForm,
        profile_model=MarketProfile,
        category="market",
    )


@login_required
def product_section(request, pk):
    return _profile_section(
        request,
        pk,
        section="product",
        title="Product",
        form_class=ProductProfileForm,
        profile_model=ProductProfile,
        category="product",
    )


@login_required
def traction_section(request, pk):
    return _profile_section(
        request,
        pk,
        section="traction",
        title="Traction",
        form_class=TractionProfileForm,
        profile_model=TractionProfile,
        category="traction",
    )


@login_required
def terms_section(request, pk):
    deal = _owned_deal(request, pk)
    factors = FACTORS["terms"]
    if request.method == "POST":
        form = TermsForm(request.POST, instance=deal)
        score_form = CategoryScoreForm(
            request.POST,
            factors=factors,
            existing=_existing_scores(deal),
            prefix="scores",
        )
        form_valid = form.is_valid()
        scores_valid = score_form.is_valid()
        if form_valid and scores_valid:
            with transaction.atomic():
                form.save()
                _save_scores(deal, score_form, factors)
            messages.success(request, "Deal terms saved.")
            return redirect("evaluations:deal_detail", pk=deal.pk)
    else:
        form = TermsForm(instance=deal)
        score_form = CategoryScoreForm(
            factors=factors,
            existing=_existing_scores(deal),
            prefix="scores",
        )
    return render(
        request,
        "evaluations/section.html",
        _section_context(deal, "terms", "Deal terms", form, score_form),
    )


@login_required
def fund_settings(request):
    profile = get_fund_profile(request.user)
    if request.method == "POST":
        form = FundSettingsForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Weights saved. Every deal uses them now.")
            return redirect("evaluations:fund_settings")
    else:
        form = FundSettingsForm(instance=profile)
    return render(request, "evaluations/settings.html", {"form": form})


@login_required
def benchmarks(request):
    queryset = SectorBenchmark.objects.in_display_order()
    if request.method == "POST":
        formset = BenchmarkFormSet(request.POST, queryset=queryset, prefix="benchmarks")
        if formset.is_valid():
            formset.save()
            messages.success(request, "Benchmarks saved.")
            return redirect("evaluations:benchmarks")
    else:
        formset = BenchmarkFormSet(queryset=queryset, prefix="benchmarks")
    return render(request, "evaluations/benchmarks.html", {"formset": formset})
