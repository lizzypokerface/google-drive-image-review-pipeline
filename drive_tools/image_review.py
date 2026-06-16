import os
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


def download_images(service, folder_id):
    ensure_dirs()
    print(f"Scanning folder {folder_id}...")
    files = list_items(service, folder_id, mime_filter='files')
    images = [f for f in files if f.get('mimeType', '').startswith('image/')]
    skipped = len(files) - len(images)

    print(f"Found {len(files)} file(s) — {len(images)} image(s), discarding {skipped} non-image file(s).")

    for file in images:
        name = unique_destination(file['name'])
        try:
            download_file(service, file['id'], name, DOWNLOADS_DIR, int(file.get('size', 0)))
        except Exception as e:
            print(f"    ERROR downloading {file['name']}: {e}")


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


def list_pending_images():
    return sorted(
        f for f in os.listdir(DOWNLOADS_DIR)
        if f.lower().endswith(IMAGE_EXTS) and os.path.isfile(os.path.join(DOWNLOADS_DIR, f))
    )


class ReviewApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Image Review")
        self.images = list_pending_images()
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
        path = os.path.join(DOWNLOADS_DIR, name)
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
        src = os.path.join(DOWNLOADS_DIR, name)
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


def run_review():
    ensure_dirs()
    images = list_pending_images()
    if not images:
        print("No images to review.")
        return

    root = tk.Tk()
    ReviewApp(root)
    root.mainloop()
