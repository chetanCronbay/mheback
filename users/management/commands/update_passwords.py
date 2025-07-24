from django.core.management.base import BaseCommand
from django.contrib.auth.hashers import make_password
from users.models import User  # Update to your app name if needed

class Command(BaseCommand):
    help = 'Update all user passwords to be their email address (hashed)'

    def handle(self, *args, **options):
        users = User.objects.all()
        for user in users:
            email = user.email.strip().lower()
            user.password = make_password(email)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Updated password for {user.email}'))
        
        self.stdout.write(self.style.SUCCESS('✅ All passwords updated successfully.'))
