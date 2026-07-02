from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.optimization.models import OptimizationRun
from apps.scheduling.models import Appointment

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
