from datetime import datetime, time, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.scheduling.models import Appointment, WaitlistEntry

pytestmark = pytest.mark.django_db


def _slot_datetime(date, hour, minute=0):
    return timezone.make_aware(datetime.combine(date, time(hour, minute)))


def test_slot_template_creation(slot_template, provider):
    assert slot_template.pk is not None
    assert slot_template.provider == provider


def test_appointment_creation(provider, service, patient, future_date):
    start = _slot_datetime(future_date, 9)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
    )
    assert appointment.pk is not None
    assert appointment.status == Appointment.Status.SCHEDULED


def test_waitlist_entry_creation(provider, service, patient):
    entry = WaitlistEntry.objects.create(patient=patient, provider=provider, service=service)
    assert entry.pk is not None
    assert entry.status == WaitlistEntry.EntryStatus.PENDING


def test_lead_time_days_future_booking(provider, service, patient, future_date):
    start = _slot_datetime(future_date, 9)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
    )
    expected = (future_date - timezone.localdate()).days
    assert expected > 0
    assert appointment.lead_time_days == expected


def test_lead_time_days_same_day_booking(provider, service, patient):
    start = timezone.now() + timedelta(hours=1)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
    )
    assert appointment.lead_time_days == 0


def test_lead_time_days_zero_not_recomputed_on_later_full_save(provider, service, patient):
    """
    Regression for the `if not self.lead_time_days` bug: 0 (same-day booking)
    is falsy, so a later save() with no update_fields restriction (e.g. via
    the Django admin) used to silently recompute it based on the date at
    save time -- corrupting the feature the no-show predictor trains on.
    """
    start = timezone.now() + timedelta(hours=2)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
    )
    assert appointment.lead_time_days == 0

    # Move scheduled_start far into the future in memory, then do a full
    # save() (no update_fields). The old buggy code would recompute
    # lead_time_days to ~20 here; the fix must leave it at 0.
    appointment.scheduled_start = start + timedelta(days=20)
    appointment.scheduled_end = appointment.scheduled_start + timedelta(minutes=30)
    appointment.save()
    appointment.refresh_from_db()

    assert appointment.lead_time_days == 0


def test_appointment_unique_active_slot_constraint(provider, service, patient, future_date):
    start = _slot_datetime(future_date, 9)
    Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            Appointment.objects.create(
                patient=patient,
                provider=provider,
                service=service,
                scheduled_start=start,
                scheduled_end=start + timedelta(minutes=30),
            )


def test_appointment_unique_active_slot_constraint_excludes_cancelled(provider, service, patient, future_date):
    """A cancelled appointment must not block rebooking the same slot."""
    start = _slot_datetime(future_date, 9)
    first = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
    )
    first.status = Appointment.Status.CANCELLED
    first.save(update_fields=["status", "updated_at"])

    second = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
    )
    assert second.pk is not None
