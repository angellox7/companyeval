from django.apps import AppConfig


class EvaluationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "evaluations"

    def ready(self):
        from django.contrib import admin

        admin.site.site_header = "Companyeval"
        admin.site.site_title = "Companyeval"
        admin.site.index_title = "Inspection"
