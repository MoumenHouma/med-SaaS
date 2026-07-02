from django import forms

from apps.core.forms import TailwindFormMixin

from .models import Clinic, Provider, Service


class ClinicOnboardingForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Clinic
        fields = ["name", "address", "wilaya", "phone", "email"]


class ProviderForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Provider
        fields = ["first_name", "last_name", "specialty"]


class ServiceForm(TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "average_duration", "price"]
