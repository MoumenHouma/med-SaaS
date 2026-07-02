from django.urls import path

from . import views

app_name = "scheduling"

urlpatterns = [
    path("book/<slug:clinic_slug>/", views.booking_search, name="booking_search"),
    path("book/<slug:clinic_slug>/confirm/", views.booking_confirm, name="booking_confirm"),
    path("book/<slug:clinic_slug>/waitlist/", views.waitlist_join, name="waitlist_join"),
    path("appointments/<uuid:pk>/", views.appointment_manage, name="appointment_manage"),
    path("appointments/<uuid:pk>/reschedule/", views.appointment_reschedule, name="appointment_reschedule"),
    path("waitlist/<uuid:pk>/respond/", views.waitlist_offer_respond, name="waitlist_offer_respond"),
]
