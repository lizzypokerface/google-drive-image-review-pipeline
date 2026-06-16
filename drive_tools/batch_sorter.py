import os
import shutil

from drive_tools.client import PROJECT_ROOT

ACCEPTED_DIR = os.path.join(PROJECT_ROOT, 'accepted')
BATCH_UPLOADS_DIR = os.path.join(PROJECT_ROOT, 'batch_uploads')


def get_files_from_source(source_dir):
    if not os.path.exists(source_dir):
        print(f"Warning: source folder not found: {source_dir}")
        return []

    files = [f for f in os.listdir(source_dir)
             if os.path.isfile(os.path.join(source_dir, f)) and not f.startswith('.')]
    files.sort()
    return [(os.path.join(source_dir, f), f) for f in files]


def create_batch_folder(dest_root, year, number):
    folder_name = f"{year}_{number:04d}"
    full_path = os.path.join(dest_root, folder_name)
    os.makedirs(full_path, exist_ok=True)
    return full_path


def get_unique_filename(filename, target_folder, tracker_dict):
    count = tracker_dict.get(filename, 0)
    if count == 0 and not os.path.exists(os.path.join(target_folder, filename)):
        tracker_dict[filename] = 0
        return filename

    name, ext = os.path.splitext(filename)
    while True:
        count += 1
        candidate = f"{name}_{count:03d}{ext}"
        if not os.path.exists(os.path.join(target_folder, candidate)):
            tracker_dict[filename] = count
            return candidate


def process_batches(file_list, dest_root, year, latest_folder_number, batch_size):
    total_files = len(file_list)
    current_batch_num = int(latest_folder_number) + 1
    filename_tracker = {}

    print(f"Found {total_files} file(s) in accepted/. Starting move process...")

    for i in range(0, total_files, batch_size):
        current_batch_files = file_list[i:i + batch_size]
        target_folder = create_batch_folder(dest_root, year, current_batch_num)
        print(f"--> Moving {len(current_batch_files)} file(s) to: {os.path.basename(target_folder)}")

        for src_full_path, original_filename in current_batch_files:
            final_filename = get_unique_filename(original_filename, target_folder, filename_tracker)
            dst_file = os.path.join(target_folder, final_filename)

            try:
                shutil.move(src_full_path, dst_file)
                if final_filename != original_filename:
                    print(f"    [Duplicate Resolved] {original_filename} -> {final_filename}")
            except Exception as e:
                print(f"    Error moving {original_filename}: {e}")

        current_batch_num += 1


def run(year, latest_folder_number, batch_size):
    all_files = get_files_from_source(ACCEPTED_DIR)

    if not all_files:
        print("No files found in accepted/. Exiting.")
        return

    os.makedirs(BATCH_UPLOADS_DIR, exist_ok=True)
    process_batches(all_files, BATCH_UPLOADS_DIR, year, latest_folder_number, batch_size)
    print("\nDone! All accepted images have been moved into batch_uploads/.")
