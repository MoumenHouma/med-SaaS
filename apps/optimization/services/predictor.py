"""
No-show prediction (project plan, section 2.1).

Cold start: every clinic opens with a literature-based heuristic (outpatient
no-show rates are commonly cited in the 15-30% range) nudged by two
well-documented correlates -- booking lead time and reminder acknowledgement.

Once a clinic has enough resolved appointment history (COMPLETED or NO_SHOW),
it switches to a per-clinic logistic regression trained on lead time, day of
week, hour of day, whether a reminder was sent, and the patient's own prior
no-show rate. Retraining happens on every scheduled run rather than being
persisted -- clinic-scale data is small enough that this is cheap, and it
keeps the model always current with the latest history.
"""

from apps.scheduling.models import Appointment

BASE_NO_SHOW_RATE = 0.20
MIN_TRAINING_SAMPLES = 30
_RESOLVED_STATUSES = [Appointment.Status.COMPLETED, Appointment.Status.NO_SHOW]


def heuristic_probability(appointment):
    """Literature base rate, adjusted for lead time and reminder response."""
    probability = BASE_NO_SHOW_RATE

    lead_time = appointment.lead_time_days or 0
    if lead_time > 14:
        probability += 0.10
    elif lead_time > 7:
        probability += 0.05
    elif lead_time <= 1:
        probability -= 0.05

    if appointment.reminder_acknowledged:
        probability -= 0.08
    elif appointment.reminder_sent:
        probability -= 0.03

    return min(max(probability, 0.01), 0.95)


def _patient_prior_no_show_rate(patient, exclude_appointment_id=None):
    qs = Appointment.objects.filter(patient=patient, status__in=_RESOLVED_STATUSES)
    if exclude_appointment_id:
        qs = qs.exclude(id=exclude_appointment_id)
    total = qs.count()
    if not total:
        return BASE_NO_SHOW_RATE
    no_shows = qs.filter(status=Appointment.Status.NO_SHOW).count()
    return no_shows / total


def _feature_vector(appointment, prior_rate):
    start = appointment.scheduled_start
    return [
        appointment.lead_time_days or 0,
        start.weekday(),
        start.hour,
        int(bool(appointment.reminder_sent)),
        prior_rate,
    ]


def train_model(clinic):
    """
    Fits a logistic regression on the clinic's resolved appointment history.
    Returns None (triggering the heuristic fallback) if there isn't enough
    history yet, or if it's all one class (a classifier can't be fit on a
    clinic with zero recorded no-shows).
    """
    from sklearn.linear_model import LogisticRegression

    history = list(
        Appointment.objects.filter(
            provider__clinic=clinic, status__in=_RESOLVED_STATUSES
        ).select_related("patient")
    )
    if len(history) < MIN_TRAINING_SAMPLES:
        return None

    features, labels = [], []
    for appt in history:
        prior_rate = _patient_prior_no_show_rate(appt.patient, exclude_appointment_id=appt.id)
        features.append(_feature_vector(appt, prior_rate))
        labels.append(1 if appt.status == Appointment.Status.NO_SHOW else 0)

    if len(set(labels)) < 2:
        return None

    model = LogisticRegression(max_iter=1000)
    model.fit(features, labels)
    return model


def predict_probability(appointment, model=None):
    """
    Returns (probability, used_learned_model). Pass a pre-trained `model`
    (see train_model) to avoid retraining per appointment when scoring a
    whole clinic's schedule in one batch run.
    """
    if model is None:
        return heuristic_probability(appointment), False

    prior_rate = _patient_prior_no_show_rate(appointment.patient, exclude_appointment_id=appointment.id)
    features = [_feature_vector(appointment, prior_rate)]
    probability = float(model.predict_proba(features)[0][1])
    return probability, True
