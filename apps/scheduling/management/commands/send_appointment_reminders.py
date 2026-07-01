"""
Sends reminder emails for upcoming appointments (see apps.scheduling.services.
reminders). Meant to run on a schedule (cron / management command scheduler);
a simple command is enough for the MVP, Celery/Redis is a phase-2 concern.
"""

from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.scheduling.models import Appointment
from apps.scheduling.services.reminders import send_appointment_reminder


class Command(BaseCommand):
    help = "Send reminder emails for appointments starting within REMINDER_LEAD_HOURS."

    def handle(self, *args, **options):
        now = timezone.now()
        window_end = now + timedelta(hours=settings.REMINDER_LEAD_HOURS)

        due = Appointment.objects.filter(
            status__in=[Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED],
            reminder_sent=False,
            scheduled_start__gte=now,
            scheduled_start__lte=window_end,
        ).select_related("patient", "provider__clinic", "service")

        sent, skipped = 0, 0
        for appointment in due:
            if send_appointment_reminder(appointment):
                sent += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"Reminders sent: {sent}. Skipped (no patient email): {skipped}.")
        )
