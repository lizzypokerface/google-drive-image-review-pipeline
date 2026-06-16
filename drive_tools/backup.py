import os
import shutil
import zipfile
from datetime import datetime

from drive_tools.client import PROJECT_ROOT
from drive_tools.image_review import ACCEPTED_DIR

BACKUPS_DIR = os.path.join(PROJECT_ROOT, 'backups')
MANIFEST_PATH = os.path.join(PROJECT_ROOT, 'manifest.csv')


def backup_accepted(dest_path):
    os.makedirs(BACKUPS_DIR, exist_ok=True)

    archive_name = f"backup_accepted_images_{datetime.now():%Y%m%d_%H%M%S}"
    local_zip_path = shutil.make_archive(
        os.path.join(BACKUPS_DIR, archive_name), 'zip', ACCEPTED_DIR
    )

    if os.path.exists(MANIFEST_PATH):
        with zipfile.ZipFile(local_zip_path, 'a') as zf:
            zf.write(MANIFEST_PATH, 'manifest.csv')

    os.makedirs(dest_path, exist_ok=True)
    zip_file_name = archive_name + '.zip'
    shutil.copy2(local_zip_path, os.path.join(dest_path, zip_file_name))

    return zip_file_name, os.path.getsize(local_zip_path)
