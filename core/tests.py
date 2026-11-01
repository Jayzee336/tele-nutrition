from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .forms import AppointmentRequestForm
from .models import Appointment, ConsultationNote, MealLog, UserProfile
from .views import has_appointment_conflict


User = get_user_model()


class AppointmentSchedulingTests(TestCase):
    """Automated tests for NutriConnect scheduling and reliability."""

    def setUp(self):
        self.consumer = self.create_user(
            "schedule_consumer", UserProfile.CONSUMER
        )
        self.consumer2 = self.create_user(
            "schedule_consumer2", UserProfile.CONSUMER
        )
        self.dietitian = self.create_user(
            "schedule_dietitian", UserProfile.DIETITIAN
        )
        self.dietitian2 = self.create_user(
            "schedule_dietitian2", UserProfile.DIETITIAN
        )

        now = timezone.localtime(timezone.now())
        self.start_time = (
            now.replace(second=0, microsecond=0) + timedelta(days=7)
        )

    def create_user(self, username, role):
        user = User.objects.create_user(
            username=username,
            password="TestPassword123!",
        )
        UserProfile.objects.create(user=user, role=role)
        return user

    def create_appointment(
        self,
        *,
        consumer=None,
        dietitian=None,
        scheduled_at=None,
        status="pending",
    ):
        return Appointment.objects.create(
            consumer=consumer or self.consumer,
            dietitian=dietitian or self.dietitian,
            scheduled_at=scheduled_at or self.start_time,
            reason="Automated scheduling test",
            status=status,
        )

    # ---------------------------------------------------------
    # Scheduling and overlap tests
    # ---------------------------------------------------------

    def test_overlapping_approved_appointment_is_a_conflict(self):
        self.create_appointment(status="approved")

        conflict = has_appointment_conflict(
            consumer=self.consumer2,
            dietitian=self.dietitian,
            scheduled_at=self.start_time + timedelta(minutes=30),
        )

        self.assertTrue(conflict)

    def test_pending_appointment_does_not_block_a_slot(self):
        self.create_appointment(status="pending")

        conflict = has_appointment_conflict(
            consumer=self.consumer2,
            dietitian=self.dietitian,
            scheduled_at=self.start_time,
        )

        self.assertFalse(conflict)

    def test_back_to_back_appointments_are_allowed(self):
        self.create_appointment(status="approved")

        conflict = has_appointment_conflict(
            consumer=self.consumer2,
            dietitian=self.dietitian,
            scheduled_at=self.start_time + timedelta(minutes=60),
        )

        self.assertFalse(conflict)

    def test_one_minute_overlap_is_a_conflict(self):
        self.create_appointment(status="approved")

        conflict = has_appointment_conflict(
            consumer=self.consumer2,
            dietitian=self.dietitian,
            scheduled_at=self.start_time + timedelta(minutes=59),
        )

        self.assertTrue(conflict)

    def test_same_consumer_cannot_overlap_approved_appointments(self):
        self.create_appointment(status="approved")
        another_dietitian = self.create_user(
            "another_dietitian", UserProfile.DIETITIAN
        )

        conflict = has_appointment_conflict(
            consumer=self.consumer,
            dietitian=another_dietitian,
            scheduled_at=self.start_time + timedelta(minutes=30),
        )

        self.assertTrue(conflict)

    def test_cancelled_appointment_frees_the_time_slot(self):
        self.create_appointment(status="cancelled")

        conflict = has_appointment_conflict(
            consumer=self.consumer2,
            dietitian=self.dietitian,
            scheduled_at=self.start_time,
        )

        self.assertFalse(conflict)

    def test_consumer_request_conflicting_with_approved_slot_is_rejected(self):
        self.create_appointment(status="approved")
        self.client.force_login(self.consumer2)

        response = self.client.post(
            reverse("appointment_create"),
            {
                "dietitian": self.dietitian.pk,
                "scheduled_at": (
                    self.start_time + timedelta(minutes=30)
                ).strftime("%Y-%m-%dT%H:%M"),
                "reason": "I would like a nutrition consultation.",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            Appointment.objects.filter(
                consumer=self.consumer2,
                status="pending",
            ).exists()
        )
        self.assertIn("scheduled_at", response.context["form"].errors)

    def test_dietitian_cannot_approve_conflicting_request(self):
        self.create_appointment(status="approved")
        conflicting_request = self.create_appointment(
            consumer=self.consumer2,
            scheduled_at=self.start_time + timedelta(minutes=30),
            status="pending",
        )
        self.client.force_login(self.dietitian)

        response = self.client.post(
            reverse("appointment_status", args=[conflicting_request.pk]),
            {"status": "approved"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        conflicting_request.refresh_from_db()
        self.assertEqual(conflicting_request.status, "pending")

    def test_dietitian_can_approve_non_conflicting_request(self):
        appointment = self.create_appointment(
            scheduled_at=self.start_time + timedelta(hours=1),
            status="pending",
        )
        self.client.force_login(self.dietitian)

        response = self.client.post(
            reverse("appointment_status", args=[appointment.pk]),
            {"status": "approved"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "approved")

    # ---------------------------------------------------------
    # Cancellation tests
    # ---------------------------------------------------------

    def test_consumer_can_cancel_own_pending_appointment(self):
        appointment = self.create_appointment(status="pending")
        self.client.force_login(self.consumer)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "Schedule conflict"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")
        self.assertEqual(
            appointment.cancellation_reason, "Schedule conflict"
        )
        self.assertEqual(appointment.cancelled_by, self.consumer)

    def test_consumer_can_cancel_own_approved_appointment(self):
        appointment = self.create_appointment(status="approved")
        self.client.force_login(self.consumer)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "Unable to attend"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")
        self.assertEqual(
            appointment.cancellation_reason, "Unable to attend"
        )
        self.assertEqual(appointment.cancelled_by, self.consumer)

    def test_dietitian_can_cancel_assigned_pending_appointment(self):
        appointment = self.create_appointment(status="pending")
        self.client.force_login(self.dietitian)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "Scheduling unavailable"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")
        self.assertEqual(
            appointment.cancellation_reason, "Scheduling unavailable"
        )
        self.assertEqual(appointment.cancelled_by, self.dietitian)

    def test_dietitian_can_cancel_assigned_approved_appointment(self):
        appointment = self.create_appointment(status="approved")
        self.client.force_login(self.dietitian)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "Unexpected scheduling issue"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")
        self.assertEqual(
            appointment.cancellation_reason,
            "Unexpected scheduling issue",
        )
        self.assertEqual(appointment.cancelled_by, self.dietitian)

    def test_consumer_cannot_cancel_another_consumers_appointment(self):
        appointment = self.create_appointment(
            consumer=self.consumer,
            status="pending",
        )
        self.client.force_login(self.consumer2)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "Unauthorized attempt"},
        )

        self.assertEqual(response.status_code, 404)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "pending")
        self.assertEqual(appointment.cancellation_reason, "")

    def test_dietitian_cannot_cancel_another_dietitians_appointment(self):
        appointment = self.create_appointment(
            dietitian=self.dietitian,
            status="pending",
        )
        self.client.force_login(self.dietitian2)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "Unauthorized attempt"},
        )

        self.assertEqual(response.status_code, 404)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "pending")
        self.assertEqual(appointment.cancellation_reason, "")

    def test_consumer_cannot_cancel_completed_appointment(self):
        appointment = self.create_appointment(status="completed")
        self.client.force_login(self.consumer)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "Too late to cancel"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "completed")

    def test_consumer_cannot_cancel_rejected_appointment(self):
        appointment = self.create_appointment(status="rejected")
        self.client.force_login(self.consumer)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "Attempt to cancel rejected request"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "rejected")

    def test_cancel_requires_a_reason(self):
        appointment = self.create_appointment(status="pending")
        self.client.force_login(self.consumer)

        response = self.client.post(
            reverse("appointment_cancel", args=[appointment.pk]),
            {"cancellation_reason": "   "},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "pending")
        self.assertEqual(appointment.cancellation_reason, "")

    def test_cancel_endpoint_rejects_get_requests(self):
        appointment = self.create_appointment(status="pending")
        self.client.force_login(self.consumer)

        response = self.client.get(
            reverse("appointment_cancel", args=[appointment.pk])
        )

        self.assertEqual(response.status_code, 405)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "pending")

    # ---------------------------------------------------------
    # Appointment status transition tests
    # ---------------------------------------------------------

    def test_cancelled_appointment_cannot_be_approved(self):
        appointment = self.create_appointment(status="cancelled")
        self.client.force_login(self.dietitian)

        response = self.client.post(
            reverse("appointment_status", args=[appointment.pk]),
            {"status": "approved"},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")

    def test_cancelled_appointment_cannot_be_completed(self):
        appointment = self.create_appointment(status="cancelled")
        self.client.force_login(self.dietitian)

        response = self.client.post(
            reverse("appointment_complete", args=[appointment.pk])
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "cancelled")

    def test_dietitian_rejection_requires_a_reason(self):
        appointment = self.create_appointment(status="pending")
        self.client.force_login(self.dietitian)

        response = self.client.post(
            reverse("appointment_status", args=[appointment.pk]),
            {"status": "rejected", "rejection_reason": "   "},
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "pending")
        self.assertEqual(appointment.rejection_reason, "")

    def test_dietitian_can_reject_request_with_a_reason(self):
        appointment = self.create_appointment(status="pending")
        self.client.force_login(self.dietitian)
        reason = "I am unavailable at the requested time."

        response = self.client.post(
            reverse("appointment_status", args=[appointment.pk]),
            {
                "status": "rejected",
                "rejection_reason": reason,
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, "rejected")
        self.assertEqual(appointment.rejection_reason, reason)

    # ---------------------------------------------------------
    # Appointment form validation tests
    # ---------------------------------------------------------

    def test_form_rejects_past_appointment_time(self):
        past_time = (
            timezone.localtime(timezone.now()) - timedelta(days=1)
        ).strftime("%Y-%m-%dT%H:%M")

        form = AppointmentRequestForm(
            data={
                "dietitian": self.dietitian.pk,
                "scheduled_at": past_time,
                "reason": "I need nutrition advice.",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("scheduled_at", form.errors)

    def test_form_rejects_empty_reason(self):
        form = AppointmentRequestForm(
            data={
                "dietitian": self.dietitian.pk,
                "scheduled_at": self.start_time.strftime("%Y-%m-%dT%H:%M"),
                "reason": "",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("reason", form.errors)

    def test_form_rejects_whitespace_only_reason(self):
        form = AppointmentRequestForm(
            data={
                "dietitian": self.dietitian.pk,
                "scheduled_at": self.start_time.strftime("%Y-%m-%dT%H:%M"),
                "reason": "    ",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("reason", form.errors)

    def test_form_excludes_inactive_dietitians(self):
        self.dietitian.is_active = False
        self.dietitian.save(update_fields=["is_active"])

        form = AppointmentRequestForm(
            data={
                "dietitian": self.dietitian.pk,
                "scheduled_at": self.start_time.strftime("%Y-%m-%dT%H:%M"),
                "reason": "I need nutrition advice.",
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn("dietitian", form.errors)


class AuthorizationTests(TestCase):
    """Authorization and access-control tests for important views."""

    def setUp(self):
        self.consumer = User.objects.create_user(
            username="auth_consumer",
            password="TestPassword123!",
        )
        UserProfile.objects.create(user=self.consumer, role=UserProfile.CONSUMER)

        self.consumer2 = User.objects.create_user(
            username="auth_consumer2",
            password="TestPassword123!",
        )
        UserProfile.objects.create(user=self.consumer2, role=UserProfile.CONSUMER)

        self.dietitian = User.objects.create_user(
            username="auth_dietitian",
            password="TestPassword123!",
        )
        UserProfile.objects.create(user=self.dietitian, role=UserProfile.DIETITIAN)

        self.dietitian2 = User.objects.create_user(
            username="auth_dietitian2",
            password="TestPassword123!",
        )
        UserProfile.objects.create(user=self.dietitian2, role=UserProfile.DIETITIAN)

        self.appointment = Appointment.objects.create(
            consumer=self.consumer,
            dietitian=self.dietitian,
            scheduled_at=timezone.localtime(timezone.now()) + timedelta(days=7),
            reason="Test authorization",
            status="approved",
        )
        self.note = ConsultationNote.objects.create(
            appointment=self.appointment,
            dietitian=self.dietitian,
            notes="Clinical notes",
            recommendations="Eat more vegetables.",
        )

    # ---------------------------------------------------------
    # Video room authorization
    # ---------------------------------------------------------

    def test_video_room_allows_assigned_consumer(self):
        self.client.force_login(self.consumer)
        response = self.client.get(
            reverse("video_room", args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_video_room_allows_assigned_dietitian(self):
        self.client.force_login(self.dietitian)
        response = self.client.get(
            reverse("video_room", args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_video_room_denies_wrong_consumer(self):
        self.client.force_login(self.consumer2)
        response = self.client.get(
            reverse("video_room", args=[self.appointment.pk])
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_video_room_denies_wrong_dietitian(self):
        self.client.force_login(self.dietitian2)
        response = self.client.get(
            reverse("video_room", args=[self.appointment.pk])
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_video_room_denies_unauthenticated(self):
        response = self.client.get(
            reverse("video_room", args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 302)  # redirect to login

    def test_video_room_denies_unapproved_appointment(self):
        pending = Appointment.objects.create(
            consumer=self.consumer,
            dietitian=self.dietitian,
            scheduled_at=timezone.localtime(timezone.now()) + timedelta(days=7),
            reason="Pending",
            status="pending",
        )
        self.client.force_login(self.consumer)
        response = self.client.get(reverse("video_room", args=[pending.pk]))
        self.assertRedirects(response, reverse("dashboard"))

    # ---------------------------------------------------------
    # Consultation note authorization
    # ---------------------------------------------------------

    def test_note_view_allows_assigned_dietitian(self):
        self.client.force_login(self.dietitian)
        response = self.client.get(
            reverse("consultation_note", args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_note_view_denies_wrong_dietitian(self):
        self.client.force_login(self.dietitian2)
        response = self.client.get(
            reverse("consultation_note", args=[self.appointment.pk])
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_note_view_denies_consumer(self):
        self.client.force_login(self.consumer)
        response = self.client.get(
            reverse("consultation_note", args=[self.appointment.pk])
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_note_view_denies_for_pending_appointment(self):
        pending = Appointment.objects.create(
            consumer=self.consumer,
            dietitian=self.dietitian,
            scheduled_at=timezone.localtime(timezone.now()) + timedelta(days=7),
            reason="Pending",
            status="pending",
        )
        self.client.force_login(self.dietitian)
        response = self.client.get(
            reverse("consultation_note", args=[pending.pk])
        )
        self.assertRedirects(response, reverse("dashboard"))

    # ---------------------------------------------------------
    # Consumer recommendations authorization
    # ---------------------------------------------------------

    def test_recommendations_allows_assigned_consumer_for_completed(self):
        completed = Appointment.objects.create(
            consumer=self.consumer,
            dietitian=self.dietitian,
            scheduled_at=timezone.localtime(timezone.now()) + timedelta(days=7),
            reason="Completed",
            status="completed",
        )
        ConsultationNote.objects.create(
            appointment=completed,
            dietitian=self.dietitian,
            notes="Notes",
            recommendations="Recommendations",
        )
        self.client.force_login(self.consumer)
        response = self.client.get(
            reverse("consumer_recommendations", args=[completed.pk])
        )
        self.assertEqual(response.status_code, 200)

    def test_recommendations_denies_wrong_consumer(self):
        self.client.force_login(self.consumer2)
        response = self.client.get(
            reverse("consumer_recommendations", args=[self.appointment.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_recommendations_denies_for_non_completed(self):
        pending = Appointment.objects.create(
            consumer=self.consumer,
            dietitian=self.dietitian,
            scheduled_at=timezone.localtime(timezone.now()) + timedelta(days=7),
            reason="Pending",
            status="approved",
        )
        self.client.force_login(self.consumer)
        response = self.client.get(
            reverse("consumer_recommendations", args=[pending.pk])
        )
        self.assertEqual(response.status_code, 404)

    # ---------------------------------------------------------
    # Meal log access control
    # ---------------------------------------------------------

    def test_meal_create_denies_dietitian(self):
        self.client.force_login(self.dietitian)
        response = self.client.get(reverse("meal_create"))
        self.assertRedirects(response, reverse("dashboard"))

    def test_meal_create_allows_consumer(self):
        self.client.force_login(self.consumer)
        response = self.client.get(reverse("meal_create"))
        self.assertEqual(response.status_code, 200)


class PublicRegistrationSecurityTests(TestCase):
    """Public sign-up must not allow users to self-assign privileged roles."""

    def test_registration_page_does_not_offer_a_role_selector(self):
        response = self.client.get(reverse("register"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="role"')

    def test_registration_always_creates_a_consumer_profile(self):
        response = self.client.post(
            reverse("register"),
            {
                "username": "newconsumer",
                "email": "newconsumer@example.com",
                "password1": "S!trongPass-9046x",
                "password2": "S!trongPass-9046x",
                # A crafted request must not grant dietitian privileges.
                "role": UserProfile.DIETITIAN,
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = User.objects.get(username="newconsumer")
        self.assertEqual(user.profile.role, UserProfile.CONSUMER)
