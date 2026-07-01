"""
Phase 1 rule-based slot generator.

Walks a provider's active weekly SlotTemplate rows for the given date's
weekday and yields service-duration-sized slots that don't overlap an
existing (non-cancelled) appointment. This is deliberately the simple
heuristic called for in the project plan — the MIP/CP-SAT optimizer
replaces this later without changing the call signature.
"""

from datetime import datetime, timedelta

from django.utils import timezone

from apps.scheduling.models import Appointment, SlotTemplate


def get_available_slots(provider, service, date, exclude_appointment_id=None):
    duration = timedelta(minutes=service.average_duration)
    templates = SlotTemplate.objects.filter(
        provider=provider, day_of_week=date.weekday(), is_active=True
    )

    busy = Appointment.objects.filter(
        provider=provider, scheduled_start__date=date
    ).exclude(status__in=[Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW])
    if exclude_appointment_id:
        busy = busy.exclude(id=exclude_appointment_id)
    busy_intervals = [(a.scheduled_start, a.scheduled_end) for a in busy]

    now = timezone.now()
    slots = []
    for template in templates:
        current = timezone.make_aware(datetime.combine(date, template.start_time))
        window_end = timezone.make_aware(datetime.combine(date, template.end_time))
        while current + duration <= window_end:
            slot_end = current + duration
            overlaps = any(current < b_end and slot_end > b_start for b_start, b_end in busy_intervals)
            if current > now and not overlaps:
                slots.append(current)
            current += duration

    return slots
