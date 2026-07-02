from django import forms

INPUT_CLASSES = (
    "block w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm "
    "placeholder-gray-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-500/30 focus:outline-none"
)


class PatientContactForm(forms.Form):
    first_name = forms.CharField(max_length=100, label="Prénom")
    last_name = forms.CharField(max_length=100, label="Nom")
    phone_number = forms.CharField(max_length=20, label="Téléphone")
    email = forms.EmailField(
        required=False,
        label="Email",
        help_text="Optionnel — utilisé pour vous envoyer un rappel avant le rendez-vous.",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES


class WaitlistJoinForm(forms.Form):
    first_name = forms.CharField(max_length=100, label="Prénom")
    last_name = forms.CharField(max_length=100, label="Nom")
    phone_number = forms.CharField(max_length=20, label="Téléphone")
    email = forms.EmailField(
        required=False,
        label="Email",
        help_text="Optionnel — utilisé pour vous prévenir si un créneau se libère.",
    )
    urgency = forms.ChoiceField(
        choices=[(1, "Normal"), (2, "Prioritaire"), (3, "Urgent")],
        initial=1,
        label="Urgence",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs["class"] = INPUT_CLASSES
