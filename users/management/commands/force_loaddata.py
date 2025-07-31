from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.apps import apps

class Command(BaseCommand):
    help = 'Deletes all data for specified apps and then loads a fixture.'

    def add_arguments(self, parser):
        parser.add_argument('fixture_path', type=str, help='The full path to the fixture file.')
        parser.add_argument(
            'app_labels',
            nargs='+',
            type=str,
            help='A list of app labels to clear before loading data.'
        )

    def handle(self, *args, **options):
        fixture_path = options['fixture_path']
        app_labels = options['app_labels']

        # Reverse the order to handle dependencies correctly (e.g., delete child before parent)
        models_to_clear = reversed(list(apps.get_models(include_auto_created=True)))

        self.stdout.write(self.style.WARNING('DELETING existing data...'))

        for model in models_to_clear:
            app_label = model._meta.app_label
            if app_label in app_labels:
                self.stdout.write(f'  - Clearing model: {app_label}.{model.__name__}')
                model.objects.all().delete()

        self.stdout.write(self.style.SUCCESS('Data deleted successfully.'))
        self.stdout.write(f'Loading data from {fixture_path}...')

        # Now load the new data
        call_command('loaddata', fixture_path)

        self.stdout.write(self.style.SUCCESS('Data loaded successfully! ✅'))