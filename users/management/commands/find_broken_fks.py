from django.core.management.base import BaseCommand
from django.apps import apps
from django.contrib.auth import get_user_model
from django.db.models import ForeignKey, OneToOneField

User = get_user_model()

class Command(BaseCommand):
    help = 'Finds broken foreign key relationships to the User model'

    def handle(self, *args, **options):
        self.stdout.write("🔍 Searching for broken User foreign keys...")

        found_broken = False
        # Get all models in your project
        all_models = apps.get_models()

        for model in all_models:
            # Find fields that are ForeignKeys or OneToOneFields to the User model
            user_fields = [
                f for f in model._meta.get_fields()
                if (isinstance(f, (ForeignKey, OneToOneField))) and f.related_model == User
            ]

            if not user_fields:
                continue

            self.stdout.write(f"--- Checking model: {model.__name__} ---")

            # Get the names of the user fields
            user_field_names = [f.name for f in user_fields]

            # Check every object in the model
            for obj in model.objects.all().iterator():
                for field_name in user_field_names:
                    try:
                        # This will raise User.DoesNotExist if the linked user is missing
                        getattr(obj, field_name)
                    except User.DoesNotExist:
                        found_broken = True
                        user_id_val = getattr(obj, f"{field_name}_id")
                        self.stdout.write(
                            self.style.ERROR(
                                f"💔 BROKEN RELATION: Model `{model.__name__}` (PK: {obj.pk}) "
                                f"points to non-existent User ID `{user_id_val}` "
                                f"via field `{field_name}`."
                            )
                        )

        if not found_broken:
            self.stdout.write(self.style.SUCCESS("✅ No broken User relationships found."))