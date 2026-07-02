from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.optimization.models import OptimizationRun
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, WaitlistEntry

pytestmark = pytest.mark.django_db


def test_run_no_show_prediction_empty_db():
    call_command("run_no_show_prediction")
    assert OptimizationRun.objects.count() == 0


def test_run_no_show_prediction_with_one_appointment(provider, service, patient):
    start = timezone.now() + timedelta(days=3)
    Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
    )
    call_command("run_no_show_prediction")

    run = OptimizationRun.objects.get()
    assert run.run_status == OptimizationRun.RunStatus.SUCCESS

    appointment = Appointment.objects.get()
    assert appointment.no_show_probability is not None


def test_match_waitlist_offers_empty_db():
    call_command("match_waitlist_offers")
    assert OptimizationRun.objects.count() == 0


def test_match_waitlist_offers_offers_available_slot(clinic, provider, service, slot_template):
    waiting_patient = Patient.objects.create(
        clinic=clinic, first_name="W", last_name="L", phone_number="0555321321"
    )
    entry = WaitlistEntry.objects.create(patient=waiting_patient, provider=provider, service=service)

    call_command("match_waitlist_offers")

    entry.refresh_from_db()
    assert entry.status == WaitlistEntry.EntryStatus.OFFERED
    assert entry.offered_slot is not None
    run = OptimizationRun.objects.get()
    assert run.run_type == OptimizationRun.RunType.WAITLIST_MATCHING
    assert run.run_status == OptimizationRun.RunStatus.SUCCESS
    assert run.results["offers_made"] == 1
