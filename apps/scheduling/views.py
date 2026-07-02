from datetime import timedelta

from django.contrib import messages
from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime

from apps.clinics.models import Clinic, Provider, Service
from apps.patients.models import Patient

from .forms import PatientContactForm
from .models import Appointment
from .services.availability import get_available_slots


def _parse_slot(raw):
    if not raw:
        return None
    slot = parse_datetime(raw)
    if slot and timezone.is_naive(slot):
        slot = timezone.make_aware(slot)
    return slot


def booking_search(request, clinic_slug):
    clinic = get_object_or_404(Clinic, slug=clinic_slug, is_active=True)
    providers = clinic.providers.filter(is_active=True).order_by("last_name", "first_name")

    selected_provider = None
    selected_service = None
    services = []
    slots = []
    selected_date = timezone.localdate()

    provider_id = request.GET.get("provider")
    if provider_id:
        selected_provider = providers.filter(id=provider_id).first()

    if selected_provider:
        services = selected_provider.services.filter(is_active=True)
        service_id = request.GET.get("service")
        if service_id:
            selected_service = services.filter(id=service_id).first()

    date_str = request.GET.get("date")
    if date_str:
        parsed = parse_date(date_str)
        if parsed and parsed >= timezone.localdate():
            selected_date = parsed

    if selected_provider and selected_service:
        slots = get_available_slots(selected_provider, selected_service, selected_date)

    return render(
        request,
        "scheduling/booking_search.html",
        {
            "clinic": clinic,
            "providers": providers,
            "services": services,
            "selected_provider": selected_provider,
            "selected_service": selected_service,
            "selected_date": selected_date,
            "slots": slots,
        },
    )


def booking_confirm(request, clinic_slug):
    clinic = get_object_or_404(Clinic, slug=clinic_slug, is_active=True)
    provider = get_object_or_404(
        Provider,
        id=request.GET.get("provider") or request.POST.get("provider"),
        clinic=clinic,
        is_active=True,
    )
    service = get_object_or_404(
        Service,
        id=request.GET.get("service") or request.POST.get("service"),
        provider=provider,
        is_active=True,
    )
    slot_start = _parse_slot(request.GET.get("slot") or request.POST.get("slot"))
    search_url = reverse("scheduling:booking_search", kwargs={"clinic_slug": clinic_slug})

    if not slot_start:
        messages.error(request, "Créneau invalide, veuillez recommencer.")
        return redirect(search_url)

    still_available = slot_start in get_available_slots(provider, service, slot_start.date())
    if not still_available:
        messages.error(request, "Ce créneau n'est plus disponible. Veuillez en choisir un autre.")
        return redirect(search_url)

    if request.method == "POST":
        form = PatientContactForm(request.POST)
        if form.is_valid():
            # re-check right before writing to narrow the booking race window;
            # the unique_active_appointment_slot DB constraint is the real
            # guarantee, caught as IntegrityError below.
            if slot_start not in get_available_slots(provider, service, slot_start.date()):
                messages.error(request, "Ce créneau vient d'être réservé. Veuillez en choisir un autre.")
                return redirect(search_url)

            try:
                with transaction.atomic():
                    patient, _created = Patient.objects.update_or_create(
                        clinic=clinic,
                        phone_number=form.cleaned_data["phone_number"],
                        defaults={
                            "first_name": form.cleaned_data["first_name"],
                            "last_name": form.cleaned_data["last_name"],
                            "email": form.cleaned_data["email"],
                        },
                    )
                    appointment = Appointment.objects.create(
                        patient=patient,
                        provider=provider,
                        service=service,
                        scheduled_start=slot_start,
                        scheduled_end=slot_start + timedelta(minutes=service.average_duration),
                    )
            except IntegrityError:
                messages.error(request, "Ce créneau vient d'être réservé. Veuillez en choisir un autre.")
                return redirect(search_url)

            messages.success(request, "Rendez-vous confirmé.")
            return redirect("scheduling:appointment_manage", pk=appointment.id)
    else:
        form = PatientContactForm()

    return render(
        request,
        "scheduling/booking_confirm.html",
        {"clinic": clinic, "provider": provider, "service": service, "slot_start": slot_start, "form": form},
    )


def appointment_manage(request, pk):
    appointment = get_object_or_404(Appointment, id=pk)
    modifiable_statuses = (Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED)

    if request.method == "POST" and request.POST.get("action") == "cancel":
        if appointment.status in modifiable_statuses:
            appointment.status = Appointment.Status.CANCELLED
            appointment.save(update_fields=["status", "updated_at"])
            messages.success(request, "Rendez-vous annulé.")
        else:
            messages.error(request, "Ce rendez-vous ne peut plus être annulé.")
        return redirect("scheduling:appointment_manage", pk=appointment.id)

    return render(
        request,
        "scheduling/appointment_manage.html",
        {"appointment": appointment, "can_modify": appointment.status in modifiable_statuses},
    )


def appointment_reschedule(request, pk):
    appointment = get_object_or_404(Appointment, id=pk)
    modifiable_statuses = (Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED)
    if appointment.status not in modifiable_statuses:
        messages.error(request, "Ce rendez-vous ne peut plus être reprogrammé.")
        return redirect("scheduling:appointment_manage", pk=appointment.id)

    provider = appointment.provider
    service = appointment.service

    selected_date = timezone.localdate()
    date_str = request.GET.get("date") or request.POST.get("date")
    if date_str:
        parsed = parse_date(date_str)
        if parsed and parsed >= timezone.localdate():
            selected_date = parsed

    if request.method == "POST" and request.POST.get("slot"):
        slot_start = _parse_slot(request.POST.get("slot"))
        valid_slots = (
            get_available_slots(provider, service, slot_start.date(), exclude_appointment_id=appointment.id)
            if slot_start
            else []
        )
        if slot_start and slot_start in valid_slots:
            appointment.scheduled_start = slot_start
            appointment.scheduled_end = slot_start + timedelta(minutes=service.average_duration)
            try:
                with transaction.atomic():
                    appointment.save(update_fields=["scheduled_start", "scheduled_end", "updated_at"])
            except IntegrityError:
                messages.error(request, "Ce créneau n'est plus disponible.")
            else:
                messages.success(request, "Rendez-vous reprogrammé.")
                return redirect("scheduling:appointment_manage", pk=appointment.id)
        else:
            messages.error(request, "Ce créneau n'est plus disponible.")

    slots = get_available_slots(provider, service, selected_date, exclude_appointment_id=appointment.id)
    return render(
        request,
        "scheduling/appointment_reschedule.html",
        {"appointment": appointment, "selected_date": selected_date, "slots": slots},
    )
