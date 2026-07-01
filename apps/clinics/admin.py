from django.contrib import admin
from .models import Clinic, ClinicStaff, Provider, Service


class ProviderInline(admin.TabularInline):
    model = Provider
    extra = 0
    fields = ("first_name", "last_name", "specialty", "is_active")
    show_change_link = True


class ServiceInline(admin.TabularInline):
    model = Service
    extra = 0
    fields = ("name", "average_duration", "price", "is_active")


@admin.register(Clinic)
class ClinicAdmin(admin.ModelAdmin):
    list_display = ("name", "wilaya", "subscription_tier", "is_active", "created_at")
    list_filter = ("subscription_tier", "is_active", "wilaya")
    search_fields = ("name", "wilaya", "email")
    prepopulated_fields = {"slug": ("name",)}
    inlines = [ProviderInline]
    date_hierarchy = "created_at"


@admin.register(Provider)
class ProviderAdmin(admin.ModelAdmin):
    list_display = ("full_name", "specialty", "clinic", "is_active", "created_at")
    list_filter = ("specialty", "is_active", "clinic")
    search_fields = ("first_name", "last_name", "specialty")
    inlines = [ServiceInline]
    autocomplete_fields = ["clinic"]


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "provider", "average_duration", "price", "is_active")
    list_filter = ("is_active", "provider__specialty")
    search_fields = ("name", "provider__last_name")


@admin.register(ClinicStaff)
class ClinicStaffAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "clinic", "provider", "is_active")
    list_filter = ("role", "is_active", "clinic")
    search_fields = ("user__username", "user__email")
    autocomplete_fields = ["user", "clinic", "provider"]
