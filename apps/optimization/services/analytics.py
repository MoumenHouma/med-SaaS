"""
Dashboard analytics (project plan, section 2.4 and the MVP feature list):
Pareto/bottleneck delay analytics, provider utilization, and no-show trend.
Read-only aggregations over Appointment history -- no ORM writes here.
"""

from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from apps.scheduling.models import Appointment


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
