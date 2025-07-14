from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.models import BaseUserManager

class UserManager(BaseUserManager):
    def create_user(self, username, email, password=None, **extra_fields):
        if not username:
            raise ValueError("The Username must be set")
        if not email:
            raise ValueError("The Email must be set")

        email = self.normalize_email(email)
        user = self.model(username=username, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, email, password=None, **extra_fields):
        from users.models import Role  # ✅ import here to avoid circular import

        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        try:
            admin_role = Role.objects.get(id=Role.ADMIN)
        except ObjectDoesNotExist:
            raise ValueError("Admin role must exist before creating a superuser")

        extra_fields.setdefault('role', admin_role)
        return self.create_user(username, email, password, **extra_fields)
