from django import forms


class PatientContactForm(forms.Form):
    first_name = forms.CharField(max_length=100, label="Prénom")
    last_name = forms.CharField(max_length=100, label="Nom")
    phone_number = forms.CharField(max_length=20, label="Téléphone")
    email = forms.EmailField(
        required=False,
        label="Email",
        help_text="Optionnel — utilisé pour vous envoyer un rappel avant le rendez-vous.",
    )
