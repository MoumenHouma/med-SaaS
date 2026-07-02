"""
Dynamic waitlist matching (project plan, section 2.3): a small bipartite-
matching problem, distinct from and much simpler than the full slot
allocation MIP. When a slot is available, score every pending WaitlistEntry
for that provider and offer it to the best match.
"""

from datetime import timedelta

from django.db.models import Q
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


def find_best_match(provider, service=None, now=None):
    """
    Returns the highest-scoring PENDING WaitlistEntry for this provider (and,
    if given, this service or a service-agnostic entry), or None if there are
    no pending entries. Scores are recomputed fresh rather than read from the
    cached priority_score field, since wait time changes continuously.
    """
    candidates = WaitlistEntry.objects.filter(
        provider=provider, status=WaitlistEntry.EntryStatus.PENDING
    )
    if service is not None:
        candidates = candidates.filter(Q(service=service) | Q(service__isnull=True))

    best_entry, best_score = None, None
    for entry in candidates:
        score = compute_priority_score(entry, now=now)
        if best_score is None or score > best_score:
            best_entry, best_score = entry, score
    return best_entry


def expire_stale_offers(expiry_hours, now=None):
    """Reverts OFFERED entries left unanswered past expiry_hours to EXPIRED."""
    now = now or timezone.now()
    cutoff = now - timedelta(hours=expiry_hours)
    return WaitlistEntry.objects.filter(
        status=WaitlistEntry.EntryStatus.OFFERED, offer_made_at__lt=cutoff
    ).update(status=WaitlistEntry.EntryStatus.EXPIRED)
