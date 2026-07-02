# Rendia (med-SaaS)

Appointment & patient-flow optimization for independent clinics in Algeria. See `Rendia_Project_Plan.md` for the full product plan.

## Stack

Django 5.2, PostgreSQL (production) / SQLite (local dev), `python-decouple` for env config. Frontend is HTMX + Alpine.js + Tailwind. Optimization engine: scikit-learn (no-show prediction) and OR-Tools CP-SAT (slot allocation) are in; SimPy simulation is still a later phase — see the plan.

## Project layout

```
config/settings/    base.py (shared) + local.py (SQLite, DEBUG) + production.py (Postgres, hardened)
apps/core/           BaseModel (UUID PK, timestamps) — inherited by every model below
apps/clinics/        Clinic, Provider, Service, ClinicStaff (auth link for dashboard login)
apps/patients/       Patient (minimal PII, clinic-isolated — see Law 18-07 compliance note in the module docstring)
apps/scheduling/     SlotTemplate, Appointment, WaitlistEntry
apps/optimization/   OptimizationRun (audit log); services/ (predictor, analytics, waitlist_matcher, scheduler — CP-SAT slot allocation — all implemented)
```

## Local setup

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows
pip install -r requirements.txt
copy .env.example .env          # fill in SECRET_KEY at minimum
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Local dev uses SQLite automatically (`config.settings.local`, set in `manage.py`) — no database setup required. Admin panel is at `/admin/`.

## Current status

Phase 1 MVP (per `Rendia_Project_Plan.md`) is functionally complete:

- **Core platform**: registration, login, clinic onboarding, and the staff dashboard.
- **Booking CRUD**: search, confirm, manage, cancel, reschedule — with a DB-level constraint (not just app logic) preventing two patients from double-booking the same slot.
- **No-show prediction**: a cold-start heuristic that upgrades to a per-clinic logistic regression once there's enough history (`apps.optimization.services.predictor` + the `run_no_show_prediction` command).
- **Slot allocation**: real-time patient-facing search still uses the Phase 1 rule-based heuristic (`apps.scheduling.services.availability.get_available_slots`); the Phase 2 CP-SAT mixed-integer program (`apps.optimization.services.scheduler`) now runs as the batch waitlist allocator (see below) — a joint optimization across every pending waitlist entry and every open slot, not the real-time search path.
- **Dynamic waitlist matching**: the `match_waitlist_offers` command jointly assigns pending waitlist entries to open slots via the CP-SAT optimizer (urgency, wait time, and each entry's preferred time windows all factored in), sending offer emails, with a patient-facing join/accept/decline flow.
- **Check-in/check-out + Pareto delay analytics**: staff mark patient arrival and visit completion, tagging (or accepting an auto-suggested) delay cause; the dashboard surfaces a ranked breakdown of what's actually causing delays (`apps.optimization.services.analytics.bottleneck_breakdown`).
- **Dashboard analytics**: utilization % and an 8-week no-show trend, alongside the delay breakdown.
- **Email reminders**: `apps.scheduling.services.reminders` + the `send_appointment_reminders` command.
- **Tests**: a pytest-django suite covers models, services, views, and management commands.
- **`/health/`** endpoint for uptime monitoring.

Deliberately not built yet: SMS/WhatsApp reminders (needs real gateway credentials — Twilio or Meta Cloud API — the roadmap sequences this after email); true overbooking (deliberately double-booking high-no-show-risk slots — needs an `Appointment.is_overbooked` schema change plus a product decision on disclosing backup-slot status to patients); CP-SAT for the real-time booking search path; SimPy simulation validating the CP-SAT allocator against the old greedy matcher (the project plan's own build order calls for this before adopting the heavier solver); and true interval-overlap booking protection across different-duration services (Postgres-only `EXCLUDE USING gist`, not portable to the SQLite dev setup).
