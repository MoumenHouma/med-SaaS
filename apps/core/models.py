"""
apps.core — Shared abstract base models and utilities.
Every model in Rendia inherits from BaseModel to get:
  - UUID primary key (safe for API exposure, avoids sequential ID enumeration)
  - created_at / updated_at timestamps (auto-managed)
"""

import uuid
from django.db import models


class BaseModel(models.Model):
    """
    Abstract base model inherited by all Rendia models.
    Provides UUID PK and automatic timestamps.
    """

    id = models.UUIDField(
        primary_key=True,
        default=uuid.uuid4,
        editable=False,
        verbose_name="ID",
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Créé le")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Mis à jour le")

    class Meta:
        abstract = True
        ordering = ["-created_at"]
