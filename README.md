# Rendia (med-SaaS)

Appointment & patient-flow optimization for independent clinics in Algeria. See `Rendia_Project_Plan.md` for the full product plan.

## Stack

Django 5.2, PostgreSQL (production) / SQLite (local dev), `python-decouple` for env config. Frontend and the optimization engine (OR-Tools, scikit-learn, SimPy) land in later phases — see the plan.

## Project layout

```
config/settings/    base.py (shared) + local.py (SQLite, DEBUG) + production.py (Postgres, hardened)
apps/core/           BaseModel (UUID PK, timestamps) — inherited by every model below
apps/clinics/        Clinic, Provider, Service, ClinicStaff (auth link for dashboard login)
apps/patients/       Patient (minimal PII, clinic-isolated — see Law 18-07 compliance note in the module docstring)
apps/scheduling/     SlotTemplate, Appointment, WaitlistEntry
apps/optimization/   OptimizationRun (audit log); services/ (predictor, scheduler, waitlist) not yet implemented
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

Schema and admin are in place for all five apps; migrations are generated and apply cleanly. No views/forms/booking flow yet — that's the Phase 1 MVP work per the project plan.
