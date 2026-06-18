import os

from drive_tools.client import get_service, PROJECT_ROOT
from drive_tools import image_review, batch_sorter, uploader, backup, manifest

DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, 'downloads')


def _menu():
    accepted = image_review.count_accepted()
    rejected = image_review.count_rejected()
    rows = manifest.read_rows()
    pending_count = sum(1 for r in rows if r['status'] == 'pending')
    downloaded_count = sum(1 for r in rows if r['status'] == 'downloaded')
    return f"""
========================================
 Google Drive Image Pipeline
========================================
1) Download Folders
   Download the next N pending folders from manifest.csv into downloads/.

2) Review Downloaded
   Review all downloaded folders from manifest.csv one by one.

3) Batch Sort
   Move everything in accepted/ into dated upload batches
   (batch_uploads/YEAR_NNNN/) of a fixed size.

4) Upload Batches
   Upload every folder in batch_uploads/ to a Google Drive folder ID,
   each as its own subfolder there.

5) Clear Rejected
   Permanently delete every file currently in rejected/.

6) Backup Accepted Images
   Zip everything in accepted/ to a timestamped archive, kept in backups/
   and copied to a destination folder path you provide.

7) Manifest Builder
   List all immediate child folders of a Drive parent folder ID into
   manifest.csv (folder, id, status=pending). Re-running is safe — existing
   folder IDs are skipped.

8) Quit
========================================
 Pending: {pending_count}  |  Downloaded: {downloaded_count}  |  Accepted: {accepted}  |  Rejected: {rejected}
"""

_service = None


def get_drive_service():
    global _service
    if _service is None:
        _service = get_service()
    return _service


def download_folders():
    if not os.path.exists(manifest.MANIFEST_PATH):
        print("No manifest.csv found. Run 'Manifest Builder' first.")
        return

    pending = [r for r in manifest.read_rows() if r['status'] == 'pending']
    if not pending:
        print("No pending folders in manifest.csv.")
        return

    n_input = input(f"How many folders to download? ({len(pending)} pending, blank = all): ").strip()
    n = int(n_input) if n_input else len(pending)
    to_download = pending[:n]

    for row in to_download:
        safe_name = image_review.sanitize_folder_name(row['folder'])
        subfolder = os.path.join(DOWNLOADS_DIR, f"{safe_name}_{row['id']}")
        print(f"\n[{row['folder']}]")
        image_review.download_images_to(get_drive_service(), row['id'], subfolder)
        manifest.update_status(row['id'], 'downloaded')

    print(f"\nDone. {len(to_download)} folder(s) downloaded and ready to review.")


def review_downloaded():
    if not os.path.exists(manifest.MANIFEST_PATH):
        print("No manifest.csv found. Run 'Manifest Builder' first.")
        return

    downloaded = [r for r in manifest.read_rows() if r['status'] == 'downloaded']
    if not downloaded:
        print("No downloaded folders to review. Run 'Download Folders' first.")
        return

    print(f"{len(downloaded)} folder(s) to review.")
    for row in downloaded:
        safe_name = image_review.sanitize_folder_name(row['folder'])
        subfolder = os.path.join(DOWNLOADS_DIR, f"{safe_name}_{row['id']}")

        if not os.path.isdir(subfolder):
            print(f"Subfolder missing for '{row['folder']}' — skipping.")
            continue

        print(f"\nReviewing: {row['folder']}")
        image_review.run_review(working_dir=subfolder)

        remaining = [f for f in os.listdir(subfolder) if os.path.isfile(os.path.join(subfolder, f))]
        if not remaining:
            os.rmdir(subfolder)
            manifest.update_status(row['id'], 'reviewed')
        # Esc mid-review: leave status as 'downloaded' so next run resumes here.


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


def run_manifest_builder():
    folder_id = input("Enter the parent Google Drive Folder ID (blank to cancel): ").strip()
    if not folder_id:
        return
    added, skipped = manifest.build_manifest(get_drive_service(), folder_id)
    print(f"Manifest updated: {added} rows added, {skipped} already present.")


def main():
    while True:
        print(_menu())
        choice = input("Choose an option: ").strip()

        if choice == '1':
            download_folders()
        elif choice == '2':
            review_downloaded()
        elif choice == '3':
            run_batch_sort()
        elif choice == '4':
            run_upload_batches()
        elif choice == '5':
            clear_rejected()
        elif choice == '6':
            run_backup_accepted()
        elif choice == '7':
            run_manifest_builder()
        elif choice == '8':
            print("Goodbye.")
            return
        else:
            print("Invalid choice, try again.")


if __name__ == '__main__':
    main()
