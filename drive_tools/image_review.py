import os
import re
import shutil
import tkinter as tk
from PIL import Image, ImageTk

from drive_tools.client import PROJECT_ROOT, list_items, download_file

DOWNLOADS_DIR = os.path.join(PROJECT_ROOT, 'downloads')
ACCEPTED_DIR = os.path.join(PROJECT_ROOT, 'accepted')
REJECTED_DIR = os.path.join(PROJECT_ROOT, 'rejected')

MAX_DISPLAY_SIZE = (1000, 800)
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.heic')


def ensure_dirs():
    for d in (DOWNLOADS_DIR, ACCEPTED_DIR, REJECTED_DIR):
        os.makedirs(d, exist_ok=True)


def clear_rejected():
    ensure_dirs()
    names = [f for f in os.listdir(REJECTED_DIR) if os.path.isfile(os.path.join(REJECTED_DIR, f))]
    for name in names:
        os.remove(os.path.join(REJECTED_DIR, name))
    print(f"Deleted {len(names)} file(s) from rejected/.")


def renumber_accepted():
    files = sorted(
        f for f in os.listdir(ACCEPTED_DIR)
        if os.path.isfile(os.path.join(ACCEPTED_DIR, f)) and not f.startswith('.')
    )
    if not files:
        print("No files in accepted/ to renumber.")
        return 0

    # Pass 1: rename to temp names to avoid collisions mid-rename.
    temp_map = []
    for i, name in enumerate(files, start=1):
        ext = os.path.splitext(name)[1].lower()
        tmp = f"_tmp_{i:06d}{ext}"
        os.rename(os.path.join(ACCEPTED_DIR, name), os.path.join(ACCEPTED_DIR, tmp))
        temp_map.append((tmp, ext, i))

    # Pass 2: rename from temp to final names.
    for tmp, ext, i in temp_map:
        final = f"{i:06d}{ext}"
        os.rename(os.path.join(ACCEPTED_DIR, tmp), os.path.join(ACCEPTED_DIR, final))

    return len(files)


def unique_destination(name):
    if (not os.path.exists(os.path.join(DOWNLOADS_DIR, name))
            and not os.path.exists(os.path.join(ACCEPTED_DIR, name))
            and not os.path.exists(os.path.join(REJECTED_DIR, name))):
        return name
    base, ext = os.path.splitext(name)
    i = 1
    while True:
        candidate = f"{base}_{i}{ext}"
        if (not os.path.exists(os.path.join(DOWNLOADS_DIR, candidate))
                and not os.path.exists(os.path.join(ACCEPTED_DIR, candidate))
                and not os.path.exists(os.path.join(REJECTED_DIR, candidate))):
            return candidate
        i += 1


def _unique_in_dest(name, dest_dir):
    """Collision-safe name for download_images_to: checks dest_dir, accepted/, and rejected/."""
    dirs = (dest_dir, ACCEPTED_DIR, REJECTED_DIR)
    if all(not os.path.exists(os.path.join(d, name)) for d in dirs):
        return name
    base, ext = os.path.splitext(name)
    i = 1
    while True:
        candidate = f"{base}_{i}{ext}"
        if all(not os.path.exists(os.path.join(d, candidate)) for d in dirs):
            return candidate
        i += 1


def sanitize_folder_name(name):
    return re.sub(r'[<>:"/\\|?*]', '', name).strip()


def download_images_to(service, folder_id, dest_dir):
    os.makedirs(dest_dir, exist_ok=True)
    ensure_dirs()
    print(f"Scanning folder {folder_id}...")
    files = list_items(service, folder_id, mime_filter='files')
    images = [f for f in files if f.get('mimeType', '').startswith('image/')]
    skipped = len(files) - len(images)

    print(f"Found {len(files)} file(s) — {len(images)} image(s), discarding {skipped} non-image file(s).")

    for file in images:
        name = _unique_in_dest(file['name'], dest_dir)
        try:
            download_file(service, file['id'], name, dest_dir, int(file.get('size', 0)))
        except Exception as e:
            print(f"    ERROR downloading {file['name']}: {e}")


def download_images(service, folder_id):
    download_images_to(service, folder_id, DOWNLOADS_DIR)


def ingest_local_images(source_dir):
    ensure_dirs()
    print(f"Scanning local folder {source_dir}...")
    entries = [f for f in os.listdir(source_dir) if os.path.isfile(os.path.join(source_dir, f))]
    images = sorted(f for f in entries if f.lower().endswith(IMAGE_EXTS))
    skipped = len(entries) - len(images)

    print(f"Found {len(entries)} file(s) — {len(images)} image(s), discarding {skipped} non-image file(s).")

    for name in images:
        dest_name = unique_destination(name)
        try:
            shutil.copy2(os.path.join(source_dir, name), os.path.join(DOWNLOADS_DIR, dest_name))
        except Exception as e:
            print(f"    ERROR copying {name}: {e}")


def _count_files(dir_path):
    if not os.path.isdir(dir_path):
        return 0
    return sum(1 for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f)))


def count_accepted():
    return _count_files(ACCEPTED_DIR)


def count_rejected():
    return _count_files(REJECTED_DIR)


def list_pending_images(working_dir=None):
    directory = working_dir if working_dir is not None else DOWNLOADS_DIR
    return sorted(
        f for f in os.listdir(directory)
        if f.lower().endswith(IMAGE_EXTS) and os.path.isfile(os.path.join(directory, f))
    )


class ReviewApp:
    def __init__(self, root, working_dir=None):
        self.root = root
        self.working_dir = working_dir if working_dir is not None else DOWNLOADS_DIR
        self.root.title("Image Review")
        self.images = list_pending_images(self.working_dir)
        self.total = len(self.images)
        self.index = 0

        self.status_label = tk.Label(root, text="", font=("Segoe UI", 11))
        self.status_label.pack(pady=(10, 5))

        self.image_label = tk.Label(root)
        self.image_label.pack(padx=10, pady=10)

        hint = tk.Label(root, text="← Accept   |   → Reject   |   Esc = Quit",
                         font=("Segoe UI", 9), fg="gray")
        hint.pack(pady=(0, 10))

        root.bind('<Left>', self.accept)
        root.bind('<Right>', self.reject)
        root.bind('<Escape>', lambda e: root.destroy())

        self.show_current()

    def show_current(self):
        if self.index >= len(self.images):
            self.root.destroy()
            return

        name = self.images[self.index]
        path = os.path.join(self.working_dir, name)
        try:
            img = Image.open(path)
            img.thumbnail(MAX_DISPLAY_SIZE)
            self.photo = ImageTk.PhotoImage(img)
            self.image_label.config(image=self.photo)
        except Exception as e:
            self.image_label.config(image='', text=f"Could not open image:\n{e}")

        self.status_label.config(text=f"{self.index + 1}/{self.total} — {name}")

    def move_current(self, dest_dir):
        name = self.images[self.index]
        src = os.path.join(self.working_dir, name)
        dst = os.path.join(dest_dir, name)
        try:
            shutil.move(src, dst)
        except Exception as e:
            print(f"    ERROR moving {name}: {e}")
        self.index += 1
        self.show_current()

    def accept(self, event=None):
        self.move_current(ACCEPTED_DIR)

    def reject(self, event=None):
        self.move_current(REJECTED_DIR)


def run_review(working_dir=None):
    ensure_dirs()
    images = list_pending_images(working_dir)
    if not images:
        print("No images to review.")
        return

    root = tk.Tk()
    ReviewApp(root, working_dir=working_dir)
    root.mainloop()
