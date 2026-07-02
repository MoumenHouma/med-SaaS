import pytest
from django.db import IntegrityError, transaction

from apps.patients.models import Patient

pytestmark = pytest.mark.django_db


def test_patient_creation(patient, clinic):
    assert patient.pk is not None
    assert patient.clinic == clinic
    assert patient.full_name == f"{patient.first_name} {patient.last_name}"


def test_patient_unique_together_clinic_phone_number(patient, clinic):
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Patient.objects.create(
                clinic=clinic,
                first_name="Autre",
                last_name="Patient",
                phone_number=patient.phone_number,
            )
