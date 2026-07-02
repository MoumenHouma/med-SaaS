import pytest

from apps.clinics.models import ClinicStaff

pytestmark = pytest.mark.django_db


def test_clinic_creation(clinic):
    assert clinic.pk is not None
    assert clinic.name == "Clinique Test"
    assert clinic.is_active is True


def test_provider_creation(provider, clinic):
    assert provider.pk is not None
    assert provider.clinic == clinic
    assert provider.full_name == f"Dr. {provider.first_name} {provider.last_name}"


def test_service_creation(service, provider):
    assert service.pk is not None
    assert service.provider == provider
    assert service.average_duration == 30


def test_clinic_staff_creation(clinic_staff, user, clinic):
    assert clinic_staff.pk is not None
    assert clinic_staff.user == user
    assert clinic_staff.clinic == clinic
    assert clinic_staff.role == ClinicStaff.Role.OWNER
    assert user.clinic_staff_profile == clinic_staff
