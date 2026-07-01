"""
apps.optimization — OR Engine stub.

This app will contain:
  - services/predictor.py  : No-show probability predictor (logistic regression)
  - services/scheduler.py  : Slot allocation optimizer (Bailey-Welch + MIP)
  - services/waitlist.py   : Dynamic waitlist matching scorer
  - management/commands/   : Django management commands for scheduled runs

OptimizationRun logs every run of the engine for auditability and debugging.
"""

from django.db import models
from apps.core.models import BaseModel
from apps.clinics.models import Provider


class OptimizationRun(BaseModel):
    """
    Audit log for each execution of the optimization engine.
    Stores the input parameters, algorithm used, and output summary.
    """

    class RunType(models.TextChoices):
        NO_SHOW_PREDICTION = "no_show_prediction", "Prédiction d'absence"
        SLOT_ALLOCATION = "slot_allocation", "Allocation des créneaux"
        WAITLIST_MATCHING = "waitlist_matching", "Correspondance liste d'attente"
        FULL_DAILY = "full_daily", "Optimisation quotidienne complète"

    class RunStatus(models.TextChoices):
        PENDING = "pending", "En cours"
        SUCCESS = "success", "Succès"
        PARTIAL = "partial", "Partiel"
        FAILED = "failed", "Échec"

    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="optimization_runs",
        verbose_name="Médecin",
        help_text="Provider whose schedule was optimized in this run.",
    )
    run_type = models.CharField(
        max_length=30,
        choices=RunType.choices,
        verbose_name="Type de run",
    )
    run_status = models.CharField(
        max_length=20,
        choices=RunStatus.choices,
        default=RunStatus.PENDING,
        verbose_name="Statut",
    )
    target_date = models.DateField(
        verbose_name="Date cible",
        help_text="The clinic date this optimization run was computed for.",
    )

    # Algorithm parameters (free-form, for reproducibility)
    parameters = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Paramètres",
        help_text="Algorithm parameters used in this run (weights, solver timeout, etc.)",
    )

    # Output metrics produced by the engine
    results = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Résultats",
        help_text="Output summary (e.g. predicted no-show count, solver objective value).",
    )

    # Error traceback if run_status == FAILED
    error_message = models.TextField(
        blank=True,
        verbose_name="Message d'erreur",
    )

    # Wall-clock duration of the run in milliseconds
    duration_ms = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Durée (ms)",
    )

    class Meta:
        verbose_name = "Exécution d'optimisation"
        verbose_name_plural = "Exécutions d'optimisation"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["provider", "target_date", "run_type"]),
            models.Index(fields=["run_status", "-created_at"]),
        ]

    def __str__(self) -> str:
        return (
            f"[{self.get_run_type_display()}] {self.provider.full_name} "
            f"— {self.target_date} [{self.get_run_status_display()}]"
        )
