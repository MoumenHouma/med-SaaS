from datetime import timedelta

import pytest
from django.utils import timezone

from apps.optimization.services.analytics import bottleneck_breakdown
from apps.patients.models import Patient
from apps.scheduling.models import Appointment

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
