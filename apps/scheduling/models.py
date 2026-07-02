"""
apps.scheduling — SlotTemplate, Appointment, and WaitlistEntry models.

This is the heart of the Rendia platform. These models represent:
  - SlotTemplate: a provider's recurring weekly availability pattern
  - Appointment:  a confirmed booking between a patient and a provider
  - WaitlistEntry: a queue of patients waiting for a slot to free up

The `no_show_probability` field on Appointment is populated by the
optimization engine (apps.optimization) before the appointment date.
"""

from django.db import models
from apps.core.models import BaseModel
from apps.clinics.models import Provider, Service
from apps.patients.models import Patient


class SlotTemplate(BaseModel):
    """
    Defines a provider's weekly recurring availability.
    The optimization engine uses this to generate concrete daily slot grids.

    Example: Dr. Benali is available Monday, Wednesday, Friday from 09:00 to 13:00
             with a default slot duration of 20 minutes.
    """

    class DayOfWeek(models.IntegerChoices):
        MONDAY = 0, "Lundi"
        TUESDAY = 1, "Mardi"
        WEDNESDAY = 2, "Mercredi"
        THURSDAY = 3, "Jeudi"
        FRIDAY = 4, "Vendredi"
        SATURDAY = 5, "Samedi"
        SUNDAY = 6, "Dimanche"

    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="slot_templates",
        verbose_name="Médecin",
    )
    day_of_week = models.IntegerField(
        choices=DayOfWeek.choices,
        verbose_name="Jour de la semaine",
    )
    start_time = models.TimeField(verbose_name="Heure de début")
    end_time = models.TimeField(verbose_name="Heure de fin")

    # Default slot duration for this session — can be overridden per-service
    default_slot_duration = models.PositiveIntegerField(
        default=20,
        verbose_name="Durée de créneau (minutes)",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Modèle de disponibilité"
        verbose_name_plural = "Modèles de disponibilité"
        ordering = ["provider", "day_of_week", "start_time"]
        unique_together = [("provider", "day_of_week", "start_time")]

    def __str__(self) -> str:
        day = self.DayOfWeek(self.day_of_week).label
        return f"{self.provider.full_name} — {day} {self.start_time}–{self.end_time}"


class Appointment(BaseModel):
    """
    A concrete appointment booking between a patient, provider, and service.

    Status FSM (Finite State Machine):
      scheduled → confirmed → checked_in → completed
                ↘ cancelled
                ↘ no_show

    The no_show_probability field is written by the optimization engine
    (apps.optimization.services.predictor) before each appointment day.
    """

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Planifié"
        CONFIRMED = "confirmed", "Confirmé"
        CHECKED_IN = "checked_in", "Arrivé"
        COMPLETED = "completed", "Terminé"
        CANCELLED = "cancelled", "Annulé"
        NO_SHOW = "no_show", "Absent"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="Patient",
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.PROTECT,
        related_name="appointments",
        verbose_name="Médecin",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
        verbose_name="Service",
    )

    # Scheduled times
    scheduled_start = models.DateTimeField(verbose_name="Début prévu")
    scheduled_end = models.DateTimeField(verbose_name="Fin prévue")

    # Actual times (filled in when the patient arrives/leaves)
    actual_start = models.DateTimeField(null=True, blank=True, verbose_name="Début réel")
    actual_end = models.DateTimeField(null=True, blank=True, verbose_name="Fin réelle")

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.SCHEDULED,
        verbose_name="Statut",
        db_index=True,
    )

    # OR Engine output: probability that this patient will not show up [0.0, 1.0]
    # Populated nightly by apps.optimization. Null until first prediction run.
    no_show_probability = models.FloatField(
        null=True,
        blank=True,
        verbose_name="Probabilité d'absence",
        help_text="Calculé par le moteur d'optimisation. Valeur entre 0.0 et 1.0.",
    )

    # Lead time in days at the time of booking (cached for model training)
    lead_time_days = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Délai de réservation (jours)",
        help_text="Nombre de jours entre la réservation et le RDV.",
    )

    # Whether a reminder was sent (SMS/WhatsApp)
    reminder_sent = models.BooleanField(default=False, verbose_name="Rappel envoyé")
    reminder_acknowledged = models.BooleanField(
        default=False,
        verbose_name="Rappel confirmé",
        help_text="True si le patient a répondu '1' pour confirmer.",
    )

    notes = models.TextField(blank=True, verbose_name="Notes internes")

    class Meta:
        verbose_name = "Rendez-vous"
        verbose_name_plural = "Rendez-vous"
        ordering = ["scheduled_start"]
        indexes = [
            models.Index(fields=["scheduled_start", "status"]),
            models.Index(fields=["provider", "scheduled_start"]),
            models.Index(fields=["patient", "status"]),
        ]

    def __str__(self) -> str:
        return (
            f"{self.patient.full_name} → {self.provider.full_name} "
            f"le {self.scheduled_start:%d/%m/%Y à %H:%M} [{self.get_status_display()}]"
        )

    def save(self, *args, **kwargs):
        """Compute lead_time_days once, on the initial INSERT only."""
        if self._state.adding and self.scheduled_start:
            from django.utils import timezone
            delta = self.scheduled_start.date() - timezone.now().date()
            self.lead_time_days = max(delta.days, 0)
        super().save(*args, **kwargs)


class WaitlistEntry(BaseModel):
    """
    A patient waiting for an available slot with a specific provider.
    When a cancellation occurs, the optimization engine scores all active
    WaitlistEntry records and offers the slot to the highest-scoring patient.

    Priority score is computed by apps.optimization.services.waitlist_matcher
    and cached here as `priority_score` for fast ranking queries.
    """

    class EntryStatus(models.TextChoices):
        PENDING = "pending", "En attente"
        OFFERED = "offered", "Slot proposé"
        ACCEPTED = "accepted", "Accepté"
        EXPIRED = "expired", "Expiré"
        CANCELLED = "cancelled", "Annulé"

    patient = models.ForeignKey(
        Patient,
        on_delete=models.CASCADE,
        related_name="waitlist_entries",
        verbose_name="Patient",
    )
    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="waitlist_entries",
        verbose_name="Médecin souhaité",
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="waitlist_entries",
        verbose_name="Service souhaité",
    )

    # Patient's preferred time windows stored as structured JSON
    # Example: [{"day": "monday", "start": "09:00", "end": "12:00"}]
    preferred_slots = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Créneaux préférés",
        help_text='Ex: [{"day": "monday", "start": "09:00", "end": "12:00"}]',
    )

    # Urgency level set by the clinic staff
    urgency = models.PositiveSmallIntegerField(
        default=1,
        verbose_name="Urgence",
        help_text="1 = normal, 2 = prioritaire, 3 = urgent",
    )

    # Computed by the OR engine, used for fast ORDER BY queries
    priority_score = models.FloatField(
        default=0.0,
        verbose_name="Score de priorité",
        db_index=True,
    )

    status = models.CharField(
        max_length=20,
        choices=EntryStatus.choices,
        default=EntryStatus.PENDING,
        verbose_name="Statut",
        db_index=True,
    )

    # When the slot offer was made (for offer expiry tracking)
    offer_made_at = models.DateTimeField(null=True, blank=True, verbose_name="Offre faite le")

    class Meta:
        verbose_name = "Liste d'attente"
        verbose_name_plural = "Liste d'attente"
        ordering = ["-priority_score", "created_at"]
        indexes = [
            models.Index(fields=["provider", "status", "-priority_score"]),
        ]

    def __str__(self) -> str:
        return (
            f"[Liste d'attente] {self.patient.full_name} → {self.provider.full_name} "
            f"(Urgence: {self.urgency}, Score: {self.priority_score:.2f})"
        )
