from django.contrib import admin
from .models import SlotTemplate, Appointment, WaitlistEntry


@admin.register(SlotTemplate)
class SlotTemplateAdmin(admin.ModelAdmin):
    list_display = ("provider", "day_of_week", "start_time", "end_time", "default_slot_duration", "is_active")
    list_filter = ("day_of_week", "is_active", "provider__clinic")
    search_fields = ("provider__first_name", "provider__last_name")
    autocomplete_fields = ["provider"]


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = (
        "patient", "provider", "service", "scheduled_start",
        "status", "no_show_probability", "reminder_sent", "reminder_acknowledged",
    )
    list_filter = ("status", "reminder_sent", "reminder_acknowledged", "provider__clinic")
    search_fields = ("patient__first_name", "patient__last_name", "patient__phone_number")
    autocomplete_fields = ["patient", "provider", "service"]
    date_hierarchy = "scheduled_start"
    readonly_fields = (
        "lead_time_days", "no_show_probability", "created_at", "updated_at"
    )
    fieldsets = (
        ("Rendez-vous", {
            "fields": ("patient", "provider", "service", "status"),
        }),
        ("Horaires", {
            "fields": ("scheduled_start", "scheduled_end", "actual_start", "actual_end"),
        }),
        ("Optimisation (calculé automatiquement)", {
            "fields": ("no_show_probability", "lead_time_days"),
            "classes": ("collapse",),
        }),
        ("Rappels", {
            "fields": ("reminder_sent", "reminder_acknowledged"),
        }),
        ("Notes", {
            "fields": ("notes",),
        }),
        ("Métadonnées", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",),
        }),
    )


@admin.register(WaitlistEntry)
class WaitlistEntryAdmin(admin.ModelAdmin):
    list_display = ("patient", "provider", "service", "urgency", "priority_score", "status", "created_at")
    list_filter = ("status", "urgency", "provider__clinic")
    search_fields = ("patient__first_name", "patient__last_name")
    autocomplete_fields = ["patient", "provider", "service"]
    readonly_fields = ("priority_score", "offer_made_at", "created_at", "updated_at")
    ordering = ("-priority_score", "created_at")
