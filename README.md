# Google Drive Image Review Pipeline

## Problem

I store lots of photos in Google Drive — often spread across many folders,
with a lot of clutter mixed in. Periodically that needs vetting: keep the
good shots, discard the rest, and re-upload a clean, space-efficient set.

This tool makes that recurring cycle fast:

1. Point at a parent Drive folder and build a manifest of all subfolders.
2. Download folders in whatever batch size you want.
3. Review images one by one — accept or reject.
4. Optionally renumber accepted images sequentially before sorting.
5. Sort accepted images into upload-sized batches and push them back to Drive.

## The Full Cycle

```
[8] Manifest Builder
     └─ parent Drive folder ──► manifest.csv (folder, id, status=pending)

[1] Download Folders
     └─ next N pending rows ──► downloads/<name>_<id>/  (status → downloaded)

[2] Review Downloaded
     └─ each downloaded subfolder ──► review (← / →) ──┬──► accepted/
                                                         └──► rejected/
                                      (status → reviewed, subfolder deleted)

[3] Renumber Accepted          ← optional
     └─ accepted/ ──► 000001.ext, 000002.ext, ...

[4] Batch Sort
     └─ accepted/ ──► batch_uploads/2026_0001/
                       batch_uploads/2026_0002/  ...

[6] Clear Rejected
     └─ rejected/ ──► permanently deleted

[5] Upload Batches
     └─ batch_uploads/* ──► Drive destination folder (each batch as subfolder)

[7] Backup Accepted            ← optional, run any time
     └─ accepted/ ──► backups/<timestamp>.zip + copy to your path
```

The menu header always shows current counts:
`Pending | Downloaded | Accepted | Rejected`

---

## One-time Google Cloud Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project (e.g. "DriveDownloader")
2. Search "Google Drive API" → **Enable**
3. **APIs & Services → OAuth consent screen** → External → fill in app name + your email → **Add your Gmail as a Test User**
4. **APIs & Services → Credentials** → Create Credentials → OAuth client ID → Desktop App → Download JSON → rename to `credentials.json` → place it in this folder

## Install

This project uses [uv](https://docs.astral.sh/uv/) for environment management.

```
uv sync
```

## Run

```
uv run python app.py
```

On first run a browser window opens for one-time login. After that `token.json`
is saved and future runs skip the browser step.

---

## Menu Options

### 8) Manifest Builder

Enter a Google Drive parent folder ID. The tool lists all immediate child
folders and appends them to `manifest.csv` with `status=pending`. Already-present
folder IDs are skipped, so re-running against the same parent is safe.

**Run this first** to start a session.

---

### 1) Download Folders

Enter how many pending folders to download (blank = all). Each folder's images
are fetched into `downloads/<name>_<id>/` and its manifest row is marked `downloaded`.

Download in batches — fetch a handful now, review them, then download more.

---

### 2) Review Downloaded

No prompt — walks all `downloaded` manifest rows automatically. For each folder,
opens the review window:

| Key | Action |
|-----|--------|
| ← Left Arrow | Accept → `accepted/` |
| → Right Arrow | Reject → `rejected/` |
| Esc | Stop; resume from here next run |

When a folder's review window closes with all images moved, the empty subfolder
is deleted and the row is marked `reviewed`. Hitting Esc leaves the row as
`downloaded` so the next run picks up where you left off.

---

### 3) Renumber Accepted

Renames every file in `accepted/` to a 6-digit zero-padded sequence —
`000001.ext`, `000002.ext`, ... — sorted alphabetically by current filename.
Original file extensions are preserved. Asks for `yes` confirmation first.

Run this before Batch Sort if you want clean sequential numbering in your
uploaded batches.

---

### 4) Batch Sort

Moves everything in `accepted/` into dated batch folders under `batch_uploads/`,
named `YEAR_NNNN`. You'll be prompted for:

- **Year label** — used as the folder name prefix.
- **Last batch folder number already created** — starts numbering at this + 1 (use 0 if starting fresh).
- **Files per batch** — defaults to 500 if left blank.

Files are *moved* (not copied) out of `accepted/`. This keeps `accepted/`
representing only "not yet batched" images across repeated cycles.

---

### 5) Upload Batches

Enter a destination Google Drive folder ID. Every folder in `batch_uploads/`
is uploaded there as its own subfolder. Prints the list and asks for `yes`
before anything uploads. Safe to re-run after interruption — existing Drive
folders and files are reused/skipped.

---

### 6) Clear Rejected

Permanently deletes every file in `rejected/`. Requires typed `yes` confirmation.

---

### 7) Backup Accepted Images

Enter a destination folder path. Creates a timestamped zip of everything in
`accepted/` (e.g. `accepted_backup_20260619_143022.zip`), saves it to `backups/`
locally, and copies it to your destination. `accepted/` is left untouched.

---

## Filename Collisions & Safety

- **Download** — collision-checked against `accepted/` and `rejected/` before writing; suffixed if needed (`IMG_0001_1.jpg`).
- **Review** — safe by construction; ingest already guaranteed uniqueness.
- **Batch Sort** — checked against both the current run and existing files on disk in the target batch folder.
- **Upload** — files already present in the destination Drive folder are skipped.
- **Clear Rejected** — the one intentionally destructive operation; gated behind typed `yes`.

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
    image_review.py      <- download, review UI, renumber
    batch_sorter.py      <- sorts accepted/ into batch_uploads/
    uploader.py          <- uploads batch_uploads/ folders to Drive
    manifest.py          <- manifest.csv builder + CRUD helpers
    backup.py            <- zip accepted/ to a timestamped archive
  docs/
    workflow.md          <- full end-to-end workflow walkthrough
  manifest.csv           <- runtime; not checked in
  downloads/             <- not checked in
    <name>_<id>/         <- per-subfolder directories (one per manifest row)
  accepted/              <- accepted images (not checked in)
  rejected/              <- rejected images (not checked in)
  batch_uploads/         <- sorted batches ready to upload (not checked in)
    2026_0001/
    2026_0002/
  backups/               <- local zip archives of accepted/ (not checked in)
```
