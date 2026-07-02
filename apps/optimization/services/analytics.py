"""
Dashboard analytics (project plan, section 2.4 and the MVP feature list):
Pareto/bottleneck delay analytics, provider utilization, and no-show trend.
Read-only aggregations over Appointment history -- no ORM writes here.
"""

from datetime import datetime, timedelta

from django.db.models import Count
from django.utils import timezone

from apps.scheduling.models import Appointment, SlotTemplate


def bottleneck_breakdown(clinic, since=None):
    """
    Count of resolved appointments per delay_reason, most common first --
    the Pareto ranking of what's actually causing delays at this clinic.
    """
    since = since or (timezone.now() - timedelta(days=30))
    rows = list(
        Appointment.objects.filter(provider__clinic=clinic, scheduled_start__gte=since)
        .exclude(delay_reason="")
        .values("delay_reason")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    for row in rows:
        row["label"] = Appointment.DelayReason(row["delay_reason"]).label
    return rows


_ACTIVE_STATUSES_EXCLUDED_FROM_UTILIZATION = [Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW]


def weekly_utilization(clinic, week_start=None):
    """
    Booked appointment-minutes / SlotTemplate capacity-minutes for the week
    starting week_start (defaults to the current week's Monday), as a
    percentage capped at 100. Capacity is the sum of each active
    SlotTemplate's weekly window -- the same rule-based capacity
    get_available_slots already relies on, not a day-specific override.
    """
    week_start = week_start or (timezone.localdate() - timedelta(days=timezone.localdate().weekday()))
    week_end = week_start + timedelta(days=7)

    appointments = Appointment.objects.filter(
        provider__clinic=clinic,
        scheduled_start__date__gte=week_start,
        scheduled_start__date__lt=week_end,
    ).exclude(status__in=_ACTIVE_STATUSES_EXCLUDED_FROM_UTILIZATION)
    booked_minutes = sum(
        (appt.scheduled_end - appt.scheduled_start).total_seconds() / 60 for appt in appointments
    )

    capacity_minutes = 0
    for template in SlotTemplate.objects.filter(provider__clinic=clinic, is_active=True):
        start = datetime.combine(week_start, template.start_time)
        end = datetime.combine(week_start, template.end_time)
        capacity_minutes += (end - start).total_seconds() / 60

    if capacity_minutes == 0:
        return 0.0
    return round(min(booked_minutes / capacity_minutes * 100, 100), 1)


def no_show_trend(clinic, weeks=8, today=None):
    """
    No-show rate per week over the trailing `weeks` weeks (oldest first), as
    [(week_label, rate), ...]. Rate is no_show / (no_show + completed) for
    that week -- appointments with no resolved outcome yet aren't counted.
    """
    today = today or timezone.localdate()
    current_week_start = today - timedelta(days=today.weekday())
    resolved_statuses = [Appointment.Status.COMPLETED, Appointment.Status.NO_SHOW]

    trend = []
    for i in range(weeks - 1, -1, -1):
        week_start = current_week_start - timedelta(weeks=i)
        week_end = week_start + timedelta(days=7)
        qs = Appointment.objects.filter(
            provider__clinic=clinic,
            scheduled_start__date__gte=week_start,
            scheduled_start__date__lt=week_end,
            status__in=resolved_statuses,
        )
        total = qs.count()
        no_shows = qs.filter(status=Appointment.Status.NO_SHOW).count()
        rate = round(no_shows / total * 100, 1) if total else 0.0
        trend.append((week_start.strftime("%d/%m"), rate))
    return trend
