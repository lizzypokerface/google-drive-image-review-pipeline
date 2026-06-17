import os

from drive_tools.client import get_service
from drive_tools import image_review, batch_sorter, uploader, backup


def _menu():
    accepted = image_review.count_accepted()
    rejected = image_review.count_rejected()
    return f"""
========================================
 Google Drive Image Pipeline
========================================
1) Download & Review
   Pull images from a Google Drive folder ID or a local folder path,
   then review them one by one (Left = Accept, Right = Reject, Esc = stop reviewing).

2) Batch Sort
   Move everything in accepted/ into dated upload batches
   (batch_uploads/YEAR_NNNN/) of a fixed size.

3) Upload Batches
   Upload every folder in batch_uploads/ to a Google Drive folder ID,
   each as its own subfolder there.

4) Clear Rejected
   Permanently delete every file currently in rejected/.

5) Backup Accepted Images
   Zip everything in accepted/ to a timestamped archive, kept in backups/
   and copied to a destination folder path you provide.

6) Quit
========================================
 Accepted: {accepted}  |  Rejected: {rejected}
"""

_service = None


def get_drive_service():
    global _service
    if _service is None:
        _service = get_service()
    return _service


def download_and_review():
    while True:
        source = input("Enter a Google Drive Folder ID or a local folder path (blank to return to menu): ").strip()
        if not source:
            return

        if os.path.isdir(source):
            image_review.ingest_local_images(source)
        else:
            image_review.download_images(get_drive_service(), source)

        image_review.run_review()


def run_batch_sort():
    year = input("Year label for the batch folders (e.g. 2026): ").strip()
    if not year:
        print("Year is required.")
        return

    latest_input = input("Last batch folder number already created (blank = 0): ").strip()
    latest_folder_number = int(latest_input) if latest_input else 0

    size_input = input("Files per batch (blank = 500): ").strip()
    batch_size = int(size_input) if size_input else 500

    batch_sorter.run(year, latest_folder_number, batch_size)


def clear_rejected():
    confirm = input("This will permanently delete every file in rejected/. Type 'yes' to confirm: ").strip().lower()
    if confirm != 'yes':
        print("Cancelled.")
        return
    image_review.clear_rejected()


def run_upload_batches():
    folder_id = input("Enter the destination Google Drive Folder ID (blank to cancel): ").strip()
    if not folder_id:
        return
    uploader.upload_all_batches(get_drive_service(), folder_id)


def run_backup_accepted():
    dest_path = input("Enter a destination folder path to copy the backup zip to (blank to cancel): ").strip()
    if not dest_path:
        return
    zip_file_name, zip_size = backup.backup_accepted(dest_path)
    print(f"Backup created: {zip_file_name} ({zip_size:,} bytes)")


def main():
    while True:
        print(_menu())
        choice = input("Choose an option: ").strip()

        if choice == '1':
            download_and_review()
        elif choice == '2':
            run_batch_sort()
        elif choice == '3':
            run_upload_batches()
        elif choice == '4':
            clear_rejected()
        elif choice == '5':
            run_backup_accepted()
        elif choice == '6':
            print("Goodbye.")
            return
        else:
            print("Invalid choice, try again.")


if __name__ == '__main__':
    main()
