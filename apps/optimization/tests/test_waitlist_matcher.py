from datetime import timedelta

import pytest
from django.utils import timezone

from apps.optimization.services.waitlist_matcher import (
    compute_priority_score,
    expire_stale_offers,
    find_best_match,
)
from apps.patients.models import Patient
from apps.scheduling.models import WaitlistEntry

pytestmark = pytest.mark.django_db


def _make_patient(clinic, suffix):
    return Patient.objects.create(
        clinic=clinic, first_name="P", last_name=suffix, phone_number=f"0555000{suffix}"
    )


def test_compute_priority_score_scales_with_urgency(clinic, provider):
    low = WaitlistEntry.objects.create(patient=_make_patient(clinic, "1"), provider=provider, urgency=1)
    high = WaitlistEntry.objects.create(patient=_make_patient(clinic, "2"), provider=provider, urgency=3)
    assert compute_priority_score(high) > compute_priority_score(low)


def test_compute_priority_score_increases_with_wait_time(clinic, provider):
    entry = WaitlistEntry.objects.create(patient=_make_patient(clinic, "1"), provider=provider, urgency=1)
    now = timezone.now()
    score_now = compute_priority_score(entry, now=now)
    score_later = compute_priority_score(entry, now=now + timedelta(hours=10))
    assert score_later > score_now


def test_find_best_match_prefers_higher_urgency(clinic, provider, service):
    WaitlistEntry.objects.create(
        patient=_make_patient(clinic, "1"), provider=provider, service=service, urgency=1
    )
    urgent = WaitlistEntry.objects.create(
        patient=_make_patient(clinic, "2"), provider=provider, service=service, urgency=3
    )
    assert find_best_match(provider, service=service) == urgent


def test_find_best_match_includes_service_agnostic_entries(clinic, provider, service):
    agnostic = WaitlistEntry.objects.create(
        patient=_make_patient(clinic, "1"), provider=provider, service=None, urgency=2
    )
    assert find_best_match(provider, service=service) == agnostic


def test_find_best_match_ignores_non_pending_entries(clinic, provider, service):
    WaitlistEntry.objects.create(
        patient=_make_patient(clinic, "1"),
        provider=provider,
        service=service,
        urgency=3,
        status=WaitlistEntry.EntryStatus.OFFERED,
    )
    assert find_best_match(provider, service=service) is None


def test_find_best_match_returns_none_without_candidates(provider, service):
    assert find_best_match(provider, service=service) is None


def test_expire_stale_offers(clinic, provider):
    stale = WaitlistEntry.objects.create(
        patient=_make_patient(clinic, "1"),
        provider=provider,
        status=WaitlistEntry.EntryStatus.OFFERED,
        offer_made_at=timezone.now() - timedelta(hours=48),
    )
    fresh = WaitlistEntry.objects.create(
        patient=_make_patient(clinic, "2"),
        provider=provider,
        status=WaitlistEntry.EntryStatus.OFFERED,
        offer_made_at=timezone.now() - timedelta(hours=1),
    )
    expired_count = expire_stale_offers(expiry_hours=24)
    assert expired_count == 1
    stale.refresh_from_db()
    fresh.refresh_from_db()
    assert stale.status == WaitlistEntry.EntryStatus.EXPIRED
    assert fresh.status == WaitlistEntry.EntryStatus.OFFERED
