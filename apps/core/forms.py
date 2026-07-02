from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

# Shared across every app's forms (clinics, scheduling, core) so the input
# styling stays in one place instead of drifting across copies.
INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm "
    "placeholder-gray-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 focus:outline-none"
)


class TailwindFormMixin:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES


class RegisterForm(TailwindFormMixin, UserCreationForm):
    email = forms.EmailField(required=True, label="Email")

    class Meta:
        model = User
        fields = ("username", "email", "password1", "password2")

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user
