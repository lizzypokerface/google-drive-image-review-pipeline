# Google Drive Image Review Pipeline

## Problem

I store lots of photos in Google Drive (or sometimes just locally) — often
spread across many folders, with a lot of clutter mixed in. Periodically that
needs vetting: keep the good shots, discard the rest, and re-upload a clean,
space-efficient set.

This tool exists to make that recurring cycle fast:

1. Point at a parent Drive folder and build a manifest of all subfolders.
2. Download and review images subfolder by subfolder (the next one pre-downloads while you review the current one).
3. Sort the accepted pile into upload-sized batches.
4. Upload those batches back to Drive.
5. Optionally back up accepted images to a local zip at any point.

Run end to end, this keeps only the best images over time, repeatedly, while
freeing up space from everything that didn't make the cut.

## The Full Cycle

```
[6] Manifest Builder
     └─ parent Drive folder ──► manifest.csv (folder, id, status=pending)

[1] Download & Review (manifest flow)
     └─ for each row in manifest.csv:
          downloads/<name>_<id>/  ──► review (← / →)  ──┬──► accepted/
          (next folder pre-downloads in background)       └──► rejected/
          row status: pending → downloaded → reviewed

[2] Batch Sort
     └─ accepted/ ──► batch_uploads/2026_0001/
                       batch_uploads/2026_0002/  ...

[4] Clear Rejected
     └─ rejected/ ──► permanently deleted

[3] Upload Batches
     └─ batch_uploads/* ──► Drive destination folder (each batch as subfolder)

[5] Backup Accepted   ← optional; run any time
     └─ accepted/ ──► backups/<timestamp>.zip + copy to your path
```

**No manifest.csv? No problem.** Option 1 falls back to the legacy flow:
prompt for a Drive folder ID or local folder path each time, downloading flat
into `downloads/`. All other steps are identical.

## One-time Google Cloud Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project (e.g. "DriveDownloader")
2. Search "Google Drive API" → **Enable**
3. **APIs & Services → OAuth consent screen** → External → fill in app name + your email → **Add your Gmail as a Test User**
4. **APIs & Services → Credentials** → Create Credentials → OAuth client ID → Desktop App → Download JSON → rename to `credentials.json` → place it in this folder

## Install Dependencies

This project uses [uv](https://docs.astral.sh/uv/) for environment management.

```
uv sync
```

This creates a `.venv` and installs all dependencies declared in `pyproject.toml`.

## Run

```
uv run python app.py
```

On first run a browser window opens for one-time login. After that `token.json`
is saved and future runs skip the browser step.

---

## Menu Options

### 1) Download & Review

**With manifest.csv present (recommended for multi-folder sessions):**

Walks the manifest automatically — no prompts needed. For each pending row:

1. Downloads images from that Drive subfolder into `downloads/<name>_<id>/`.
2. Immediately pre-downloads the next pending subfolder (so review starts with no wait from folder 2 onward).
3. Opens the review window for the current subfolder.
4. When the window closes, marks the row `reviewed` (and deletes the empty subfolder). If you hit Esc early, the row stays `downloaded` and resumes next run.

**Without manifest.csv (legacy flow):**

Enter either:
- a Google Drive folder ID (the string at the end of the Drive URL:
  `drive.google.com/drive/folders/`**`THIS_PART`**), or
- a local folder path (e.g. `C:\Users\you\Pictures\batch1`)

Only image files are pulled in to `downloads/` — everything else is discarded
(local files are copied, originals are left untouched). Once that finishes, a
review window opens automatically. Leave the source blank to return to the menu.

**Review keys (both flows):**

| Key | Action |
|-----|--------|
| ← Left Arrow | Accept current image → `accepted/` |
| → Right Arrow | Reject current image → `rejected/` |
| Esc | Stop reviewing and return to the menu |

### 2) Batch Sort

Moves everything currently in `accepted/` into dated batch folders under
`batch_uploads/`, named `YEAR_NNNN` (e.g. `2026_0001`, `2026_0002`, ...).
You'll be prompted for:

- **Year label** — used as the folder name prefix.
- **Last batch folder number already created** — the script starts numbering at this + 1 (use 0 if starting fresh).
- **Files per batch** — defaults to 500 if left blank.

Files are *moved* (not copied) out of `accepted/` and into the batch folder.
This matters for the recurring-cycle workflow: if accepted images stuck
around in `accepted/`, the next Batch Sort run would re-batch (and later
re-upload) photos already handled in an earlier cycle. Moving them keeps
`accepted/` representing only "not yet batched" images.

Duplicate filenames are automatically suffixed (e.g. `photo_001.jpg`) — checked
against both the current run and whatever's already sitting in the target batch
folder on disk.

### 3) Upload Batches

Enter a destination Google Drive folder ID. Every folder currently in
`batch_uploads/` (e.g. `2026_0001`, `2026_0002`) is uploaded there as its own
subfolder, preserving the same names and contents.

Before anything uploads, the full list of folders about to go up is printed
so you can check the destination Drive folder for duplicates first — nothing
uploads until you type `yes` to confirm.

Safe to re-run if interrupted: it reuses an existing Drive folder of the same
name instead of creating a duplicate, and skips any file that's already
present there by name.

### 4) Clear Rejected

Permanently deletes every file in `rejected/`. Asks for a typed `yes`
confirmation first since this is destructive and not reversible.

### 5) Backup Accepted Images

Enter a destination folder path (local filesystem). The tool:

1. Zips everything in `accepted/` to a timestamped archive (e.g. `accepted_backup_20260619_143022.zip`).
2. Saves a copy to `backups/` locally.
3. Copies the same zip to your destination path.

`accepted/` is left untouched — this is a backup, not a move. Safe to run
multiple times; each run produces a new timestamped zip.

### 6) Manifest Builder

Enter a Google Drive parent folder ID. The tool lists all immediate child
folders and appends them to `manifest.csv` with status `pending`. Already-present
folder IDs are skipped, so re-running against the same parent is safe.

**Run this first** at the start of a multi-folder session, then use option 1
to walk through all the subfolders automatically.

---

## Filename Collisions & Safety

Two different images can legitimately share a filename (e.g. `IMG_0001.jpg`
from two different cameras/source folders). The pipeline never overwrites one
with the other:

- **Ingest (Drive download → `downloads/<name>_<id>/` or flat `downloads/`)** — before a file
  is written, its name is checked for collisions. A collision gets suffixed
  (`IMG_0001_1.jpg`, `IMG_0001_2.jpg`, ...) before it ever touches disk.
- **Review (`downloads/…` → `accepted/`/`rejected/`)** — safe by construction,
  since ingest already guaranteed the name is free in both destination folders.
- **Batch Sort (`accepted/` → `batch_uploads/<batch>/`)** — checked against
  both the files being moved in the current run *and* whatever already exists
  in the destination batch folder on disk.
- **Upload (`batch_uploads/*` → Drive)** — a file already present by name in
  the destination Drive folder is skipped, not re-uploaded or replaced.

The one operation that's intentionally destructive is **Clear Rejected** —
it permanently deletes everything in `rejected/`, gated behind a typed `yes`
confirmation.

## Folder Structure

```
google-drive-image-review-pipeline/
  credentials.json       <- you provide this (not checked in)
  token.json             <- auto-generated on first run (not checked in)
  pyproject.toml         <- dependencies (uv)
  uv.lock                <- locked dependency versions
  app.py                 <- entry point; run this
  drive_tools/
    client.py            <- Drive auth + listing + download/upload helpers
    image_review.py      <- download images + accept/reject review UI
    batch_sorter.py      <- sorts accepted/ into batch_uploads/
    uploader.py          <- uploads batch_uploads/ folders to Drive
    manifest.py          <- manifest.csv builder + CRUD helpers
    backup.py            <- zip accepted/ to a timestamped archive
  docs/
    workflow.md          <- full end-to-end workflow walkthrough
  manifest.csv           <- runtime; not checked in
  downloads/             <- images downloaded, awaiting review (not checked in)
    <name>_<id>/         <- per-subfolder directories (manifest flow)
  accepted/              <- accepted images (not checked in)
  rejected/              <- rejected images (not checked in)
  batch_uploads/         <- sorted batches ready to upload (not checked in)
    2026_0001/
    2026_0002/
  backups/               <- local zip archives of accepted/ (not checked in)
```
