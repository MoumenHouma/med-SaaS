import uuid

from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.utils.text import slugify
from django.views.generic import CreateView, TemplateView

from .forms import ClinicOnboardingForm, ProviderForm, ServiceForm
from .models import Clinic, ClinicStaff, Provider


class ClinicStaffRequiredMixin(LoginRequiredMixin):
    """
    Ensures the logged-in user has completed onboarding (has a ClinicStaff
    profile) and exposes the clinic they belong to as `self.clinic`.
    Unauthenticated users still get the normal LoginRequiredMixin redirect.
    """

    clinic = None

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            if not hasattr(request.user, "clinic_staff_profile"):
                return redirect("clinics:onboarding")
            self.clinic = request.user.clinic_staff_profile.clinic
        return super().dispatch(request, *args, **kwargs)


class OnboardingView(LoginRequiredMixin, CreateView):
    """
    First-run flow: the logged-in user creates their clinic and becomes
    its owner. Redirects straight to the dashboard if they already have one.
    """

    model = Clinic
    form_class = ClinicOnboardingForm
    template_name = "clinics/onboarding_form.html"

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated and hasattr(request.user, "clinic_staff_profile"):
            return redirect("clinics:dashboard")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        clinic = form.save(commit=False)
        base_slug = slugify(clinic.name) or "clinique"
        slug = base_slug
        while Clinic.objects.filter(slug=slug).exists():
            slug = f"{base_slug}-{uuid.uuid4().hex[:6]}"
        clinic.slug = slug
        clinic.save()

        ClinicStaff.objects.create(
            user=self.request.user,
            clinic=clinic,
            role=ClinicStaff.Role.OWNER,
        )
        self.object = clinic
        return redirect("clinics:dashboard")


class DashboardView(ClinicStaffRequiredMixin, TemplateView):
    template_name = "clinics/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["clinic"] = self.clinic
        context["providers"] = self.clinic.providers.prefetch_related("services").order_by(
            "last_name", "first_name"
        )
        return context


class ProviderCreateView(ClinicStaffRequiredMixin, CreateView):
    model = Provider
    form_class = ProviderForm
    template_name = "clinics/provider_form.html"

    def form_valid(self, form):
        provider = form.save(commit=False)
        provider.clinic = self.clinic
        provider.save()
        return redirect("clinics:dashboard")


class ServiceCreateView(ClinicStaffRequiredMixin, CreateView):
    form_class = ServiceForm
    template_name = "clinics/service_form.html"

    def get_provider(self):
        return get_object_or_404(Provider, id=self.kwargs["provider_id"], clinic=self.clinic)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["provider"] = self.get_provider()
        return context

    def form_valid(self, form):
        service = form.save(commit=False)
        service.provider = self.get_provider()
        service.save()
        return redirect("clinics:dashboard")
