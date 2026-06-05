"""
URL configuration for app project.
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from aps import views

urlpatterns = [
    path("admin/", admin.site.urls),
    path(
        "login/",
        auth_views.LoginView.as_view(template_name="aps/login.html"),
        name="login",
    ),
    path("logout/", views.logout_view, name="logout"),
    path("", include("aps.urls")),
]

from django.urls import re_path
from django.views.static import serve

# Serve media files (even in production since Whitenoise only handles static)
urlpatterns += [
    re_path(r'^media/(?P<path>.*)$', serve, {'document_root': settings.MEDIA_ROOT}),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
