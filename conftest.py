"""
Shared fixtures for the Rendia test suite.

Nearly every model in every app FKs transitively into Clinic, so the
Clinic -> Provider -> Service/SlotTemplate and Patient chain lives here
once instead of being duplicated per app.
"""

from datetime import time, timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.clinics.models import Clinic, ClinicStaff, Provider, Service
from apps.patients.models import Patient
from apps.scheduling.models import SlotTemplate


@pytest.fixture
def future_date():
    """A date safely in the future, so slot/availability tests don't depend on 'today'."""
    return timezone.localdate() + timedelta(days=14)


@pytest.fixture
def clinic(db):
    return Clinic.objects.create(
        name="Clinique Test",
        slug="clinique-test",
        address="1 rue des Frères, Alger",
    )


@pytest.fixture
def provider(clinic):
    return Provider.objects.create(
        clinic=clinic,
        first_name="Amine",
        last_name="Benali",
        specialty="Généraliste",
    )


@pytest.fixture
def service(provider):
    return Service.objects.create(
        provider=provider,
        name="Consultation",
        average_duration=30,
        price="2000.00",
    )


@pytest.fixture
def slot_template(provider, future_date):
    """Covers 09:00-12:00 on future_date's weekday -- six 30-minute slots."""
    return SlotTemplate.objects.create(
        provider=provider,
        day_of_week=future_date.weekday(),
        start_time=time(9, 0),
        end_time=time(12, 0),
    )


@pytest.fixture
def patient(clinic):
    return Patient.objects.create(
        clinic=clinic,
        first_name="Sara",
        last_name="Kaci",
        phone_number="0555111222",
    )


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="staffuser", password="testpass123", email="staff@example.com"
    )


@pytest.fixture
def clinic_staff(user, clinic):
    return ClinicStaff.objects.create(user=user, clinic=clinic, role=ClinicStaff.Role.OWNER)
