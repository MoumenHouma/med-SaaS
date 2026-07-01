"""
apps.patients — Patient model.

COMPLIANCE NOTE (Law 18-07 / ANPDP):
  This model is deliberately minimal. Only the data strictly required for
  appointment scheduling is stored. Full medical records, diagnoses, and
  prescriptions are kept outside this system (at the clinic level) to reduce
  the ANPDP authorization footprint during the MVP phase.

  Do NOT add fields (e.g. national ID, full medical history) without first
  consulting with an ANPDP-registered legal advisor.
"""

from django.db import models
from apps.core.models import BaseModel
from apps.clinics.models import Clinic


class Patient(BaseModel):
    """
    Represents a patient registered within a specific clinic's system.
    The same real person may have separate Patient records at different clinics —
    this is intentional to maintain data isolation between clinics.
    """

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="patients",
        verbose_name="Clinique",
    )

    # Minimal PII — only what is needed to contact the patient
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    phone_number = models.CharField(
        max_length=20,
        verbose_name="Numéro de téléphone",
        help_text="Utilisé pour les rappels SMS/WhatsApp.",
    )
    email = models.EmailField(
        blank=True,
        verbose_name="Email",
        help_text="Optionnel. Utilisé pour les rappels par email (Phase 1, avant la passerelle SMS/WhatsApp).",
    )
    date_of_birth = models.DateField(
        null=True,
        blank=True,
        verbose_name="Date de naissance",
        help_text="Optionnel. Utilisé pour distinguer les patients homonymes.",
    )

    # Clinic-assigned patient reference number (printed on physical file)
    clinic_ref = models.CharField(
        max_length=50,
        blank=True,
        verbose_name="Référence dossier",
        help_text="Numéro de dossier interne de la clinique (optionnel).",
    )

    notes = models.TextField(
        blank=True,
        verbose_name="Notes",
        help_text="Notes générales non-médicales (ex: préfère les rendez-vous matinaux).",
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Patient"
        verbose_name_plural = "Patients"
        ordering = ["last_name", "first_name"]
        # Prevent duplicate patients within the same clinic
        unique_together = [("clinic", "phone_number")]

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name} ({self.phone_number})"

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
