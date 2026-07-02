"""
Dynamic waitlist matching support (project plan, section 2.3). The actual
demand-to-slot assignment is the CP-SAT allocator in
apps.optimization.services.scheduler; this module covers the pieces around
it -- priority scoring (used both as the allocator's urgency/wait-time input
and as a cached ranking field) and offer expiry.
"""

from datetime import timedelta

from django.utils import timezone

from apps.scheduling.models import WaitlistEntry

# Wait time contributes at most this many "hours" worth of score, so a very
# old entry can't outrank urgency entirely -- urgency is still the primary
# signal (each level is worth 100 points, ten days' wait is worth 240).
MAX_WAIT_HOURS_CONTRIBUTION = 240


def compute_priority_score(entry, now=None):
    """
    Higher score = higher priority. Combines urgency (dominant factor) with
    time spent waiting (tie-breaker among entries of the same urgency).
    """
    now = now or timezone.now()
    wait_hours = (now - entry.created_at).total_seconds() / 3600
    return round(entry.urgency * 100 + min(wait_hours, MAX_WAIT_HOURS_CONTRIBUTION), 2)


def expire_stale_offers(expiry_hours, now=None):
    """Reverts OFFERED entries left unanswered past expiry_hours to EXPIRED."""
    now = now or timezone.now()
    cutoff = now - timedelta(hours=expiry_hours)
    return WaitlistEntry.objects.filter(
        status=WaitlistEntry.EntryStatus.OFFERED, offer_made_at__lt=cutoff
    ).update(status=WaitlistEntry.EntryStatus.EXPIRED)
