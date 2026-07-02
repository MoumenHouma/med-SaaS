from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from apps.optimization.services.analytics import bottleneck_breakdown, no_show_trend, weekly_utilization
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, SlotTemplate

pytestmark = pytest.mark.django_db


def _make_patient(clinic, suffix):
    return Patient.objects.create(
        clinic=clinic, first_name="P", last_name=suffix, phone_number=f"0555999{suffix}"
    )


def test_bottleneck_breakdown_ranks_by_count(clinic, provider, service):
    start = timezone.now() - timedelta(days=1)
    for i, reason in enumerate(
        [
            Appointment.DelayReason.LATE_ARRIVAL,
            Appointment.DelayReason.LATE_ARRIVAL,
            Appointment.DelayReason.PROVIDER_OVERRUN,
        ]
    ):
        Appointment.objects.create(
            patient=_make_patient(clinic, str(i)),
            provider=provider,
            service=service,
            scheduled_start=start + timedelta(minutes=i),
            scheduled_end=start + timedelta(minutes=i + 30),
            status=Appointment.Status.COMPLETED,
            delay_reason=reason,
        )

    breakdown = bottleneck_breakdown(clinic)
    assert breakdown[0]["delay_reason"] == Appointment.DelayReason.LATE_ARRIVAL
    assert breakdown[0]["count"] == 2
    assert breakdown[0]["label"] == "Retard patient"
    assert breakdown[1]["delay_reason"] == Appointment.DelayReason.PROVIDER_OVERRUN
    assert breakdown[1]["count"] == 1


def test_bottleneck_breakdown_excludes_appointments_without_a_delay_reason(clinic, provider, service):
    start = timezone.now() - timedelta(days=1)
    Appointment.objects.create(
        patient=_make_patient(clinic, "1"),
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        status=Appointment.Status.COMPLETED,
    )
    assert bottleneck_breakdown(clinic) == []


def test_bottleneck_breakdown_respects_since_window(clinic, provider, service):
    old_start = timezone.now() - timedelta(days=60)
    Appointment.objects.create(
        patient=_make_patient(clinic, "1"),
        provider=provider,
        service=service,
        scheduled_start=old_start,
        scheduled_end=old_start + timedelta(minutes=30),
        status=Appointment.Status.COMPLETED,
        delay_reason=Appointment.DelayReason.LATE_ARRIVAL,
    )
    assert bottleneck_breakdown(clinic) == []


def _next_monday():
    today = timezone.localdate()
    return today + timedelta(days=7 - today.weekday())


def test_weekly_utilization_computes_percentage(clinic, provider, service):
    week_start = _next_monday()
    SlotTemplate.objects.create(
        provider=provider, day_of_week=week_start.weekday(), start_time=time(9, 0), end_time=time(12, 0)
    )
    booking_start = timezone.make_aware(datetime.combine(week_start, time(9, 0)))
    Appointment.objects.create(
        patient=_make_patient(clinic, "1"),
        provider=provider,
        service=service,
        scheduled_start=booking_start,
        scheduled_end=booking_start + timedelta(minutes=30),
    )
    # 30 booked minutes / 180 capacity minutes (09:00-12:00) = 16.7%
    assert weekly_utilization(clinic, week_start=week_start) == pytest.approx(16.7, abs=0.1)


def test_weekly_utilization_zero_capacity_returns_zero(clinic):
    assert weekly_utilization(clinic, week_start=_next_monday()) == 0.0


def test_weekly_utilization_excludes_cancelled_appointments(clinic, provider, service):
    week_start = _next_monday()
    SlotTemplate.objects.create(
        provider=provider, day_of_week=week_start.weekday(), start_time=time(9, 0), end_time=time(12, 0)
    )
    booking_start = timezone.make_aware(datetime.combine(week_start, time(9, 0)))
    Appointment.objects.create(
        patient=_make_patient(clinic, "1"),
        provider=provider,
        service=service,
        scheduled_start=booking_start,
        scheduled_end=booking_start + timedelta(minutes=30),
        status=Appointment.Status.CANCELLED,
    )
    assert weekly_utilization(clinic, week_start=week_start) == 0.0


def test_no_show_trend_computes_rate_for_current_week(clinic, provider, service):
    today = timezone.localdate()
    current_week_start = today - timedelta(days=today.weekday())
    start = timezone.make_aware(datetime.combine(current_week_start, time(9, 0)))
    Appointment.objects.create(
        patient=_make_patient(clinic, "1"),
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=30),
        status=Appointment.Status.NO_SHOW,
    )
    Appointment.objects.create(
        patient=_make_patient(clinic, "2"),
        provider=provider,
        service=service,
        scheduled_start=start + timedelta(hours=1),
        scheduled_end=start + timedelta(hours=1, minutes=30),
        status=Appointment.Status.COMPLETED,
    )
    trend = no_show_trend(clinic, weeks=1, today=today)
    assert len(trend) == 1
    assert trend[0][1] == 50.0


def test_no_show_trend_week_with_no_resolved_appointments_is_zero(clinic):
    trend = no_show_trend(clinic, weeks=1)
    assert trend[0][1] == 0.0


def test_no_show_trend_returns_one_entry_per_week_oldest_first(clinic):
    today = timezone.localdate()
    current_week_start = today - timedelta(days=today.weekday())
    expected_labels = [
        (current_week_start - timedelta(weeks=i)).strftime("%d/%m") for i in (2, 1, 0)
    ]
    trend = no_show_trend(clinic, weeks=3, today=today)
    assert [label for label, _rate in trend] == expected_labels
