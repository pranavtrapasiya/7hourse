import os
from django.core.management.base import BaseCommand
from django.core.management import call_command

class Command(BaseCommand):
    help = 'Restores the database from a JSON backup file.'

    def add_arguments(self, parser):
        parser.add_argument('filepath', type=str, help='Path to the backup JSON file')

    def handle(self, *args, **kwargs):
        filepath = kwargs['filepath']

        if not os.path.exists(filepath):
            self.stdout.write(self.style.ERROR(f'Backup file not found: {filepath}'))
            return

        self.stdout.write(f'Restoring database from {filepath}...')
        
        try:
            call_command('loaddata', filepath)
            self.stdout.write(self.style.SUCCESS(f'Successfully restored database from {filepath}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error restoring database: {e}'))
