from django.urls import path

from evaluations import views

app_name = "evaluations"

urlpatterns = [
    path("", views.pipeline, name="pipeline"),
    path("deals/new/", views.deal_create, name="deal_create"),
    path("deals/<int:pk>/", views.deal_detail, name="deal_detail"),
    path("deals/<int:pk>/edit/", views.deal_edit, name="deal_edit"),
    path("deals/<int:pk>/delete/", views.deal_delete, name="deal_delete"),
    path("deals/<int:pk>/deck/", views.deal_deck, name="deal_deck"),
    path("deals/<int:pk>/assessment/", views.deal_assessment, name="deal_assessment"),
    path("deals/<int:pk>/assessment.pdf", views.deal_assessment_pdf, name="deal_assessment_pdf"),
    path("deals/<int:pk>/generate/", views.deal_generate, name="deal_generate"),
    path("deals/<int:pk>/team/", views.team_section, name="team_section"),
    path("deals/<int:pk>/market/", views.market_section, name="market_section"),
    path("deals/<int:pk>/product/", views.product_section, name="product_section"),
    path("deals/<int:pk>/traction/", views.traction_section, name="traction_section"),
    path("deals/<int:pk>/terms/", views.terms_section, name="terms_section"),
    path("settings/", views.fund_settings, name="fund_settings"),
    path("benchmarks/", views.benchmarks, name="benchmarks"),
]
