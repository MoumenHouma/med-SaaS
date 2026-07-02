import threading
from datetime import datetime, time, timedelta

import pytest
from django.db import connections
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.clinics.models import Clinic, Provider, Service
from apps.patients.models import Patient
from apps.scheduling.models import Appointment, SlotTemplate


def _slot_datetime(date, hour, minute=0):
    return timezone.make_aware(datetime.combine(date, time(hour, minute)))


@pytest.mark.django_db
def test_full_booking_flow(client, clinic, provider, service, slot_template, future_date):
    search_url = reverse("scheduling:booking_search", kwargs={"clinic_slug": clinic.slug})
    response = client.get(
        search_url,
        {"provider": str(provider.id), "service": str(service.id), "date": future_date.isoformat()},
    )
    assert response.status_code == 200
    slots = response.context["slots"]
    assert slots

    slot = slots[0]
    confirm_url = reverse("scheduling:booking_confirm", kwargs={"clinic_slug": clinic.slug})
    response = client.get(
        confirm_url,
        {"provider": str(provider.id), "service": str(service.id), "slot": slot.isoformat()},
    )
    assert response.status_code == 200

    response = client.post(
        confirm_url,
        {
            "provider": str(provider.id),
            "service": str(service.id),
            "slot": slot.isoformat(),
            "first_name": "Sara",
            "last_name": "K",
            "phone_number": "0555999888",
            "email": "",
        },
    )
    assert response.status_code == 302
    appointment = Appointment.objects.get()
    assert appointment.scheduled_start == slot
    assert appointment.status == Appointment.Status.SCHEDULED
    assert response.url == reverse("scheduling:appointment_manage", kwargs={"pk": appointment.id})


@pytest.mark.django_db(transaction=True)
def test_double_booking_race_is_prevented():
    """
    Two concurrent POSTs to booking_confirm for the identical slot must not
    both succeed. Requires transaction=True (transactional_db) -- the default
    `db` fixture wraps the test in a transaction invisible to other threads/
    connections, which would make this test pass without ever exercising the
    real DB constraint. Do not "simplify" this back to the default fixture.

    Also requires config.settings.local's DATABASES["default"]["TEST"]["NAME"]
    to be a file (not Django's default :memory:), since separate threads get
    separate connections and isolated :memory: databases would not share data.
    """
    clinic = Clinic.objects.create(name="Race Clinic", slug="race-clinic", address="Adresse")
    provider = Provider.objects.create(
        clinic=clinic, first_name="A", last_name="B", specialty="Généraliste"
    )
    service = Service.objects.create(
        provider=provider, name="Consultation", average_duration=30, price="2000.00"
    )
    future_date = timezone.localdate() + timedelta(days=14)
    SlotTemplate.objects.create(
        provider=provider,
        day_of_week=future_date.weekday(),
        start_time=time(9, 0),
        end_time=time(12, 0),
    )
    slot = _slot_datetime(future_date, 9)

    confirm_url = reverse("scheduling:booking_confirm", kwargs={"clinic_slug": clinic.slug})
    results = []
    barrier = threading.Barrier(2)

    def make_booking(suffix):
        barrier.wait()
        try:
            response = Client().post(
                confirm_url,
                {
                    "provider": str(provider.id),
                    "service": str(service.id),
                    "slot": slot.isoformat(),
                    "first_name": "Patient",
                    "last_name": suffix,
                    "phone_number": f"055500000{suffix}",
                    "email": "",
                },
            )
            results.append(response.status_code)
        finally:
            connections.close_all()

    threads = [threading.Thread(target=make_booking, args=(str(i),)) for i in (1, 2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert results == [302, 302]
    assert Appointment.objects.filter(provider=provider, scheduled_start=slot).count() == 1


@pytest.mark.django_db
def test_reschedule_moves_appointment_to_new_slot(client, provider, service, slot_template, patient, future_date):
    start = _slot_datetime(future_date, 9)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
    )
    new_slot = _slot_datetime(future_date, 10)
    url = reverse("scheduling:appointment_reschedule", kwargs={"pk": appointment.id})
    response = client.post(url, {"slot": new_slot.isoformat()})
    assert response.status_code == 302
    appointment.refresh_from_db()
    assert appointment.scheduled_start == new_slot


@pytest.mark.django_db
def test_reschedule_rejects_unavailable_slot(client, provider, service, slot_template, patient, future_date):
    start = _slot_datetime(future_date, 9)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
    )
    other_patient = Patient.objects.create(
        clinic=provider.clinic, first_name="X", last_name="Y", phone_number="0555222333"
    )
    taken_slot = _slot_datetime(future_date, 10)
    Appointment.objects.create(
        patient=other_patient,
        provider=provider,
        service=service,
        scheduled_start=taken_slot,
        scheduled_end=taken_slot + timedelta(minutes=service.average_duration),
    )

    url = reverse("scheduling:appointment_reschedule", kwargs={"pk": appointment.id})
    response = client.post(url, {"slot": taken_slot.isoformat()})
    assert response.status_code == 200
    appointment.refresh_from_db()
    assert appointment.scheduled_start == start


@pytest.mark.django_db
def test_cancel_appointment(client, provider, service, patient, future_date):
    start = _slot_datetime(future_date, 9)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
    )
    url = reverse("scheduling:appointment_manage", kwargs={"pk": appointment.id})
    response = client.post(url, {"action": "cancel"})
    assert response.status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CANCELLED


@pytest.mark.django_db
def test_cancelled_appointment_refuses_further_cancel(client, provider, service, patient, future_date):
    start = _slot_datetime(future_date, 9)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
        status=Appointment.Status.CANCELLED,
    )
    url = reverse("scheduling:appointment_manage", kwargs={"pk": appointment.id})
    response = client.post(url, {"action": "cancel"})
    assert response.status_code == 302
    appointment.refresh_from_db()
    assert appointment.status == Appointment.Status.CANCELLED


@pytest.mark.django_db
def test_cancelled_appointment_refuses_reschedule(client, provider, service, patient, future_date):
    start = _slot_datetime(future_date, 9)
    appointment = Appointment.objects.create(
        patient=patient,
        provider=provider,
        service=service,
        scheduled_start=start,
        scheduled_end=start + timedelta(minutes=service.average_duration),
        status=Appointment.Status.CANCELLED,
    )
    url = reverse("scheduling:appointment_reschedule", kwargs={"pk": appointment.id})
    response = client.get(url)
    assert response.status_code == 302
    assert response.url == reverse("scheduling:appointment_manage", kwargs={"pk": appointment.id})
