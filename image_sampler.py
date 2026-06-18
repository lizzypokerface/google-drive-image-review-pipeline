import atexit
import os
import random
import shutil
from urllib.parse import quote

import gradio as gr

from drive_tools.client import PROJECT_ROOT, get_service, list_items, download_file

SAMPLE_TEMP = os.path.join(PROJECT_ROOT, "sample_temp")
PARENT_FOLDER_ID = ""  # hardcode a Drive folder ID here to pre-fill the UI
NUM_FOLDERS = 3
SAMPLE_SIZE = 30
IMAGE_MIMETYPES = {
    "image/jpeg", "image/png", "image/gif",
    "image/webp", "image/tiff", "image/bmp", "image/heic",
}
IMAGE_EXTS = ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff', '.heic')


def clear_temp():
    if os.path.exists(SAMPLE_TEMP):
        shutil.rmtree(SAMPLE_TEMP)
    os.makedirs(SAMPLE_TEMP, exist_ok=True)



def list_subfolders(service, parent_id):
    return list_items(service, parent_id, mime_filter='folders')


def list_images_in_folder(service, folder_id):
    files = list_items(service, folder_id, mime_filter='files')
    return [
        f for f in files
        if f.get('mimeType', '') in IMAGE_MIMETYPES
        or f['name'].lower().endswith(IMAGE_EXTS)
    ]


def build_ui():
    service = get_service()

    with gr.Blocks(title="Drive Image Sampler") as demo:
        gr.Markdown("## Drive Image Sampler")

        with gr.Row():
            folder_input = gr.Textbox(
                label="Parent Folder ID",
                placeholder="Paste Google Drive folder ID here",
                value=PARENT_FOLDER_ID or "",
                scale=5,
            )
            num_folders_input = gr.Number(
                label="Folders to sample",
                value=NUM_FOLDERS,
                minimum=1,
                precision=0,
                scale=1,
            )
            sample_size_input = gr.Number(
                label="Images to fetch",
                value=SAMPLE_SIZE,
                minimum=1,
                precision=0,
                scale=1,
            )
            load_btn = gr.Button("Load", variant="primary", scale=1)

        status_label = gr.Markdown("Enter a folder ID and click Load.")

        image_display = gr.Image(type="filepath", label="", height=600)

        with gr.Row():
            prev_btn = gr.Button("← Prev", scale=1)
            counter_label = gr.Markdown("—", elem_id="counter")
            next_btn = gr.Button("Next →", scale=1)

        size_label = gr.Markdown("", elem_id="size")

        refresh_btn = gr.Button("Refresh (new random sample)")

        paths_state = gr.State([])
        idx_state = gr.State(0)
        seen_ids_state = gr.State(set())

        def fmt_size(path):
            try:
                b = os.path.getsize(path)
                if b >= 1024 ** 2:
                    return f"{b / 1024 ** 2:.1f} MB"
                return f"{b / 1024:.1f} KB"
            except OSError:
                return ""

        def do_load(folder_id, num_folders, sample_size, seen_ids):
            if not folder_id.strip():
                yield [], 0, None, "Please enter a folder ID.", "—", "", gr.update()
                return

            yield [], 0, None, "Scanning folders...", "—", "", gr.update()

            subfolders = list_subfolders(service, folder_id.strip())
            if not subfolders:
                yield [], 0, None, "No subfolders found in the given folder ID.", "—", "", gr.update()
                return

            chosen = random.sample(subfolders, min(int(num_folders), len(subfolders)))
            folder_names = [f['name'] for f in chosen]
            yield [], 0, None, f"Listing images in: {', '.join(folder_names)}...", "—", "", gr.update()

            pool = []
            for folder in chosen:
                images = list_images_in_folder(service, folder['id'])
                print(f"  {folder['name']}: {len(images)} image(s)")
                pool.extend(images)

            if not pool:
                yield [], 0, None, "No images found in the selected folders.", "—", "", gr.update()
                return

            unseen = [f for f in pool if f['id'] not in seen_ids]
            if len(unseen) < int(sample_size):
                print(f"  Seen pool exhausted ({len(seen_ids)} seen) — resetting.")
                seen_ids = set()
                unseen = pool

            sample = random.sample(unseen, min(int(sample_size), len(unseen)))
            new_seen = seen_ids | {f['id'] for f in sample}
            total = len(sample)
            clear_temp()
            yield [], 0, None, f"Downloading 0 of {total}...", "—", "", gr.update()

            paths = []
            first_shown = False
            for file in sample:
                name = file['name']
                dest = os.path.join(SAMPLE_TEMP, name)
                if os.path.exists(dest):
                    base, ext = os.path.splitext(name)
                    i = 1
                    while os.path.exists(os.path.join(SAMPLE_TEMP, f"{base}_{i}{ext}")):
                        i += 1
                    name = f"{base}_{i}{ext}"
                    dest = os.path.join(SAMPLE_TEMP, name)
                try:
                    download_file(service, file['id'], name, SAMPLE_TEMP, int(file.get('size', 0)))
                    paths.append(dest)
                except Exception as e:
                    print(f"  ERROR downloading {file['name']}: {e}")

                status = f"Downloading... {len(paths)} of {total}"
                if not first_shown and paths:
                    yield paths.copy(), 0, paths[0], status, f"Image 1 of {len(paths)}", fmt_size(paths[0]), gr.update()
                    first_shown = True
                else:
                    yield paths.copy(), gr.update(), gr.update(), status, gr.update(), gr.update(), gr.update()

            final_msg = f"Loaded {len(paths)} of {total} images from {len(chosen)} folder(s). ({len(new_seen)} seen total)"
            yield paths.copy(), gr.update(), gr.update(), final_msg, gr.update(), gr.update(), new_seen

        def do_refresh(folder_id, num_folders, sample_size, paths, seen_ids):
            yield from do_load(folder_id, num_folders, sample_size, seen_ids)

        def go_prev(paths, idx):
            if not paths:
                return idx, None, "—", ""
            new_idx = (idx - 1) % len(paths)
            return new_idx, paths[new_idx], f"Image {new_idx + 1} of {len(paths)}", fmt_size(paths[new_idx])

        def go_next(paths, idx):
            if not paths:
                return idx, None, "—", ""
            new_idx = (idx + 1) % len(paths)
            return new_idx, paths[new_idx], f"Image {new_idx + 1} of {len(paths)}", fmt_size(paths[new_idx])

        load_btn.click(
            do_load,
            inputs=[folder_input, num_folders_input, sample_size_input, seen_ids_state],
            outputs=[paths_state, idx_state, image_display, status_label, counter_label, size_label, seen_ids_state],
        )

        refresh_btn.click(
            do_refresh,
            inputs=[folder_input, num_folders_input, sample_size_input, paths_state, seen_ids_state],
            outputs=[paths_state, idx_state, image_display, status_label, counter_label, size_label, seen_ids_state],
        )

        prev_btn.click(
            go_prev,
            inputs=[paths_state, idx_state],
            outputs=[idx_state, image_display, counter_label, size_label],
        )

        next_btn.click(
            go_next,
            inputs=[paths_state, idx_state],
            outputs=[idx_state, image_display, counter_label, size_label],
        )

        with gr.Accordion("SoundCloud Player", open=False):
            gr.Markdown(
                "Use a SoundCloud **set** URL, e.g. `https://soundcloud.com/chillhopdotcom/sets/the-best-of-essentials-summer`"
            )
            with gr.Row():
                sc_input = gr.Textbox(
                    label="SoundCloud Set URL",
                    placeholder="https://soundcloud.com/artist/sets/set-name",
                    scale=5,
                )
                sc_btn = gr.Button("Play", scale=1)
            sc_player = gr.HTML("<p style='color:gray;font-size:0.9em'>Enter a SoundCloud set URL above and click Play.</p>")

        def load_soundcloud(url):
            if not url.strip():
                return "<p style='color:gray;font-size:0.9em'>Enter a SoundCloud URL above and click Play.</p>"
            src = (
                "https://w.soundcloud.com/player/?"
                f"url={quote(url.strip(), safe='')}"
                "&auto_play=true&color=%23ff5500&hide_related=true"
                "&show_comments=false&show_reposts=false"
            )
            return (
                f'<iframe width="100%" height="166" scrolling="no" frameborder="no" '
                f'allow="autoplay" src="{src}"></iframe>'
            )

        sc_btn.click(load_soundcloud, inputs=[sc_input], outputs=[sc_player])

    return demo


def _cleanup():
    if os.path.exists(SAMPLE_TEMP):
        shutil.rmtree(SAMPLE_TEMP, ignore_errors=True)
        print("sample_temp cleared.")

atexit.register(_cleanup)

if __name__ == "__main__":
    demo = build_ui()
    demo.queue().launch()
