from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from django.utils import timezone

from .models import (
    Appointment,
    ConsultationNote,
    MealLog,
    UserProfile,
)


class RegistrationForm(UserCreationForm):
    email = forms.EmailField(required=True)

    role = forms.ChoiceField(
        choices=[
            (UserProfile.CONSUMER, "Consumer"),
            (UserProfile.DIETITIAN, "Dietitian"),
        ],
        widget=forms.Select(
            attrs={"class": "form-control"}
        ),
    )

    class Meta:
        model = User
        fields = [
            "username",
            "email",
            "role",
            "password1",
            "password2",
        ]

    def save(self, commit=True):
        user = super().save(commit=commit)

        if commit:
            user.email = self.cleaned_data["email"]
            user.save(update_fields=["email"])

            UserProfile.objects.create(
                user=user,
                role=self.cleaned_data["role"],
            )

        return user


class MealLogForm(forms.ModelForm):
    class Meta:
        model = MealLog
        fields = [
            "meal_type",
            "food_name",
            "details",
            "calories",
            "protein",
            "carbohydrates",
            "fats",
            "meal_date",
        ]

        widgets = {
            "meal_type": forms.Select(
                attrs={"class": "form-control"}
            ),
            "food_name": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "e.g. Chicken adobo with rice",
                }
            ),
            "details": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "placeholder": "Optional serving size or meal notes",
                    "rows": 3,
                }
            ),
            "calories": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "1",
                }
            ),
            "protein": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "carbohydrates": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "fats": forms.NumberInput(
                attrs={
                    "class": "form-control",
                    "min": "0",
                    "step": "0.01",
                }
            ),
            "meal_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
        }

    def clean_food_name(self):
        food_name = self.cleaned_data["food_name"].strip()

        if not food_name:
            raise forms.ValidationError(
                "Please enter the name of the food."
            )

        return food_name

    def clean(self):
        cleaned_data = super().clean()

        for field in [
            "calories",
            "protein",
            "carbohydrates",
            "fats",
        ]:
            value = cleaned_data.get(field)

            if value is not None and value < 0:
                self.add_error(
                    field,
                    "Nutrition values cannot be negative.",
                )

        return cleaned_data


class AppointmentRequestForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ["dietitian", "scheduled_at", "reason"]

        widgets = {
            "dietitian": forms.Select(
                attrs={"class": "form-control"}
            ),
            "scheduled_at": forms.DateTimeInput(
                attrs={
                    "class": "form-control",
                    "type": "datetime-local",
                },
                format="%Y-%m-%dT%H:%M",
            ),
            "reason": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 4,
                    "placeholder": (
                        "Briefly describe what you would like "
                        "help with during your consultation."
                    ),
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.fields["dietitian"].queryset = User.objects.filter(
            profile__role=UserProfile.DIETITIAN,
            is_active=True,
        ).order_by("username")

        self.fields["scheduled_at"].input_formats = [
            "%Y-%m-%dT%H:%M",
        ]

    def clean_scheduled_at(self):
        scheduled_at = self.cleaned_data["scheduled_at"]

        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(
                scheduled_at,
                timezone.get_current_timezone(),
            )

        if scheduled_at <= timezone.now():
            raise forms.ValidationError(
                "Please choose a future date and time."
            )

        return scheduled_at

    def clean_reason(self):
        reason = self.cleaned_data["reason"].strip()

        if not reason:
            raise forms.ValidationError(
                "Please provide a reason for your appointment."
            )

        return reason


class ConsultationNoteForm(forms.ModelForm):
    class Meta:
        model = ConsultationNote
        fields = ["notes", "recommendations"]

        labels = {
            "notes": "Private Consultation Notes",
            "recommendations": "Nutrition Recommendations",
        }

        help_texts = {
            "notes": (
                "For the assigned dietitian's clinical documentation. "
                "Do not include unnecessary sensitive information."
            ),
            "recommendations": (
                "Practical nutrition guidance intended for the consumer."
            ),
        }

        widgets = {
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Record relevant consultation observations..."
                    ),
                }
            ),
            "recommendations": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": (
                        "Enter nutrition recommendations for the consumer..."
                    ),
                }
            ),
        }

    def clean_notes(self):
        notes = self.cleaned_data["notes"].strip()

        if not notes:
            raise forms.ValidationError(
                "Please enter the consultation notes."
            )

        return notes

    def clean_recommendations(self):
        return self.cleaned_data.get("recommendations", "").strip()
