from django import forms

from .models import Clinic, Provider, Service


class ClinicOnboardingForm(forms.ModelForm):
    class Meta:
        model = Clinic
        fields = ["name", "address", "wilaya", "phone", "email"]


class ProviderForm(forms.ModelForm):
    class Meta:
        model = Provider
        fields = ["first_name", "last_name", "specialty"]


class ServiceForm(forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "average_duration", "price"]
