from datetime import timedelta

import pytest
from django.utils import timezone

import apps.optimization.services.predictor as predictor_module
from apps.optimization.services.predictor import (
    BASE_NO_SHOW_RATE,
    MIN_TRAINING_SAMPLES,
    heuristic_probability,
    train_model,
)
from apps.patients.models import Patient
from apps.scheduling.models import Appointment

pytestmark = pytest.mark.django_db


class _FakeAppointment:
    """
    heuristic_probability only reads plain attributes off the appointment, so
    a lightweight stand-in avoids fighting Appointment.save()'s own
    lead_time_days auto-computation just to pin an exact value.
    """

    def __init__(self, lead_time_days=0, reminder_sent=False, reminder_acknowledged=False):
        self.lead_time_days = lead_time_days
        self.reminder_sent = reminder_sent
        self.reminder_acknowledged = reminder_acknowledged


def test_heuristic_probability_base_rate():
    assert heuristic_probability(_FakeAppointment(lead_time_days=5)) == pytest.approx(BASE_NO_SHOW_RATE)


def test_heuristic_probability_long_lead_time():
    appt = _FakeAppointment(lead_time_days=15)
    assert heuristic_probability(appt) == pytest.approx(BASE_NO_SHOW_RATE + 0.10)


def test_heuristic_probability_medium_lead_time():
    appt = _FakeAppointment(lead_time_days=10)
    assert heuristic_probability(appt) == pytest.approx(BASE_NO_SHOW_RATE + 0.05)


def test_heuristic_probability_short_lead_time():
    appt = _FakeAppointment(lead_time_days=1)
    assert heuristic_probability(appt) == pytest.approx(BASE_NO_SHOW_RATE - 0.05)


def test_heuristic_probability_reminder_acknowledged():
    appt = _FakeAppointment(lead_time_days=5, reminder_sent=True, reminder_acknowledged=True)
    assert heuristic_probability(appt) == pytest.approx(BASE_NO_SHOW_RATE - 0.08)


def test_heuristic_probability_reminder_sent_not_acknowledged():
    appt = _FakeAppointment(lead_time_days=5, reminder_sent=True, reminder_acknowledged=False)
    assert heuristic_probability(appt) == pytest.approx(BASE_NO_SHOW_RATE - 0.03)


def test_heuristic_probability_clamps_to_upper_bound(monkeypatch):
    # The documented lever combinations never actually reach the [0.01, 0.95]
    # clamp (max realistic value is 0.30), so exercise the clamp directly.
    monkeypatch.setattr(predictor_module, "BASE_NO_SHOW_RATE", 5.0)
    assert predictor_module.heuristic_probability(_FakeAppointment(lead_time_days=5)) == 0.95


def test_heuristic_probability_clamps_to_lower_bound(monkeypatch):
    monkeypatch.setattr(predictor_module, "BASE_NO_SHOW_RATE", -5.0)
    assert predictor_module.heuristic_probability(_FakeAppointment(lead_time_days=5)) == 0.01


def _create_resolved_history(clinic, provider, service, count, status_for_index):
    for i in range(count):
        patient = Patient.objects.create(
            clinic=clinic, first_name="P", last_name=str(i), phone_number=f"0555{i:07d}"
        )
        start = timezone.now() - timedelta(days=1) + timedelta(minutes=i)
        Appointment.objects.create(
            patient=patient,
            provider=provider,
            service=service,
            scheduled_start=start,
            scheduled_end=start + timedelta(minutes=30),
            status=status_for_index(i),
        )


def test_train_model_returns_none_below_min_training_samples(clinic, provider, service):
    _create_resolved_history(
        clinic, provider, service, MIN_TRAINING_SAMPLES - 1, lambda i: Appointment.Status.COMPLETED
    )
    assert train_model(clinic) is None


def test_train_model_returns_none_on_single_class_history(clinic, provider, service):
    _create_resolved_history(
        clinic, provider, service, MIN_TRAINING_SAMPLES, lambda i: Appointment.Status.COMPLETED
    )
    assert train_model(clinic) is None


def test_train_model_returns_fitted_model_with_mixed_classes(clinic, provider, service):
    _create_resolved_history(
        clinic,
        provider,
        service,
        MIN_TRAINING_SAMPLES,
        lambda i: Appointment.Status.NO_SHOW if i % 3 == 0 else Appointment.Status.COMPLETED,
    )
    model = train_model(clinic)
    assert model is not None
