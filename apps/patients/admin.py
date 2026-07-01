from django.contrib import admin
from .models import Patient


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = ("full_name", "phone_number", "email", "clinic", "clinic_ref", "is_active", "created_at")
    list_filter = ("clinic", "is_active")
    search_fields = ("first_name", "last_name", "phone_number", "email", "clinic_ref")
    autocomplete_fields = ["clinic"]
    date_hierarchy = "created_at"
    readonly_fields = ("created_at", "updated_at")
