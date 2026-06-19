# Workflow Guide

This document describes the full recurring photo-vetting cycle from end to end.
For developer/architecture notes, see [CLAUDE.md](../CLAUDE.md).

## Full Cycle Overview

```
[8] Manifest Builder
        |
        v  (manifest.csv created/updated)
[1] Download Folders
        |  (downloads/<name>_<id>/ subfolders created, status → downloaded)
        v
[2] Review Downloaded
        |  (accepted/ and rejected/ populated, status → reviewed)
        v
[3] Renumber Accepted      ← optional, run before Batch Sort
        |  (000001.ext, 000002.ext, ...)
        v
[4] Batch Sort
        |  (accepted/ → batch_uploads/YEAR_NNNN/)
        v
[6] Clear Rejected
        |  (rejected/ emptied)
        v
[5] Upload Batches
        |  (batch_uploads/* → Drive destination folder)
        v
[7] Backup Accepted        ← optional, run any time
```

**Key state locations:**

| Path | What lives here |
|------|-----------------|
| `manifest.csv` | folder name, Drive ID, status (pending / downloaded / reviewed) |
| `downloads/<name>_<id>/` | images downloaded and awaiting review |
| `accepted/` | images accepted during review, awaiting batch sort |
| `rejected/` | images rejected during review, awaiting deletion |
| `batch_uploads/YEAR_NNNN/` | sorted batches ready to upload to Drive |
| `backups/` | timestamped zip archives of accepted/ |

The menu header always shows current counts:
`Pending | Downloaded | Accepted | Rejected`

---

## Menu Options

### 8) Manifest Builder

**Run this first** at the start of a new session.

**Prerequisite:** none — creates `manifest.csv` if it doesn't exist.

**What it asks for:**
- A Google Drive parent folder ID whose immediate child folders you want to review.

**What it does:**
1. Lists all immediate child folders of the given Drive folder.
2. Appends any folder not already in `manifest.csv` as a new row with `status=pending`.
3. Skips folders whose Drive ID is already present (idempotent — safe to re-run against the same parent).
4. Prints how many rows were added vs. already present.

**Filesystem state after:** `manifest.csv` created/updated.

---

### 1) Download Folders

**Prerequisite:** `manifest.csv` must exist (run Manifest Builder first).

**What it asks for:**
- How many pending folders to download (blank = all pending).

**What it does:**
1. Reads all `pending` rows from `manifest.csv`.
2. For each selected row: downloads images into `downloads/<sanitized_name>_<folder_id>/`, then marks the row `downloaded`.
3. Prints a summary when done.

**Filesystem state after:** `downloads/<name>_<id>/` subfolders created; manifest rows updated to `downloaded`.

> Run this in batches — download a handful overnight, review in the morning, then download more.

---

### 2) Review Downloaded

**Prerequisite:** at least one folder with status `downloaded` in `manifest.csv`.

**What it asks for:** nothing — walks all `downloaded` rows automatically.

**What it does:**
1. For each `downloaded` row in order:
   - Opens the review window for its subfolder in `downloads/`.
   - When the window closes, if the subfolder is empty (all images moved): deletes it and marks the row `reviewed`.
   - If not empty (Esc pressed early): leaves status as `downloaded` — next run resumes from here.

**Review keys:**

| Key | Action |
|-----|--------|
| ← Left Arrow | Accept → `accepted/` |
| → Right Arrow | Reject → `rejected/` |
| Esc | Stop reviewing; resume next run |

**Filesystem state after:** images distributed across `accepted/` and `rejected/`; reviewed subfolders deleted; manifest rows updated to `reviewed`.

---

### 3) Renumber Accepted

**Prerequisite:** `accepted/` should be populated.

**What it asks for:**
- Typed confirmation `yes`.

**What it does:**
Renames every file in `accepted/` to a 6-digit zero-padded sequence — `000001.ext`, `000002.ext`, ... — sorted alphabetically by the current filename. Original file extensions are preserved.

Uses a two-pass rename (via temp names) so there are no collisions if existing filenames overlap with target names.

**Filesystem state after:** all files in `accepted/` renamed sequentially; no files added or removed.

> Run this before Batch Sort if you want a clean sequential numbering scheme in your uploaded batches.

---

### 4) Batch Sort

**Prerequisite:** `accepted/` should be populated.

**What it asks for:**
- Year label (e.g. `2026`)
- Last batch folder number already created (blank = 0, i.e. start from `0001`)
- Files per batch (blank = 500)

**What it does:**
1. Reads all files from `accepted/`.
2. Creates `batch_uploads/YEAR_NNNN/` folders and **moves** (not copies) files into them in chunks of the given size.
3. Collision-safe: suffixes duplicates rather than overwriting.

**Filesystem state after:** `accepted/` is empty; `batch_uploads/YEAR_NNNN/` folders populated.

> Moving rather than copying is intentional — it keeps `accepted/` representing only images not yet batched. Re-running after an interruption is safe.

---

### 5) Upload Batches

**Prerequisite:** `batch_uploads/` should contain at least one batch folder.

**What it asks for:**
- Destination Google Drive folder ID.
- Typed confirmation `yes`.

**What it does:**
1. Lists all folders under `batch_uploads/`.
2. For each batch: creates or reuses a same-named subfolder in the destination Drive folder, then uploads each file (skipping files already present by name).

**Filesystem state after:** `batch_uploads/` unchanged locally; files mirrored to Drive.

> Safe to re-run after an interruption: existing Drive folders and files are reused/skipped.

---

### 6) Clear Rejected

**Prerequisite:** none.

**What it asks for:**
- Typed confirmation `yes`.

**What it does:**
Permanently deletes every file in `rejected/`.

**Filesystem state after:** `rejected/` is empty.

---

### 7) Backup Accepted Images

**Prerequisite:** none (zip will be empty if `accepted/` is empty).

**What it asks for:**
- Destination folder path to copy the backup zip to (local filesystem).

**What it does:**
1. Creates a timestamped zip of everything in `accepted/` (e.g. `accepted_backup_20260619_143022.zip`).
2. Saves the zip to `backups/` locally.
3. Copies the same zip to the destination path you provided.
4. Leaves `accepted/` untouched — this is a backup, not a move.

**Filesystem state after:** zip present in both `backups/` and the destination path; `accepted/` unchanged.
