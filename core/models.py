import uuid

from django.conf import settings
from django.db import models


class UserProfile(models.Model):
    CONSUMER = "consumer"
    DIETITIAN = "dietitian"

    ROLE_CHOICES = [
        (CONSUMER, "Consumer"),
        (DIETITIAN, "Dietitian"),
    ]

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=CONSUMER,
    )

    def __str__(self):
        return f"{self.user.username} ({self.role})"


class MealLog(models.Model):
    MEAL_CHOICES = [
        ("breakfast", "Breakfast"),
        ("lunch", "Lunch"),
        ("dinner", "Dinner"),
        ("snack", "Snack"),
    ]

    consumer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="meal_logs",
    )
    meal_type = models.CharField(max_length=20, choices=MEAL_CHOICES)
    food_name = models.CharField(max_length=200)
    details = models.TextField(blank=True)
    calories = models.PositiveIntegerField(default=0)
    protein = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
    )
    carbohydrates = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
    )
    fats = models.DecimalField(
        max_digits=7,
        decimal_places=2,
        default=0,
    )
    logged_at = models.DateTimeField(auto_now_add=True)
    meal_date = models.DateField()

    class Meta:
        ordering = ["-meal_date", "-logged_at"]

    def __str__(self):
        return f"{self.food_name} - {self.consumer.username}"


class Appointment(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    consumer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consumer_appointments",
    )
    dietitian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="dietitian_appointments",
    )
    scheduled_at = models.DateTimeField()
    reason = models.TextField()

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    # Reason provided when an appointment is cancelled.
    cancellation_reason = models.TextField(
        blank=True,
        default="",
    )

    # Reason provided by the dietitian when rejecting a request.
    rejection_reason = models.TextField(
        blank=True,
        default="",
    )

    # Records who cancelled the appointment, if applicable.
    cancelled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="cancelled_appointments",
    )

    room_id = models.UUIDField(
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["scheduled_at"]

    def __str__(self):
        return f"Appointment #{self.pk} - {self.consumer.username}"


class ConsultationNote(models.Model):
    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="consultation_note",
    )
    dietitian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="consultation_notes",
    )
    notes = models.TextField()
    recommendations = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Notes for appointment #{self.appointment_id}"
