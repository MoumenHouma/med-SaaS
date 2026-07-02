import pytest
from django.utils import timezone

from apps.optimization.models import OptimizationRun

pytestmark = pytest.mark.django_db


def test_optimization_run_creation(provider):
    run = OptimizationRun.objects.create(
        provider=provider,
        run_type=OptimizationRun.RunType.NO_SHOW_PREDICTION,
        target_date=timezone.localdate(),
    )
    assert run.pk is not None
    assert run.run_status == OptimizationRun.RunStatus.PENDING
