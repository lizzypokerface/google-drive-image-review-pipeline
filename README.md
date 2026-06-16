# Google Drive Image Review Pipeline

## Problem

I store lots of photos in Google Drive (or sometimes just locally) — often
spread across many folders, with a lot of clutter mixed in. Periodically that
needs vetting: keep the good shots, discard the rest, and re-upload a clean,
space-efficient set.

This tool exists to make that recurring cycle fast:

1. Point at an image folder (Drive or local) and download its contents.
2. Review the images one by one — accept or reject.
3. Sort the accepted pile into upload-sized batches.
4. Upload those batches back to Drive.

Run end to end, this keeps only the best images over time, repeatedly, while
freeing up space from everything that didn't make the cut.

## The Full Cycle

```
   Drive folder #1  ─┐
   Drive folder #2  ─┼──►  downloads/  ──► review each image ──┬──► accepted/
   local folder #3  ─┘     (images only,        (← / →)        │
                             rest discarded)                    └──► rejected/
                                                                       │
                                                                       │ (3) Clear Rejected
                                                                       ▼
                                                                  permanently deleted

   accepted/ ──(2) Batch Sort──► batch_uploads/2026_0001/
                                  batch_uploads/2026_0002/
                                  ...

   batch_uploads/* ──(4) Upload Batches──► Drive destination folder
                                            (each batch as its own subfolder)
```

One pass through the menu, in order:

1. **Download & Review** — repeat for as many Drive folders or local folders
   as you have; every image you accept or reject during this step moves into
   `accepted/` or `rejected/` (you can review images from multiple source
   folders in the same sitting — they all land in the same two piles).
2. **Batch Sort** — once you're done reviewing, everything sitting in
   `accepted/` gets moved into fresh `batch_uploads/YEAR_NNNN/` folders.
3. **Clear Rejected** — discard everything in `rejected/` for good.
4. **Upload Batches** — push every folder in `batch_uploads/` up to a Drive
   folder ID, each batch becoming its own subfolder there.

After step 4, the cycle is complete: only the photos worth keeping survived
review, got sorted into batches, and ended up back in Drive. Run it again
next time clutter builds up.

## What It Does

A small local pipeline: pull images out of a Google Drive folder, review them
one by one (accept/reject), sort the accepted images into numbered batches,
then upload those batches back to a Google Drive folder.

## One-time Google Cloud Setup

1. Go to [console.cloud.google.com](https://console.cloud.google.com) → create a project (e.g. "DriveDownloader")
2. Search "Google Drive API" → **Enable**
3. **APIs & Services → OAuth consent screen** → External → fill in app name + your email → **Add your Gmail as a Test User**
4. **APIs & Services → Credentials** → Create Credentials → OAuth client ID → Desktop App → Download JSON → rename to `credentials.json` → place it in this folder

## Install Dependencies

```
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib tqdm Pillow
```

## Run

```
python app.py
```

On first run a browser window opens for one-time login. After that `token.json` is saved and future runs skip the browser step.

You'll see a menu with these options:

### 1) Download & Review

Enter either:
- a Google Drive folder ID (the string at the end of the Drive URL:
  `drive.google.com/drive/folders/`**`THIS_PART`**), or
- a local folder path (e.g. `C:\Users\you\Pictures\batch1`) if the photos are already on disk.

Only image files are pulled in to `downloads/` — everything else is discarded
(local files are copied, originals are left untouched). Once that finishes, a
review window opens automatically:

| Key | Action |
|-----|--------|
| ← Left Arrow | Accept current image (moves to `accepted/`) |
| → Right Arrow | Reject current image (moves to `rejected/`) |
| Esc | Stop reviewing and return to the menu |

You can keep entering folder IDs — everything accumulates into the same
`accepted/`/`rejected/` folders. Leave the folder ID blank to return to the menu.
If you quit mid-review, anything left in `downloads/` is simply picked back up
next time.

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
Duplicate filenames are automatically suffixed (e.g. `photo_001.jpg`) — this
checks both the current run and whatever's already sitting in the target
batch folder on disk, so re-running into a folder that already has files
(e.g. after an interrupted run, or accidentally reusing the same "last batch
number") renames around them instead of silently overwriting.

### 3) Clear Rejected

Permanently deletes every file in `rejected/`. Asks for a typed `yes` confirmation
first since this is destructive and not reversible.

### 4) Upload Batches

Enter a destination Google Drive folder ID. Every folder currently in
`batch_uploads/` (e.g. `2026_0001`, `2026_0002`) is uploaded there as its own
subfolder, preserving the same names and contents.

Before anything uploads, the full list of folders about to go up is printed
so you can check the destination Drive folder for duplicates first — nothing
uploads until you type `yes` to confirm.

Safe to re-run if interrupted: it reuses an existing Drive folder of the same
name instead of creating a duplicate, and skips any file that's already
present there by name.

This requires upload permission (`drive.file` scope) in addition to the
read-only scope used for downloading. If you set this project up before this
feature existed, delete `token.json` once and re-run so it can re-authorize
with the new scope.

## Filename Collisions & Safety

Two different images can legitimately share a filename (e.g. `IMG_0001.jpg`
from two different cameras/source folders). The pipeline never overwrites one
with the other:

- **Ingest (Drive download or local folder → `downloads/`)** — before a file
  is written, its name is checked against everything currently in
  `downloads/`, `accepted/`, and `rejected/`. A collision gets suffixed
  (`IMG_0001_1.jpg`, `IMG_0001_2.jpg`, ...) before it ever touches disk.
- **Review (`downloads/` → `accepted/`/`rejected/`)** — safe by construction,
  since ingest already guaranteed the name is free in both destination
  folders.
- **Batch Sort (`accepted/` → `batch_uploads/<batch>/`)** — checked against
  both the files being moved in the current run *and* whatever already
  exists in the destination batch folder on disk, so re-running Batch Sort
  into a folder that's already partially populated (interrupted run, or
  re-entering the same "last batch number" by mistake) suffixes the new
  arrival instead of clobbering the old file.
- **Upload (`batch_uploads/*` → Drive)** — a file already present by name in
  the destination Drive folder is skipped, not re-uploaded or replaced, so
  re-running an interrupted upload is safe.

The one operation that's intentionally destructive is **Clear Rejected** —
it permanently deletes everything in `rejected/`, gated behind a typed `yes`
confirmation.

## Folder Structure

```
google_drive_downloader/
  credentials.json     <- you provide this
  token.json           <- auto-generated on first run
  app.py                <- run this
  drive_tools/
    client.py            <- Drive auth + listing + download/upload helpers
    image_review.py       <- download images + accept/reject review UI
    batch_sorter.py        <- sorts accepted/ into batch_uploads/
    uploader.py             <- uploads batch_uploads/ folders to Drive
  downloads/             <- images downloaded, awaiting review
  accepted/               <- accepted images
  rejected/                <- rejected images
  batch_uploads/
    2026_0001/
    2026_0002/
```
