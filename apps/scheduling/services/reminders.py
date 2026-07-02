"""
Email reminders (project plan, phase 1: "email reminders first, SMS/WhatsApp
once the gateway is in place"). Sends via Django's configured EMAIL_BACKEND
(console in dev, SMTP in production) -- no external gateway needed yet.
"""

from django.core.mail import send_mail
from django.conf import settings
from django.urls import reverse

from apps.scheduling.models import Appointment


def build_manage_url(appointment):
    path = reverse("scheduling:appointment_manage", kwargs={"pk": appointment.id})
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def send_appointment_reminder(appointment):
    """
    Sends a reminder email for a single appointment and marks it as sent.
    Returns True if an email was actually sent, False if skipped (no email
    on file) -- callers should treat False as "not applicable", not a failure.
    """
    patient = appointment.patient
    if not patient.email:
        return False

    subject = f"Rappel de rendez-vous — {appointment.provider.clinic.name}"
    manage_url = build_manage_url(appointment)
    body = (
        f"Bonjour {patient.first_name},\n\n"
        f"Ceci est un rappel pour votre rendez-vous :\n"
        f"  Médecin : {appointment.provider.full_name}\n"
        f"  Service : {appointment.service.name if appointment.service else '—'}\n"
        f"  Date : {appointment.scheduled_start:%A %d/%m/%Y à %H:%M}\n"
        f"  Clinique : {appointment.provider.clinic.name}\n\n"
        f"Pour annuler ou reprogrammer ce rendez-vous, suivez ce lien :\n"
        f"{manage_url}\n\n"
        f"À bientôt,\n{appointment.provider.clinic.name}"
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=None,  # falls back to settings.DEFAULT_FROM_EMAIL
        recipient_list=[patient.email],
    )

    appointment.reminder_sent = True
    appointment.save(update_fields=["reminder_sent", "updated_at"])
    return True


def build_waitlist_offer_url(entry):
    path = reverse("scheduling:waitlist_offer_respond", kwargs={"pk": entry.id})
    return f"{settings.SITE_URL.rstrip('/')}{path}"


def send_waitlist_offer_email(entry):
    """
    Sends the "a slot opened up" email for a waitlist offer. Returns True if
    sent, False if skipped (no email on file) -- same not-applicable-not-a-
    failure convention as send_appointment_reminder.
    """
    patient = entry.patient
    if not patient.email:
        return False

    subject = f"Un créneau s'est libéré — {entry.provider.clinic.name}"
    offer_url = build_waitlist_offer_url(entry)
    body = (
        f"Bonjour {patient.first_name},\n\n"
        f"Un créneau s'est libéré avec {entry.provider.full_name} "
        f"le {entry.offered_slot:%A %d/%m/%Y à %H:%M}.\n\n"
        f"Pour accepter ou refuser ce créneau, suivez ce lien :\n"
        f"{offer_url}\n\n"
        f"À bientôt,\n{entry.provider.clinic.name}"
    )

    send_mail(
        subject=subject,
        message=body,
        from_email=None,
        recipient_list=[patient.email],
    )
    return True
