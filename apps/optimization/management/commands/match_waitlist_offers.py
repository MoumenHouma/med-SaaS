"""
Dynamic waitlist matching (project plan, section 2.3). Meant to run on a
schedule (cron / management command scheduler); a simple management command
is enough for the MVP -- Celery/Redis is a phase-2 concern, same as the other
two commands in this project.
"""

import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.clinics.models import Provider
from apps.optimization.models import OptimizationRun
from apps.optimization.services.waitlist_matcher import (
    compute_priority_score,
    expire_stale_offers,
    find_best_match,
)
from apps.scheduling.models import WaitlistEntry
from apps.scheduling.services.availability import get_available_slots
from apps.scheduling.services.reminders import send_waitlist_offer_email

LOOKAHEAD_DAYS = 14


class Command(BaseCommand):
    help = "Match currently available slots to pending waitlist entries and send offers."

    def handle(self, *args, **options):
        now = timezone.now()
        expired = expire_stale_offers(settings.WAITLIST_OFFER_EXPIRY_HOURS, now=now)
        if expired:
            self.stdout.write(f"Expired {expired} stale offer(s).")

        offers_made = 0
        providers = Provider.objects.filter(
            is_active=True, waitlist_entries__status=WaitlistEntry.EntryStatus.PENDING
        ).distinct()

        for provider in providers:
            started_at = time.monotonic()
            run = OptimizationRun.objects.create(
                provider=provider,
                run_type=OptimizationRun.RunType.WAITLIST_MATCHING,
                run_status=OptimizationRun.RunStatus.PENDING,
                target_date=timezone.localdate(),
            )
            provider_offers = 0
            try:
                for service in provider.services.filter(is_active=True):
                    slot = self._first_available_slot(provider, service, now)
                    if slot is None:
                        continue

                    entry = find_best_match(provider, service=service, now=now)
                    if entry is None:
                        continue

                    entry.status = WaitlistEntry.EntryStatus.OFFERED
                    entry.offered_slot = slot
                    entry.offer_made_at = now
                    entry.priority_score = compute_priority_score(entry, now=now)
                    entry.save(
                        update_fields=[
                            "status",
                            "offered_slot",
                            "offer_made_at",
                            "priority_score",
                            "updated_at",
                        ]
                    )
                    send_waitlist_offer_email(entry)
                    provider_offers += 1

                run.run_status = OptimizationRun.RunStatus.SUCCESS
                run.results = {"offers_made": provider_offers}
            except Exception as exc:  # noqa: BLE001 -- log per-provider, keep the batch going
                run.run_status = OptimizationRun.RunStatus.FAILED
                run.error_message = str(exc)
                self.stderr.write(self.style.ERROR(f"{provider}: {exc}"))
            finally:
                run.duration_ms = int((time.monotonic() - started_at) * 1000)
                run.save(
                    update_fields=["run_status", "results", "error_message", "duration_ms", "updated_at"]
                )
            offers_made += provider_offers

        self.stdout.write(self.style.SUCCESS(f"Made {offers_made} waitlist offer(s)."))

    def _first_available_slot(self, provider, service, now):
        for day_offset in range(LOOKAHEAD_DAYS):
            date = (now + timedelta(days=day_offset)).date()
            slots = get_available_slots(provider, service, date)
            if slots:
                return slots[0]
        return None
