from django.urls import path

from . import views

app_name = "clinics"

urlpatterns = [
    path("onboarding/", views.OnboardingView.as_view(), name="onboarding"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("providers/add/", views.ProviderCreateView.as_view(), name="provider_add"),
    path(
        "providers/<uuid:provider_id>/services/add/",
        views.ServiceCreateView.as_view(),
        name="service_add",
    ),
]
