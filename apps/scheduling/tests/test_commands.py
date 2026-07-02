from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from apps.patients.models import Patient
from apps.scheduling.models import Appointment

pytestmark = pytest.mark.django_db


def test_send_appointment_reminders_empty_db():
    call_command("send_appointment_reminders")
    assert Appointment.objects.count() == 0


def test_send_appointment_reminders_sends_for_due_appointment(provider, service, clinic):
    patient = Patient.objects.create(
        clinic=clinic,
        first_name="Sara",
        last_name="K",
        phone_number="0555777888",
        email="sara@example.com",
    )
    start = timezone.now() + timedelta(hours=2)  # inside the default 24h REMINDER_LEAD_HOURS window
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
    )
    call_command("send_appointment_reminders")
    appointment.refresh_from_db()
    assert appointment.reminder_sent is True
