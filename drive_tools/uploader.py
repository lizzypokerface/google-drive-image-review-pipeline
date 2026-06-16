import os

from drive_tools.client import PROJECT_ROOT, create_drive_folder, find_drive_child, upload_file

BATCH_UPLOADS_DIR = os.path.join(PROJECT_ROOT, 'batch_uploads')


def list_batch_folders():
    if not os.path.isdir(BATCH_UPLOADS_DIR):
        return []
    return sorted(
        d for d in os.listdir(BATCH_UPLOADS_DIR)
        if os.path.isdir(os.path.join(BATCH_UPLOADS_DIR, d))
    )


def upload_all_batches(service, dest_folder_id):
    batch_names = list_batch_folders()
    if not batch_names:
        print("No batch folders found in batch_uploads/.")
        return

    print("The following folders are about to be uploaded:")
    for name in batch_names:
        print(f"  - {name}")
    print("Please check the destination Google Drive folder to make sure none of these already exist there.")

    confirm = input("Type 'yes' to proceed with the upload: ").strip().lower()
    if confirm != 'yes':
        print("Cancelled.")
        return

    for name in batch_names:
        local_path = os.path.join(BATCH_UPLOADS_DIR, name)
        files = sorted(f for f in os.listdir(local_path) if os.path.isfile(os.path.join(local_path, f)))

        print(f"\nPreparing Drive folder '{name}' ({len(files)} file(s))...")
        drive_folder_id = create_drive_folder(service, name, dest_folder_id)

        for filename in files:
            if find_drive_child(service, filename, drive_folder_id):
                print(f"    skip (already uploaded): {filename}")
                continue
            try:
                upload_file(service, os.path.join(local_path, filename), filename, drive_folder_id)
            except Exception as e:
                print(f"    ERROR uploading {filename}: {e}")

        print(f"  Done: {name}")

    print("\nAll batches uploaded.")
