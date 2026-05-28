from django.contrib.auth.backends import ModelBackend
from django.contrib.auth import get_user_model
from django.db.models import Q

class EmailOrUsernameBackend(ModelBackend):
    """
    Permite iniciar sesión con email o username.
    """
    def authenticate(self, request, username=None, password=None, **kwargs):
        UserModel = get_user_model()

        # En Django, a veces llega como username, otras como el USERNAME_FIELD
        identifier = username or kwargs.get(UserModel.USERNAME_FIELD)
        if not identifier or not password:
            return None

        users = UserModel.objects.filter(
            Q(username__iexact=identifier) | Q(email__iexact=identifier)
        )

        for user in users:
            if user.check_password(password) and self.user_can_authenticate(user):
                return user

        return None
