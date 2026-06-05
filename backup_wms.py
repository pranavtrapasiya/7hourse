#!/usr/bin/env python
"""
Warehouse Management System (WMS)
Automated Backup and Restore Verification Script
Performs backup of SQLite database and Media files, with rotation.
"""

import os
import sys
import shutil
import datetime
import zipfile
import logging
from pathlib import Path

# Setup paths
BASE_DIR = Path(__file__).resolve().parent
BACKUP_DIR = BASE_DIR / 'backups'
DB_PATH = BASE_DIR / 'db.sqlite3'
MEDIA_DIR = BASE_DIR / 'media'
MAX_BACKUPS_TO_KEEP = 7

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(BASE_DIR / 'backup.log', encoding='utf-8')
    ]
)


def create_backup():
    """Create a zipped backup containing the db and media folder."""
    BACKUP_DIR.mkdir(exist_ok=True)
    timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_filename = f'wms_backup_{timestamp}.zip'
    backup_path = BACKUP_DIR / backup_filename

    logging.info(f"Starting database and media backup to: {backup_filename}")

    try:
        with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # 1. Backup database
            if DB_PATH.exists():
                logging.info("Backing up SQLite database...")
                zipf.write(DB_PATH, arcname='db.sqlite3')
            else:
                logging.warning("SQLite database file not found! Skipping database backup.")

            # 2. Backup media files
            if MEDIA_DIR.exists():
                logging.info("Backing up media uploads...")
                for root, _, files in os.walk(MEDIA_DIR):
                    for file in files:
                        file_path = Path(root) / file
                        relative_path = file_path.relative_to(BASE_DIR)
                        zipf.write(file_path, arcname=relative_path)
            else:
                logging.info("Media directory does not exist yet. Skipping media files backup.")

        logging.info(f"Backup created successfully: {backup_path.stat().st_size / 1024 / 1024:.2f} MB")
        rotate_backups()
        return True
    except Exception as e:
        logging.error(f"Backup failed: {e}")
        if backup_path.exists():
            backup_path.unlink()
        return False


def rotate_backups():
    """Rotate backups, keeping only the most recent N files."""
    try:
        backups = sorted(
            [f for f in BACKUP_DIR.glob('wms_backup_*.zip')],
            key=os.path.getmtime,
            reverse=True
        )
        if len(backups) > MAX_BACKUPS_TO_KEEP:
            logging.info(f"Rotating backups: Keeping newest {MAX_BACKUPS_TO_KEEP}")
            for old_backup in backups[MAX_BACKUPS_TO_KEEP:]:
                logging.info(f"Removing old backup: {old_backup.name}")
                old_backup.unlink()
    except Exception as e:
        logging.error(f"Backup rotation failed: {e}")


def verify_backup(backup_file):
    """Verify integrity of a backup file by checking its contents."""
    backup_path = Path(backup_file)
    if not backup_path.is_absolute():
        backup_path = BACKUP_DIR / backup_path

    if not backup_path.exists():
        logging.error(f"File not found for verification: {backup_path}")
        return False

    logging.info(f"Verifying backup integrity for: {backup_path.name}")
    try:
        with zipfile.ZipFile(backup_path, 'r') as zipf:
            # Check for zip corruption
            bad_file = zipf.testzip()
            if bad_file:
                logging.error(f"Backup zip is corrupted! First bad file found: {bad_file}")
                return False

            # Check for required files
            file_list = zipf.namelist()
            if 'db.sqlite3' not in file_list:
                logging.warning("Backup verification: db.sqlite3 not found inside backup file.")
            else:
                logging.info("Backup verification: db.sqlite3 found and valid.")

            logging.info(f"Backup verification successful! Total files inside: {len(file_list)}")
            return True
    except Exception as e:
        logging.error(f"Backup verification failed: {e}")
        return False


if __name__ == '__main__':
    if len(sys.argv) > 1 and sys.argv[1] == 'verify':
        if len(sys.argv) < 3:
            # Verify the latest backup
            backups = sorted(
                [f for f in BACKUP_DIR.glob('wms_backup_*.zip')],
                key=os.path.getmtime,
                reverse=True
            )
            if not backups:
                print("No backups found to verify.")
                sys.exit(1)
            latest = backups[0]
            success = verify_backup(latest)
        else:
            success = verify_backup(sys.argv[2])
        sys.exit(0 if success else 1)
    else:
        success = create_backup()
        sys.exit(0 if success else 1)
