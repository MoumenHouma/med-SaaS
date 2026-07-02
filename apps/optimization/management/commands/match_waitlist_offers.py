"""
Dynamic waitlist matching (project plan, section 2.3), powered by the CP-SAT
slot allocation optimizer (section 2.2): meant to run on a schedule (cron /
management command scheduler); a simple management command is enough for the
MVP -- Celery/Redis is a phase-2 concern, same as the other two commands in
this project.
"""

import time
from datetime import datetime, timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.clinics.models import Provider
from apps.optimization.models import OptimizationRun
from apps.optimization.services.scheduler import Demand, SlotOption, allocate_slots
from apps.optimization.services.waitlist_matcher import compute_priority_score, expire_stale_offers
from apps.scheduling.models import WaitlistEntry
from apps.scheduling.services.availability import get_available_slots
from apps.scheduling.services.reminders import send_waitlist_offer_email

LOOKAHEAD_DAYS = 14

_WEEKDAY_NAMES = {
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}


def _parse_preferred_windows(preferred_slots, now):
    """
    Converts WaitlistEntry.preferred_slots (e.g. [{"day": "monday", "start":
    "09:00", "end": "12:00"}]) into concrete datetime windows over the
    lookahead period. Returns None (no preference, any slot fits) if the
    entry has no preferences set or none of them resolve to anything.
    """
    if not preferred_slots:
        return None

    windows = []
    for pref in preferred_slots:
        weekday = _WEEKDAY_NAMES.get(str(pref.get("day", "")).lower())
        start_str, end_str = pref.get("start"), pref.get("end")
        if weekday is None or not start_str or not end_str:
            continue
        start_time = datetime.strptime(start_str, "%H:%M").time()
        end_time = datetime.strptime(end_str, "%H:%M").time()
        for day_offset in range(LOOKAHEAD_DAYS):
            date = (now + timedelta(days=day_offset)).date()
            if date.weekday() != weekday:
                continue
            windows.append(
                (
                    timezone.make_aware(datetime.combine(date, start_time)),
                    timezone.make_aware(datetime.combine(date, end_time)),
                )
            )
    return windows or None


def _build_demands(entries, now):
    return [
        Demand(
            id=str(entry.id),
            urgency=entry.urgency,
            wait_hours=(now - entry.created_at).total_seconds() / 3600,
            preferred_windows=_parse_preferred_windows(entry.preferred_slots, now),
        )
        for entry in entries
    ]


def _build_slot_options(provider, service, now):
    slots = []
    for day_offset in range(LOOKAHEAD_DAYS):
        date = (now + timedelta(days=day_offset)).date()
        for slot_start in get_available_slots(provider, service, date):
            slot_end = slot_start + timedelta(minutes=service.average_duration)
            slots.append(SlotOption(id=slot_start.isoformat(), start=slot_start, end=slot_end))
    return slots


class Command(BaseCommand):
    help = "Match available slots to pending waitlist entries via the CP-SAT allocator and send offers."

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
            demands_considered = 0
            slots_considered = 0
            objective_total = 0.0
            try:
                for service in provider.services.filter(is_active=True):
                    entries = list(
                        WaitlistEntry.objects.filter(
                            provider=provider, status=WaitlistEntry.EntryStatus.PENDING
                        ).filter(Q(service=service) | Q(service__isnull=True))
                    )
                    if not entries:
                        continue
                    entry_by_id = {str(entry.id): entry for entry in entries}

                    slot_options = _build_slot_options(provider, service, now)
                    if not slot_options:
                        continue
                    slot_by_id = {slot.id: slot for slot in slot_options}

                    demands_considered += len(entries)
                    slots_considered += len(slot_options)

                    result = allocate_slots(_build_demands(entries, now), slot_options)
                    objective_total += result.objective_value

                    for assignment in result.assignments:
                        entry = entry_by_id[assignment.demand_id]
                        slot = slot_by_id[assignment.slot_id]

                        entry.status = WaitlistEntry.EntryStatus.OFFERED
                        entry.offered_slot = slot.start
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
                run.results = {
                    "offers_made": provider_offers,
                    "demands_considered": demands_considered,
                    "slots_considered": slots_considered,
                    "objective_value": objective_total,
                }
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
