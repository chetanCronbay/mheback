import json
from django.core.management.base import BaseCommand
from django.core import serializers
from django.apps import apps

class Command(BaseCommand):
    help = 'Dumps the data for a given app to a json file with guaranteed UTF-8 encoding.'

    def add_arguments(self, parser):
        parser.add_argument('app_label', type=str, help='The app label to dump.')

    def handle(self, *args, **options):
        app_label = options['app_label']
        output_file = f'{app_label}_data_utf8.json'
        
        try:
            # Get all models from the specified app
            app_models = apps.get_app_config(app_label).get_models()
            
            # Serialize the data from all models
            data = serializers.serialize('json', [obj for model in app_models for obj in model.objects.all()], indent=2)
            
            # Write to file with explicit UTF-8 encoding
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(data)
                
            self.stdout.write(self.style.SUCCESS(f'Successfully dumped {app_label} data to {output_file}'))

        except Exception as e:
            self.stderr.write(self.style.ERROR(f'An error occurred: {e}'))