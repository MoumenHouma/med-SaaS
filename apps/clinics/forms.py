from django import forms

from .models import Clinic, Provider, Service

INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm "
    "placeholder-gray-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 focus:outline-none"
)


class _TailwindFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES


class ClinicOnboardingForm(_TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Clinic
        fields = ["name", "address", "wilaya", "phone", "email"]


class ProviderForm(_TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Provider
        fields = ["first_name", "last_name", "specialty"]


class ServiceForm(_TailwindFormMixin, forms.ModelForm):
    class Meta:
        model = Service
        fields = ["name", "average_duration", "price"]
