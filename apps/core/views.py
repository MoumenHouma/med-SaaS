from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import RegisterForm


@login_required
def home(request):
    """
    Landing point after login. Routes the user to onboarding if they
    have no clinic yet, otherwise to their clinic dashboard.
    """
    if hasattr(request.user, "clinic_staff_profile"):
        return redirect("clinics:dashboard")
    return redirect("clinics:onboarding")


def register(request):
    if request.user.is_authenticated:
        return redirect("core:home")

    if request.method == "POST":
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("clinics:onboarding")
    else:
        form = RegisterForm()

    return render(request, "core/register.html", {"form": form})
