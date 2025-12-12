# core/urls.py
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from lms.views import CustomLoginView

urlpatterns = [
    path("admin/", admin.site.urls),

    # Auth (login, logout, password reset, etc.)
    # Usa las vistas por defecto de Django en /login, /logout, /password_reset, etc.
    path("login/", CustomLoginView.as_view(template_name="registration/login.html"), name="login"),
    path("", include("django.contrib.auth.urls")),

    # App LMS
    path("", include("lms.urls")),
]

# Servir archivos de MEDIA en desarrollo (avatares, comprobantes, etc.)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
