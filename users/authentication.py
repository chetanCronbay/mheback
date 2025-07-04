from django.contrib.auth.backends import ModelBackend
from users.models import User

class EmailBackend(ModelBackend):
    def authenticate(self, request, username=None, password=None, **kwargs):
        email = kwargs.get('email', username)
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            return None

        if password is not None and user.check_password(password) and self.user_can_authenticate(user):
            return user
        return None
