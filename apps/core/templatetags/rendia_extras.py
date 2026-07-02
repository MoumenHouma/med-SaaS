from django import template

register = template.Library()

# Shared across every template that shows an Appointment status badge
# (dashboard, appointment_manage), so the color mapping stays in one place.
_STATUS_BADGE_CLASSES = {
    "completed": "bg-green-50 text-green-700 border border-green-200",
    "cancelled": "bg-gray-100 text-gray-500 border border-gray-200",
    "no_show": "bg-gray-100 text-gray-500 border border-gray-200",
    "checked_in": "bg-blue-50 text-blue-700 border border-blue-200",
}
_DEFAULT_STATUS_BADGE_CLASSES = "bg-amber-50 text-amber-700 border border-amber-200"


@register.filter
def status_badge_class(status):
    return _STATUS_BADGE_CLASSES.get(status, _DEFAULT_STATUS_BADGE_CLASSES)
