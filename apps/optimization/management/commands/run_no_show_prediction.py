"""
Populates Appointment.no_show_probability for every upcoming, still-active
appointment. Meant to run nightly (cron / management command scheduler);
see the project plan's "Background jobs" note -- a simple management
command is enough for the MVP, Celery/Redis is a phase-2 concern.
"""

import time

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.clinics.models import Provider
from apps.optimization.models import OptimizationRun
from apps.optimization.services.predictor import predict_probability, train_model
from apps.scheduling.models import Appointment


class Command(BaseCommand):
    help = "Predict no-show probability for each provider's upcoming appointments."

    def add_arguments(self, parser):
        parser.add_argument(
            "--provider", type=str, default=None, help="Limit the run to a single provider UUID."
        )

    def handle(self, *args, **options):
        providers = Provider.objects.filter(is_active=True)
        if options["provider"]:
            providers = providers.filter(id=options["provider"])

        clinic_models = {}
        total_runs = 0

        for provider in providers:
            upcoming = Appointment.objects.filter(
                provider=provider,
                status__in=[Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED],
                scheduled_start__gte=timezone.now(),
            ).select_related("patient")

            if not upcoming.exists():
                continue

            started_at = time.monotonic()
            run = OptimizationRun.objects.create(
                provider=provider,
                run_type=OptimizationRun.RunType.NO_SHOW_PREDICTION,
                run_status=OptimizationRun.RunStatus.PENDING,
                target_date=timezone.localdate(),
            )
            total_runs += 1

            try:
                if provider.clinic_id not in clinic_models:
                    clinic_models[provider.clinic_id] = train_model(provider.clinic)
                model = clinic_models[provider.clinic_id]

                updated = 0
                used_model = False
                for appointment in upcoming:
                    probability, model_used = predict_probability(appointment, model)
                    appointment.no_show_probability = probability
                    appointment.save(update_fields=["no_show_probability", "updated_at"])
                    updated += 1
                    used_model = used_model or model_used

                run.run_status = OptimizationRun.RunStatus.SUCCESS
                run.results = {"appointments_updated": updated, "used_learned_model": used_model}
            except Exception as exc:  # noqa: BLE001 -- log per-provider, keep the batch going
                run.run_status = OptimizationRun.RunStatus.FAILED
                run.error_message = str(exc)
                self.stderr.write(self.style.ERROR(f"{provider}: {exc}"))
            finally:
                run.duration_ms = int((time.monotonic() - started_at) * 1000)
                run.save(update_fields=["run_status", "results", "error_message", "duration_ms", "updated_at"])

        self.stdout.write(self.style.SUCCESS(f"Completed {total_runs} provider run(s)."))
