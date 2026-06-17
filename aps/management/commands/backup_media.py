import os
import zipfile
import datetime
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Backs up the media directory to a ZIP file.'

    def handle(self, *args, **kwargs):
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'media_backup_{timestamp}.zip'
        filepath = os.path.join(backup_dir, filename)

        media_root = settings.MEDIA_ROOT
        if not os.path.exists(media_root):
            self.stdout.write(self.style.WARNING(f'Media directory {media_root} does not exist. Nothing to backup.'))
            return

        self.stdout.write(f'Backing up media directory to {filepath}...')
        
        try:
            with zipfile.ZipFile(filepath, 'w', zipfile.ZIP_DEFLATED) as zipf:
                for root, dirs, files in os.walk(media_root):
                    for file in files:
                        file_path = os.path.join(root, file)
                        # Archive path relative to MEDIA_ROOT
                        archive_path = os.path.relpath(file_path, media_root)
                        zipf.write(file_path, archive_path)
            
            self.stdout.write(self.style.SUCCESS(f'Successfully backed up media to {filepath}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error backing up media: {e}'))
