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
    assert run.results["demands_considered"] == 1
    assert run.results["slots_considered"] > 0
    assert run.results["objective_value"] > 0


def test_match_waitlist_offers_fills_multiple_slots_in_one_run(clinic, provider, service, slot_template):
    """
    Regression for the greedy predecessor, which only ever made at most one
    offer per service per run. The CP-SAT allocator jointly considers every
    pending entry against every available slot in the lookahead window, so
    two pending entries for a provider with multiple open slots should both
    get offers from a single command run.
    """
    low = WaitlistEntry.objects.create(
        patient=Patient.objects.create(clinic=clinic, first_name="A", last_name="1", phone_number="0555000001"),
        provider=provider,
        service=service,
        urgency=1,
    )
    high = WaitlistEntry.objects.create(
        patient=Patient.objects.create(clinic=clinic, first_name="B", last_name="2", phone_number="0555000002"),
        provider=provider,
        service=service,
        urgency=3,
    )

    call_command("match_waitlist_offers")

    low.refresh_from_db()
    high.refresh_from_db()
    assert low.status == WaitlistEntry.EntryStatus.OFFERED
    assert high.status == WaitlistEntry.EntryStatus.OFFERED
    assert low.offered_slot != high.offered_slot
    # the more urgent entry gets the earlier of the two slots
    assert high.offered_slot < low.offered_slot
