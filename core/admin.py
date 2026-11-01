from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    Appointment,
    ConsultationNote,
    MealLog,
    UserProfile,
)


class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = "Profile"
    fields = ("role",)


# Integrate profile management into the user admin so a superadmin
# can create or edit a user and set their role in one operation.
admin.site.unregister(User)

@admin.register(User)
class CustomUserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ("username", "email", "is_active", "get_role")
    list_filter = ("is_active", "is_staff", "is_superuser", "profile__role")
    search_fields = ("username", "email", "profile__user__username")

    def get_role(self, obj):
        return obj.profile.role
    get_role.short_description = "Role"
    get_role.admin_order_field = "profile__role"


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
