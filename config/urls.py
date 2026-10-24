from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import path

from core import views


urlpatterns = [
    # Admin
    path("admin/", admin.site.urls),

    # Authentication
    path(
        "accounts/login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html",
        ),
        name="login",
    ),
    path(
        "accounts/register/",
        views.register_view,
        name="register",
    ),
    path(
        "accounts/logout/",
        views.logout_view,
        name="logout",
    ),

    # Meal logging
    path(
        "meals/add/",
        views.meal_create_view,
        name="meal_create",
    ),

    # Consultation requests, review, and cancellation
    path(
        "appointments/request/",
        views.appointment_create_view,
        name="appointment_create",
    ),
    path(
        "appointments/<int:appointment_id>/review/",
        views.appointment_status_view,
        name="appointment_status",
    ),
    path(
        "appointments/<int:appointment_id>/cancel/",
        views.appointment_cancel_view,
        name="appointment_cancel",
    ),

    # Video consultations
    path(
        "appointments/<int:appointment_id>/video/",
        views.video_room_view,
        name="video_room",
    ),

    # Consultation notes and completion
    path(
        "appointments/<int:appointment_id>/notes/",
        views.consultation_note_view,
        name="consultation_note",
    ),
    path(
        "appointments/<int:appointment_id>/complete/",
        views.appointment_complete_view,
        name="appointment_complete",
    ),

    # Consumer recommendations
    path(
        "appointments/<int:appointment_id>/recommendations/",
        views.consumer_recommendations_view,
        name="consumer_recommendations",
    ),

    # Main dashboard
    path(
        "",
        views.dashboard_view,
        name="dashboard",
    ),
]
