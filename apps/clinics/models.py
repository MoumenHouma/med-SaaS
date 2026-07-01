"""
apps.clinics — Clinic, Provider, and Service models.

Hierarchy:
  Clinic → Provider (doctors/practitioners employed by the clinic)
         → Service  (the types of consultations the provider offers)
"""

from django.conf import settings
from django.db import models
from apps.core.models import BaseModel


class Clinic(BaseModel):
    """
    Represents an independent clinic or cabinet médical.
    One clinic may have one or more providers (doctors).
    """

    class SubscriptionTier(models.TextChoices):
        FREE = "free", "Gratuit (Essai)"
        STARTER = "starter", "Starter"
        PRO = "pro", "Pro"

    name = models.CharField(max_length=200, verbose_name="Nom de la clinique")
    slug = models.SlugField(max_length=220, unique=True, verbose_name="Slug")
    address = models.TextField(verbose_name="Adresse")
    wilaya = models.CharField(max_length=100, verbose_name="Wilaya", default="Alger")
    phone = models.CharField(max_length=20, blank=True, verbose_name="Téléphone")
    email = models.EmailField(blank=True, verbose_name="Email")
    timezone = models.CharField(
        max_length=50,
        default="Africa/Algiers",
        verbose_name="Fuseau horaire",
    )
    subscription_tier = models.CharField(
        max_length=20,
        choices=SubscriptionTier.choices,
        default=SubscriptionTier.FREE,
        verbose_name="Abonnement",
    )
    is_active = models.BooleanField(default=True, verbose_name="Active")

    class Meta:
        verbose_name = "Clinique"
        verbose_name_plural = "Cliniques"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.wilaya})"


class Provider(BaseModel):
    """
    A provider is a doctor, nurse practitioner, or other licensed practitioner
    working at a clinic. One provider belongs to exactly one clinic.
    """

    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="providers",
        verbose_name="Clinique",
    )
    first_name = models.CharField(max_length=100, verbose_name="Prénom")
    last_name = models.CharField(max_length=100, verbose_name="Nom")
    specialty = models.CharField(max_length=150, verbose_name="Spécialité")

    # JSONField to store resource constraints (e.g. required exam room, equipment)
    # Example: {"room": "consultation_1", "requires_echo_machine": true}
    resource_constraints = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Contraintes de ressources",
        help_text='Ex: {"room": "Salle 1", "requires_echo_machine": false}',
    )

    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Médecin / Praticien"
        verbose_name_plural = "Médecins / Praticiens"
        ordering = ["last_name", "first_name"]

    def __str__(self) -> str:
        return f"Dr. {self.last_name} {self.first_name} — {self.specialty}"

    @property
    def full_name(self) -> str:
        return f"Dr. {self.first_name} {self.last_name}"


class Service(BaseModel):
    """
    A type of consultation or medical service offered by a provider.
    The average_duration feeds directly into the scheduling optimization engine.
    """

    provider = models.ForeignKey(
        Provider,
        on_delete=models.CASCADE,
        related_name="services",
        verbose_name="Médecin",
    )
    name = models.CharField(
        max_length=200,
        verbose_name="Nom du service",
        help_text='Ex: "Consultation générale", "Échographie"',
    )
    average_duration = models.PositiveIntegerField(
        verbose_name="Durée moyenne (minutes)",
        default=20,
        help_text="Durée moyenne estimée de la consultation en minutes.",
    )
    price = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        verbose_name="Prix (DZD)",
        help_text="Tarif de la consultation en Dinars Algériens.",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Service / Consultation"
        verbose_name_plural = "Services / Consultations"
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.average_duration} min) — {self.provider.full_name}"


class ClinicStaff(BaseModel):
    """
    Links a Django auth User to a Clinic for dashboard access.

    Covers both roles the product layout calls for: a clinic owner/receptionist
    who manages the whole clinic's schedule, and a doctor who logs in to see
    (typically) just their own. `provider` is left blank for staff accounts
    that are not themselves a practitioner (e.g. front-desk).
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Propriétaire"
        DOCTOR = "doctor", "Médecin"
        RECEPTIONIST = "receptionist", "Réceptionniste"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clinic_staff_profile",
        verbose_name="Utilisateur",
    )
    clinic = models.ForeignKey(
        Clinic,
        on_delete=models.CASCADE,
        related_name="staff",
        verbose_name="Clinique",
    )
    provider = models.OneToOneField(
        Provider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="staff_account",
        verbose_name="Médecin associé",
        help_text="Renseigné uniquement si ce compte correspond à un médecin de la clinique.",
    )
    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.RECEPTIONIST,
        verbose_name="Rôle",
    )
    is_active = models.BooleanField(default=True, verbose_name="Actif")

    class Meta:
        verbose_name = "Membre du personnel"
        verbose_name_plural = "Personnel"
        ordering = ["clinic", "role"]

    def __str__(self) -> str:
        return f"{self.user.get_username()} — {self.get_role_display()} @ {self.clinic.name}"
