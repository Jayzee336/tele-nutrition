from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailOrUsernameBackend(ModelBackend):
    """Allow authentication with either username or email address."""

    def authenticate(self, request, username=None, password=None, **kwargs):
        if username is None:
            return None
        try:
            # Try finding by username first.
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            # Try finding by email.
            try:
                user = User.objects.get(email=username)
            except User.DoesNotExist:
                # Run default password hasher to prevent timing attacks.
                User().set_password(password)
                return None
        if user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
