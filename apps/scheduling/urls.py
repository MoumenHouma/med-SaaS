from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("book/<slug:clinic_slug>/", views.booking_search, name="booking_search"),
    path("book/<slug:clinic_slug>/confirm/", views.booking_confirm, name="booking_confirm"),
    path("appointments/<uuid:pk>/", views.appointment_manage, name="appointment_manage"),
    path("appointments/<uuid:pk>/reschedule/", views.appointment_reschedule, name="appointment_reschedule"),
]
