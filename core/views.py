from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import models, transaction
from django.db.models import Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import (
    AppointmentRequestForm,
    ConsultationNoteForm,
    MealLogForm,
    RegistrationForm,
)
from .models import (
    Appointment,
    ConsultationNote,
    MealLog,
    UserProfile,
)


# Each consultation occupies a 60-minute time slot.
APPOINTMENT_DURATION = timedelta(minutes=60)


def admin_required(view_func):
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect(
                f"{reverse('login')}?next={request.path}"
            )
        if request.user.is_superuser:
            return view_func(request, *args, **kwargs)
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden(
            "Access denied: Administrator privileges required."
        )
    wrapper.__name__ = view_func.__name__
    return wrapper


def has_appointment_conflict(
    *,
    consumer,
    dietitian,
    scheduled_at,
    exclude_appointment_id=None,
):
    """
    Return True if an approved appointment overlaps the proposed
    time slot for the same consumer or dietitian.

    Pending, rejected, cancelled, and completed appointments do
    not block a slot.
    """
    proposed_end = scheduled_at + APPOINTMENT_DURATION

    conflicts = Appointment.objects.filter(
        status="approved",
        scheduled_at__lt=proposed_end,
        scheduled_at__gt=scheduled_at - APPOINTMENT_DURATION,
    ).filter(
        models.Q(consumer=consumer)
        | models.Q(dietitian=dietitian)
    )

    if exclude_appointment_id is not None:
        conflicts = conflicts.exclude(pk=exclude_appointment_id)

    for existing in conflicts:
        existing_end = existing.scheduled_at + APPOINTMENT_DURATION

        # Half-open intervals allow back-to-back appointments.
        if (
            existing.scheduled_at < proposed_end
            and existing_end > scheduled_at
        ):
            return True

    return False


def register_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = RegistrationForm(request.POST)

        if form.is_valid():
            user = form.save()
            user.backend = "core.authentication.EmailOrUsernameBackend"
            login(request, user)

            messages.success(
                request,
                "Your NutriConnect account has been created successfully.",
            )
            return redirect("dashboard")
    else:
        form = RegistrationForm()

    return render(
        request,
        "registration/register.html",
        {"form": form},
    )


@login_required
def dashboard_view(request):
    # Superusers must be routed to the custom Admin Dashboard.
    if request.user.is_superuser:
        return redirect("admin_dashboard")

    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # DIETITIAN DASHBOARD
    if profile.role == UserProfile.DIETITIAN:
        appointments = (
            Appointment.objects.filter(dietitian=request.user)
            .select_related("consumer", "cancelled_by")
            .prefetch_related("consultation_note")
            .order_by("scheduled_at")
        )

        # Only show meal logs for consumers with an approved or
        # completed appointment with this dietitian.
        patient_ids = (
            appointments.filter(status__in=["approved", "completed"])
            .values_list("consumer_id", flat=True)
            .distinct()
        )

        patient_meals = (
            MealLog.objects.filter(consumer_id__in=patient_ids)
            .select_related("consumer")
            .order_by("-meal_date", "-logged_at")[:50]
        )

        context = {
            "appointments": appointments,
            "pending_count": appointments.filter(status="pending").count(),
            "patient_count": (
                appointments.values("consumer_id")
                .distinct()
                .count()
            ),
            "patient_meals": patient_meals,
        }

        return render(
            request,
            "core/dietitian_dashboard.html",
            context,
        )

    # CONSUMER DASHBOARD
    today = timezone.localdate()

    today_meals = MealLog.objects.filter(
        consumer=request.user,
        meal_date=today,
    )

    totals = today_meals.aggregate(
        total_calories=Sum("calories"),
        total_protein=Sum("protein"),
        total_carbohydrates=Sum("carbohydrates"),
        total_fats=Sum("fats"),
    )

    all_meals = MealLog.objects.filter(consumer=request.user)

    appointments = (
        Appointment.objects.filter(consumer=request.user)
        .select_related("dietitian", "cancelled_by")
        .prefetch_related("consultation_note")
        .order_by("-scheduled_at")
    )

    context = {
        "meals": all_meals.order_by("-logged_at")[:10],
        "today_meals": today_meals.count(),
        "total_calories": totals["total_calories"] or 0,
        "total_protein": totals["total_protein"] or 0,
        "total_carbohydrates": totals["total_carbohydrates"] or 0,
        "total_fats": totals["total_fats"] or 0,
        "total_entries": all_meals.count(),
        "appointments": appointments[:5],
    }

    return render(
        request,
        "core/consumer_dashboard.html",
        context,
    )


@login_required
def meal_create_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if profile.role != UserProfile.CONSUMER:
        messages.error(
            request,
            "Only consumer accounts can log meals.",
        )
        return redirect("dashboard")

    if request.method == "POST":
        form = MealLogForm(request.POST)

        if form.is_valid():
            meal = form.save(commit=False)
            meal.consumer = request.user
            meal.save()

            messages.success(
                request,
                "Your meal has been logged successfully.",
            )
            return redirect("dashboard")
    else:
        form = MealLogForm()

    return render(
        request,
        "core/meal_form.html",
        {"form": form},
    )


@login_required
def appointment_create_view(request):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if profile.role != UserProfile.CONSUMER:
        messages.error(
            request,
            "Only consumer accounts can request consultations.",
        )
        return redirect("dashboard")

    if request.method == "POST":
        form = AppointmentRequestForm(request.POST)

        if form.is_valid():
            consumer = request.user
            dietitian = form.cleaned_data["dietitian"]
            scheduled_at = form.cleaned_data["scheduled_at"]

            if scheduled_at <= timezone.now():
                form.add_error(
                    "scheduled_at",
                    "Please select a future appointment time.",
                )
            elif has_appointment_conflict(
                consumer=consumer,
                dietitian=dietitian,
                scheduled_at=scheduled_at,
            ):
                form.add_error(
                    "scheduled_at",
                    "This time conflicts with an existing approved "
                    "appointment. Please choose another time.",
                )
            else:
                appointment = form.save(commit=False)
                appointment.consumer = consumer
                appointment.status = "pending"
                appointment.save()

                messages.success(
                    request,
                    "Your consultation request has been submitted.",
                )
                return redirect("dashboard")
    else:
        form = AppointmentRequestForm()

    return render(
        request,
        "core/appointment_form.html",
        {"form": form},
    )


@login_required
@require_POST
def appointment_status_view(request, appointment_id):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if profile.role != UserProfile.DIETITIAN:
        messages.error(
            request,
            "Only dietitians can review consultation requests.",
        )
        return redirect("dashboard")

    new_status = request.POST.get("status")

    if new_status not in ("approved", "rejected"):
        messages.error(request, "Invalid appointment status.")
        return redirect("dashboard")

    rejection_reason = ""

    if new_status == "rejected":
        rejection_reason = request.POST.get(
            "rejection_reason",
            "",
        ).strip()

        if not rejection_reason:
            messages.error(
                request,
                "Please provide a reason for rejecting this request.",
            )
            return redirect("dashboard")

        if len(rejection_reason) > 2000:
            messages.error(
                request,
                "The rejection reason must be 2000 characters or fewer.",
            )
            return redirect("dashboard")

    with transaction.atomic():
        appointment = get_object_or_404(
            Appointment.objects.select_for_update(),
            pk=appointment_id,
            dietitian=request.user,
        )

        if appointment.status != "pending":
            messages.warning(
                request,
                "This appointment has already been processed.",
            )
            return redirect("dashboard")

        if new_status == "approved":
            if appointment.scheduled_at <= timezone.now():
                messages.error(
                    request,
                    "Past appointment times cannot be approved.",
                )
                return redirect("dashboard")

            if has_appointment_conflict(
                consumer=appointment.consumer,
                dietitian=appointment.dietitian,
                scheduled_at=appointment.scheduled_at,
                exclude_appointment_id=appointment.pk,
            ):
                messages.error(
                    request,
                    "This request conflicts with another approved "
                    "appointment. It has not been approved. "
                    "Please resolve the scheduling conflict first.",
                )
                return redirect("dashboard")

            appointment.status = "approved"
            appointment.save(update_fields=["status"])
        else:
            appointment.status = "rejected"
            appointment.rejection_reason = rejection_reason
            appointment.save(
                update_fields=["status", "rejection_reason"],
            )

    if new_status == "approved":
        messages.success(
            request,
            "The consultation request has been approved.",
        )
    else:
        messages.success(
            request,
            "The consultation request has been rejected.",
        )

    return redirect("dashboard")


@login_required
@require_POST
def appointment_cancel_view(request, appointment_id):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    # Determine which appointments the current user may access.
    if profile.role == UserProfile.CONSUMER:
        ownership_filter = models.Q(consumer=request.user)
    elif profile.role == UserProfile.DIETITIAN:
        ownership_filter = models.Q(dietitian=request.user)
    else:
        messages.error(
            request,
            "You are not authorized to cancel appointments.",
        )
        return redirect("dashboard")

    cancellation_reason = request.POST.get(
        "cancellation_reason",
        "",
    ).strip()

    if not cancellation_reason:
        messages.error(
            request,
            "Please provide a reason for cancelling the appointment.",
        )
        return redirect("dashboard")

    if len(cancellation_reason) > 2000:
        messages.error(
            request,
            "The cancellation reason must be 2000 characters or fewer.",
        )
        return redirect("dashboard")

    with transaction.atomic():
        appointment = get_object_or_404(
            Appointment.objects.select_for_update().filter(
                ownership_filter,
            ),
            pk=appointment_id,
        )

        if appointment.status not in ("pending", "approved"):
            messages.warning(
                request,
                "Only pending or approved appointments can be cancelled.",
            )
            return redirect("dashboard")

        appointment.status = "cancelled"
        appointment.cancellation_reason = cancellation_reason
        appointment.cancelled_by = request.user

        appointment.save(
            update_fields=[
                "status",
                "cancellation_reason",
                "cancelled_by",
            ],
        )

    messages.success(
        request,
        "The appointment has been cancelled successfully.",
    )
    return redirect("dashboard")


@login_required
def video_room_view(request, appointment_id):
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
    )

    is_consumer = appointment.consumer_id == request.user.id
    is_dietitian = appointment.dietitian_id == request.user.id

    if not (is_consumer or is_dietitian):
        messages.error(
            request,
            "You are not authorized to access this consultation.",
        )
        return redirect("dashboard")

    if appointment.status != "approved":
        messages.warning(
            request,
            "The consultation room is available only after approval.",
        )
        return redirect("dashboard")

    room_url = f"https://meet.jit.si/NutriConnect-{appointment.room_id}"

    return render(
        request,
        "core/video_room.html",
        {
            "appointment": appointment,
            "room_url": room_url,
        },
    )


@login_required
def consultation_note_view(request, appointment_id):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    appointment = get_object_or_404(
        Appointment.objects.select_related("consumer", "dietitian"),
        pk=appointment_id,
    )

    # Only the assigned dietitian can manage consultation notes.
    if (
        profile.role != UserProfile.DIETITIAN
        or appointment.dietitian_id != request.user.id
    ):
        messages.error(
            request,
            "You are not authorized to manage these consultation notes.",
        )
        return redirect("dashboard")

    # Notes can only be managed for approved or completed appointments.
    if appointment.status not in ("approved", "completed"):
        messages.warning(
            request,
            "Notes can only be managed for approved or completed consultations.",
        )
        return redirect("dashboard")

    note = ConsultationNote.objects.filter(
        appointment=appointment,
    ).first()

    if request.method == "POST":
        form = ConsultationNoteForm(
            request.POST,
            instance=note,
        )

        if form.is_valid():
            with transaction.atomic():
                note = form.save(commit=False)
                note.appointment = appointment
                note.dietitian = request.user
                note.save()

            messages.success(
                request,
                "Consultation notes and recommendations have been saved.",
            )
            return redirect(
                "consultation_note",
                appointment_id=appointment.id,
            )
    else:
        form = ConsultationNoteForm(instance=note)

    return render(
        request,
        "core/consultation_note_form.html",
        {
            "appointment": appointment,
            "form": form,
            "note": note,
        },
    )


@login_required
@require_POST
def appointment_complete_view(request, appointment_id):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if profile.role != UserProfile.DIETITIAN:
        messages.error(
            request,
            "Only dietitians can complete consultations.",
        )
        return redirect("dashboard")

    with transaction.atomic():
        appointment = get_object_or_404(
            Appointment.objects.select_for_update(),
            pk=appointment_id,
            dietitian=request.user,
        )

        if appointment.status != "approved":
            messages.warning(
                request,
                "Only approved appointments can be marked as completed.",
            )
            return redirect("dashboard")

        note_exists = ConsultationNote.objects.filter(
            appointment=appointment,
            dietitian=request.user,
        ).exists()

        if not note_exists:
            messages.error(
                request,
                "Save the consultation notes before completing this appointment.",
            )
            return redirect(
                "consultation_note",
                appointment_id=appointment.id,
            )

        appointment.status = "completed"
        appointment.save(update_fields=["status"])

    messages.success(
        request,
        "The consultation has been marked as completed.",
    )
    return redirect("dashboard")


@login_required
def consumer_recommendations_view(request, appointment_id):
    profile, _ = UserProfile.objects.get_or_create(user=request.user)

    if profile.role != UserProfile.CONSUMER:
        messages.error(
            request,
            "This page is available to consumer accounts only.",
        )
        return redirect("dashboard")

    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
        consumer=request.user,
        status="completed",
    )

    note = get_object_or_404(
        ConsultationNote,
        appointment=appointment,
    )

    # Expose recommendations only, never private dietitian notes.
    return render(
        request,
        "core/consumer_recommendations.html",
        {
            "appointment": appointment,
            "recommendations": note.recommendations,
        },
    )


@login_required
@require_POST
def logout_view(request):
    logout(request)
    messages.success(
        request,
        "You have been logged out successfully.",
    )
    return redirect("login")


# =====================================================================
# Custom Admin Dashboard Views
# =====================================================================

@admin_required
def admin_dashboard_view(request):
    total_users = User.objects.count()
    total_consumers = UserProfile.objects.filter(
        role=UserProfile.CONSUMER
    ).count()
    total_dietitians = UserProfile.objects.filter(
        role=UserProfile.DIETITIAN
    ).count()
    total_appointments = Appointment.objects.count()
    pending_appointments = Appointment.objects.filter(
        status="pending"
    ).count()
    approved_appointments = Appointment.objects.filter(
        status="approved"
    ).count()
    completed_appointments = Appointment.objects.filter(
        status="completed"
    ).count()
    recent_users = User.objects.order_by("-date_joined")[:10]

    context = {
        "total_users": total_users,
        "total_consumers": total_consumers,
        "total_dietitians": total_dietitians,
        "total_appointments": total_appointments,
        "pending_appointments": pending_appointments,
        "approved_appointments": approved_appointments,
        "completed_appointments": completed_appointments,
        "recent_users": recent_users,
    }
    return render(
        request,
        "core/admin_dashboard.html",
        context,
    )


@admin_required
def admin_users_view(request):
    users = User.objects.all().order_by("-date_joined")
    query = request.GET.get("q", "").strip()
    role_filter = request.GET.get("role", "").strip()
    active_filter = request.GET.get("active", "").strip()

    if query:
        users = users.filter(
            models.Q(username__icontains=query)
            | models.Q(email__icontains=query)
        )
    if role_filter:
        users = users.filter(profile__role=role_filter)
    if active_filter == "active":
        users = users.filter(is_active=True)
    elif active_filter == "inactive":
        users = users.filter(is_active=False)

    context = {"users": users, "request_get": request.GET}
    return render(request, "core/admin_users.html", context)


@admin_required
def admin_user_create_view(request):
    from django.contrib.auth.forms import UserCreationForm
    from django import forms

    class AdminUserCreateForm(UserCreationForm):
        email = forms.EmailField(required=True)

        class Meta:
            model = User
            fields = [
                "username",
                "email",
                "password1",
                "password2",
            ]

    if request.method == "POST":
        form = AdminUserCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            # Default new admin users to active; role set below.
            user.is_active = True
            user.save(update_fields=["is_active"])
            # Ensure profile exists (consumer by default); admin manages it later
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={"role": UserProfile.CONSUMER},
            )
            messages.success(
                request,
                "User account created successfully.",
            )
            return redirect("admin_users")
    else:
        form = AdminUserCreateForm()
    return render(
        request,
        "core/admin_user_create.html",
        {"form": form},
    )


@admin_required
def admin_user_detail_view(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(
        user=user, defaults={"role": UserProfile.CONSUMER}
    )
    context = {"user": user, "profile": profile}
    return render(
        request,
        "core/admin_user_detail.html",
        context,
    )


@admin_required
def admin_user_edit_view(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(
        user=user, defaults={"role": UserProfile.CONSUMER}
    )

    # Protect final superuser
    if user == request.user and user.is_superuser:
        messages.error(
            request,
            "You cannot deactivate your own administrator account.",
        )

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        role = request.POST.get("role", "").strip()
        is_active = request.POST.get("is_active", "") == "on"

        if not username:
            messages.error(request, "Username is required.")
        else:
            user.username = username
            user.email = email
            user.is_active = is_active
            user.save(update_fields=["username", "email", "is_active"])
            profile.role = role if role in [
                UserProfile.CONSUMER,
                UserProfile.DIETITIAN,
            ] else UserProfile.CONSUMER
            profile.save(update_fields=["role"])
            messages.success(
                request,
                "User updated successfully.",
            )
            return redirect("admin_user_detail", user_id=user.pk)

    context = {
        "user": user,
        "profile": profile,
        "roles": UserProfile.ROLE_CHOICES,
    }
    return render(
        request,
        "core/admin_user_edit.html",
        context,
    )


@admin_required
@require_POST
def admin_user_toggle_active_view(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    # Prevent deactivating the final superuser
    if user.is_superuser:
        superusers = User.objects.filter(is_superuser=True)
        if superusers.count() <= 1 and not user.is_active:
            messages.error(
                request,
                "Cannot deactivate the final superuser.",
            )
            return redirect("admin_users")

    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    status = "activated" if user.is_active else "deactivated"
    messages.success(
        request,
        f"User {user.username} has been {status}.",
    )
    return redirect("admin_users")


@admin_required
def admin_dietitians_view(request):
    dietitians = User.objects.filter(
        profile__role=UserProfile.DIETITIAN
    ).order_by("username")
    query = request.GET.get("q", "").strip()
    active_filter = request.GET.get("active", "").strip()
    if query:
        dietitians = dietitians.filter(
            models.Q(username__icontains=query)
            | models.Q(email__icontains=query)
        )
    if active_filter == "active":
        dietitians = dietitians.filter(is_active=True)
    elif active_filter == "inactive":
        dietitians = dietitians.filter(is_active=False)
    context = {
        "dietitians": dietitians,
        "request_get": request.GET,
    }
    return render(
        request,
        "core/admin_dietitians.html",
        context,
    )


@admin_required
def admin_dietitian_create_view(request):
    from django import forms
    from django.contrib.auth.forms import UserCreationForm

    class DietitianCreateForm(UserCreationForm):
        email = forms.EmailField(required=True)

        class Meta:
            model = User
            fields = [
                "username",
                "email",
                "password1",
                "password2",
            ]

    if request.method == "POST":
        form = DietitianCreateForm(request.POST)
        if form.is_valid():
            user = form.save()
            user.is_active = True
            user.save(update_fields=["is_active"])
            UserProfile.objects.create(
                user=user,
                role=UserProfile.DIETITIAN,
            )
            messages.success(
                request,
                "Dietitian account created successfully.",
            )
            return redirect("admin_dietitians")
    else:
        form = DietitianCreateForm()
    return render(
        request,
        "core/admin_dietitian_create.html",
        {"form": form},
    )


@admin_required
def admin_dietitian_detail_view(request, user_id):
    user = get_object_or_404(
        User,
        pk=user_id,
        profile__role=UserProfile.DIETITIAN,
    )
    profile = get_object_or_404(UserProfile, user=user)
    appointments = Appointment.objects.filter(
        dietitian=user
    ).select_related("consumer").order_by("-scheduled_at")[:10]
    context = {
        "user": user,
        "profile": profile,
        "appointments": appointments,
    }
    return render(
        request,
        "core/admin_dietitian_detail.html",
        context,
    )


@admin_required
def admin_dietitian_edit_view(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={"role": UserProfile.DIETITIAN},
    )

    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        email = request.POST.get("email", "").strip()
        is_active = request.POST.get("is_active", "") == "on"
        if not username:
            messages.error(request, "Username is required.")
        else:
            user.username = username
            user.email = email
            user.is_active = is_active
            user.save(update_fields=["username", "email", "is_active"])
            profile.role = UserProfile.DIETITIAN
            profile.save(update_fields=["role"])
            messages.success(
                request,
                "Dietitian updated successfully.",
            )
            return redirect(
                "admin_dietitian_detail",
                user_id=user.pk,
            )
    context = {
        "user": user,
        "profile": profile,
    }
    return render(
        request,
        "core/admin_dietitian_edit.html",
        context,
    )


@admin_required
@require_POST
def admin_dietitian_toggle_active_view(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    status = "activated" if user.is_active else "deactivated"
    messages.success(
        request,
        f"Dietitian {user.username} has been {status}.",
    )
    return redirect("admin_dietitians")


@admin_required
def admin_consumers_view(request):
    consumers = User.objects.filter(
        profile__role=UserProfile.CONSUMER
    ).order_by("-date_joined")
    query = request.GET.get("q", "").strip()
    active_filter = request.GET.get("active", "").strip()
    if query:
        consumers = consumers.filter(
            models.Q(username__icontains=query)
            | models.Q(email__icontains=query)
        )
    if active_filter == "active":
        consumers = consumers.filter(is_active=True)
    elif active_filter == "inactive":
        consumers = consumers.filter(is_active=False)
    context = {
        "consumers": consumers,
        "request_get": request.GET,
    }
    return render(
        request,
        "core/admin_consumers.html",
        context,
    )


@admin_required
def admin_consumer_detail_view(request, user_id):
    user = get_object_or_404(
        User,
        pk=user_id,
        profile__role=UserProfile.CONSUMER,
    )
    profile = get_object_or_404(UserProfile, user=user)
    appointments = Appointment.objects.filter(
        consumer=user
    ).select_related("dietitian").order_by("-scheduled_at")[:10]
    meal_logs = MealLog.objects.filter(
        consumer=user
    ).order_by("-meal_date", "-logged_at")[:10]
    context = {
        "user": user,
        "profile": profile,
        "appointments": appointments,
        "meal_logs": meal_logs,
    }
    return render(
        request,
        "core/admin_consumer_detail.html",
        context,
    )


@admin_required
@require_POST
def admin_consumer_toggle_active_view(request, user_id):
    user = get_object_or_404(User, pk=user_id)
    user.is_active = not user.is_active
    user.save(update_fields=["is_active"])
    status = "activated" if user.is_active else "deactivated"
    messages.success(
        request,
        f"Consumer {user.username} has been {status}.",
    )
    return redirect("admin_consumers")


@admin_required
def admin_appointments_view(request):
    appointments = Appointment.objects.select_related(
        "consumer", "dietitian", "cancelled_by"
    ).order_by("-scheduled_at")
    query = request.GET.get("q", "").strip()
    status_filter = request.GET.get("status", "").strip()
    if query:
        appointments = appointments.filter(
            models.Q(consumer__username__icontains=query)
            | models.Q(dietitian__username__icontains=query)
            | models.Q(reason__icontains=query)
        )
    if status_filter:
        appointments = appointments.filter(
            status=status_filter,
        )
    context = {
        "appointments": appointments,
        "request_get": request.GET,
        "status_choices": Appointment.STATUS_CHOICES,
    }
    return render(
        request,
        "core/admin_appointments.html",
        context,
    )


@admin_required
def admin_appointment_detail_view(request, appointment_id):
    appointment = get_object_or_404(
        Appointment,
        pk=appointment_id,
    )
    context = {"appointment": appointment}
    return render(
        request,
        "core/admin_appointment_detail.html",
        context,
    )
