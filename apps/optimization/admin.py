from django.contrib import admin
from .models import OptimizationRun


@admin.register(OptimizationRun)
class OptimizationRunAdmin(admin.ModelAdmin):
    list_display = (
        "provider", "run_type", "target_date", "run_status",
        "duration_ms", "created_at"
    )
    list_filter = ("run_type", "run_status", "provider__clinic")
    search_fields = ("provider__first_name", "provider__last_name")
    date_hierarchy = "target_date"
    readonly_fields = (
        "created_at", "updated_at", "duration_ms",
        "parameters", "results", "error_message"
    )
    fieldsets = (
        ("Run Info", {
            "fields": ("provider", "run_type", "target_date", "run_status"),
        }),
        ("Performance", {
            "fields": ("duration_ms",),
        }),
        ("Parameters & Results", {
            "fields": ("parameters", "results"),
            "classes": ("collapse",),
        }),
        ("Error Details", {
            "fields": ("error_message",),
            "classes": ("collapse",),
        }),
        ("Metadata", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )
