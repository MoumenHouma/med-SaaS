from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from apps.scheduling.models import Appointment, SlotTemplate
from apps.scheduling.services.availability import get_available_slots

pytestmark = pytest.mark.django_db


def _slot_datetime(date, hour, minute=0):
    return timezone.make_aware(datetime.combine(date, time(hour, minute)))


def test_respects_slot_template_window(provider, service, slot_template, future_date):
    slots = get_available_slots(provider, service, future_date)
    assert slots

    first = _slot_datetime(future_date, 9)
    last_start = _slot_datetime(future_date, 12) - timedelta(minutes=service.average_duration)
    assert slots[0] == first
    assert slots[-1] == last_start
    assert all(first <= s <= last_start for s in slots)


def test_excludes_overlapping_active_appointment(provider, service, slot_template, patient, future_date):
    busy_start = _slot_datetime(future_date, 9)
    Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=busy_start,
        scheduled_end=busy_start + timedelta(minutes=service.average_duration),
    )
    slots = get_available_slots(provider, service, future_date)
    assert busy_start not in slots


def test_includes_slot_freed_by_cancelled_appointment(provider, service, slot_template, patient, future_date):
    busy_start = _slot_datetime(future_date, 9)
    Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=busy_start,
        scheduled_end=busy_start + timedelta(minutes=service.average_duration),
        status=Appointment.Status.CANCELLED,
    )
    slots = get_available_slots(provider, service, future_date)
    assert busy_start in slots


def test_excludes_past_times(provider, service):
    # A date entirely in the past, so every generated slot is guaranteed to be
    # before "now" regardless of what time of day the test happens to run at.
    yesterday = timezone.localdate() - timedelta(days=1)
    SlotTemplate.objects.create(
        provider=provider,
        day_of_week=yesterday.weekday(),
        start_time=time(0, 0),
        end_time=time(23, 0),
    )
    slots = get_available_slots(provider, service, yesterday)
    assert slots == []


def test_exclude_appointment_id_lets_own_slot_reappear(provider, service, slot_template, patient, future_date):
    start = _slot_datetime(future_date, 9)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
    )
    assert start not in get_available_slots(provider, service, future_date)
    assert start in get_available_slots(
        provider, service, future_date, exclude_appointment_id=appointment.id
    )
