import os
import datetime
from django.core.management.base import BaseCommand
from django.core.management import call_command
from django.conf import settings

class Command(BaseCommand):
    help = 'Backs up the database to a JSON file.'

    def handle(self, *args, **kwargs):
        # Create backups directory if it doesn't exist
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'db_backup_{timestamp}.json'
        filepath = os.path.join(backup_dir, filename)

        self.stdout.write(f'Backing up database to {filepath}...')
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                # Exclude content types and permissions to avoid restore conflicts
                call_command('dumpdata', exclude=['contenttypes', 'auth.permission'], format='json', indent=2, stdout=f)
            self.stdout.write(self.style.SUCCESS(f'Successfully backed up database to {filepath}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error backing up database: {e}'))
