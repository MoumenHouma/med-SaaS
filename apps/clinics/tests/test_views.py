import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_register_onboarding_dashboard_flow(client):
    register_url = reverse("core:register")
    response = client.post(
        register_url,
        {
            "username": "newdoc",
            "email": "newdoc@example.com",
            "password1": "S3cure!Pass123",
            "password2": "S3cure!Pass123",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("clinics:onboarding")

    onboarding_url = reverse("clinics:onboarding")
    response = client.post(
        onboarding_url,
        {
            "name": "Cabinet Test",
            "address": "1 rue Test",
            "wilaya": "Alger",
            "phone": "0555000000",
            "email": "cabinet@example.com",
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("clinics:dashboard")

    response = client.get(reverse("clinics:dashboard"))
    assert response.status_code == 200
    assert response.context["clinic"].name == "Cabinet Test"
