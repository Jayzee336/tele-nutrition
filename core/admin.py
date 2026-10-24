from django.contrib import admin

from .models import (
    Appointment,
    ConsultationNote,
    MealLog,
    UserProfile,
)


@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)
    search_fields = ("user__username", "user__email")


@admin.register(MealLog)
class MealLogAdmin(admin.ModelAdmin):
    list_display = (
        "food_name",
        "consumer",
        "meal_type",
        "meal_date",
        "calories",
    )
    list_filter = ("meal_type", "meal_date")
    search_fields = ("food_name", "consumer__username")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("id", "consumer", "dietitian", "scheduled_at", "status")
    list_filter = ("status",)
    search_fields = ("consumer__username", "dietitian__username")


@admin.register(ConsultationNote)
class ConsultationNoteAdmin(admin.ModelAdmin):
    list_display = ("appointment", "dietitian", "updated_at")
    search_fields = ("dietitian__username",)
