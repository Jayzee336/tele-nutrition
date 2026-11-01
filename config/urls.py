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

    # Custom Admin Dashboard
    path(
        "admin-dashboard/",
        views.admin_dashboard_view,
        name="admin_dashboard",
    ),
    path(
        "admin-dashboard/users/",
        views.admin_users_view,
        name="admin_users",
    ),
    path(
        "admin-dashboard/users/create/",
        views.admin_user_create_view,
        name="admin_user_create",
    ),
    path(
        "admin-dashboard/users/<int:user_id>/",
        views.admin_user_detail_view,
        name="admin_user_detail",
    ),
    path(
        "admin-dashboard/users/<int:user_id>/edit/",
        views.admin_user_edit_view,
        name="admin_user_edit",
    ),
    path(
        "admin-dashboard/users/<int:user_id>/toggle-active/",
        views.admin_user_toggle_active_view,
        name="admin_user_toggle_active",
    ),

    path(
        "admin-dashboard/dietitians/",
        views.admin_dietitians_view,
        name="admin_dietitians",
    ),
    path(
        "admin-dashboard/dietitians/create/",
        views.admin_dietitian_create_view,
        name="admin_dietitian_create",
    ),
    path(
        "admin-dashboard/dietitians/<int:user_id>/",
        views.admin_dietitian_detail_view,
        name="admin_dietitian_detail",
    ),
    path(
        "admin-dashboard/dietitians/<int:user_id>/edit/",
        views.admin_dietitian_edit_view,
        name="admin_dietitian_edit",
    ),
    path(
        "admin-dashboard/dietitians/<int:user_id>/toggle-active/",
        views.admin_dietitian_toggle_active_view,
        name="admin_dietitian_toggle_active",
    ),
    path(
        "admin-dashboard/consumers/",
        views.admin_consumers_view,
        name="admin_consumers",
    ),
    path(
        "admin-dashboard/consumers/<int:user_id>/",
        views.admin_consumer_detail_view,
        name="admin_consumer_detail",
    ),
    path(
        "admin-dashboard/consumers/<int:user_id>/toggle-active/",
        views.admin_consumer_toggle_active_view,
        name="admin_consumer_toggle_active",
    ),
    path(
        "admin-dashboard/appointments/",
        views.admin_appointments_view,
        name="admin_appointments",
    ),
    path(
        "admin-dashboard/appointments/<int:appointment_id>/",
        views.admin_appointment_detail_view,
        name="admin_appointment_detail",
    ),
]
