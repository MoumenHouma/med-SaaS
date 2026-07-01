"""
Rendia — Root URL Configuration
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

admin.site.site_header = "Rendia Admin"
admin.site.site_title = "Rendia"
admin.site.index_title = "Tableau de bord"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("django.contrib.auth.urls")),
    # App-level URL includes (to be expanded as views are built)
    path("", include("apps.core.urls")),
    path("clinics/", include("apps.clinics.urls")),
    path("patients/", include("apps.patients.urls")),
    path("scheduling/", include("apps.scheduling.urls")),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
