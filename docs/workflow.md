# Workflow Guide

This document describes the full recurring photo-vetting cycle from end to end.
For developer/architecture notes, see [CLAUDE.md](../CLAUDE.md).

## Full Cycle Overview

```
[6] Manifest Builder
        |
        v  (manifest.csv created/updated)
[1] Download & Review
        |  (downloads/<name>_<id>/ subfolders, reviewed → accepted/ or rejected/)
        v
[2] Batch Sort
        |  (accepted/ → batch_uploads/YEAR_NNNN/)
        v
[4] Clear Rejected
        |  (rejected/ emptied)
        v
[3] Upload Batches
        |  (batch_uploads/* → Drive destination folder)
        v
[5] Backup Accepted   ← optional, run any time accepted/ has files worth keeping
```

**Key state locations:**

| Path | What lives here |
|------|-----------------|
| `manifest.csv` | folder name, Drive ID, status (pending/downloaded/reviewed) |
| `downloads/<name>_<id>/` | images currently being reviewed (manifest flow) |
| `downloads/` | images currently being reviewed (legacy flow) |
| `accepted/` | images accepted during review, awaiting batch sort |
| `rejected/` | images rejected during review, awaiting deletion |
| `batch_uploads/YEAR_NNNN/` | batches ready to upload to Drive |
| `backups/` | timestamped zip archives of accepted/ |

---

## Menu Options

### 1) Download & Review

**Prerequisite:** none (manifest.csv optional)

**What it asks for:**
- If `manifest.csv` does not exist: prompts for a Google Drive folder ID or a local folder path each iteration. Blank input returns to the menu.
- If `manifest.csv` exists: no prompt — it walks the manifest automatically.

**What it does (legacy flow — no manifest.csv):**
1. If you entered a Drive folder ID: downloads all images from that folder into `downloads/`, skipping files already present.
2. If you entered a local folder path: copies all images from that folder into `downloads/`.
3. Opens the review window (Left = Accept → `accepted/`, Right = Reject → `rejected/`, Esc = stop).
4. Returns to the source-prompt loop when the window closes.

**What it does (manifest flow — manifest.csv present):**
1. Finds the first row with status `downloaded` (already fetched), or `pending` if none.
2. If the row is `pending`, downloads its images into `downloads/<sanitized_name>_<folder_id>/` and sets its status to `downloaded`.
3. Immediately preloads the next `pending` row (if any) into its own subfolder — synchronously, before the review window opens.
4. Opens the review window for the current subfolder.
5. When the window closes:
   - If the subfolder is empty (all images reviewed): deletes it and marks the row `reviewed`.
   - If not empty (Esc pressed early): leaves status as `downloaded` so the next run resumes where you left off.
6. Repeats until all rows are `reviewed`.

**Filesystem state after:** images distributed across `accepted/` and `rejected/`; manifest rows updated.

---

### 2) Batch Sort

**Prerequisite:** `accepted/` should be populated.

**What it asks for:**
- Year label (e.g. `2026`)
- Last batch folder number already created (blank = 0, i.e. start from `0001`)
- Files per batch (blank = 500)

**What it does:**
1. Reads all files from `accepted/`.
2. Creates `batch_uploads/YEAR_NNNN/` folders and **moves** (not copies) files into them in batches of the given size.
3. Collision-safe: suffixes duplicates rather than overwriting.

**Filesystem state after:** `accepted/` is empty; `batch_uploads/YEAR_NNNN/` folders populated.

> Moving rather than copying is intentional — it keeps `accepted/` representing only images not yet batched. Re-running after an interruption is safe; existing filenames are suffixed rather than overwritten.

---

### 3) Upload Batches

**Prerequisite:** `batch_uploads/` should contain at least one batch folder.

**What it asks for:**
- Destination Google Drive folder ID

**What it does:**
1. Lists all folders under `batch_uploads/`.
2. Prompts for confirmation (`yes` required).
3. For each batch folder: creates or reuses a same-named subfolder in the destination Drive folder, then uploads each file (skipping files already present by name).

**Filesystem state after:** `batch_uploads/` unchanged locally; files mirrored to Drive.

> Safe to re-run after an interruption: existing Drive folders and files are reused/skipped.

---

### 4) Clear Rejected

**Prerequisite:** none

**What it asks for:**
- Typed confirmation `yes`

**What it does:**
Permanently deletes every file in `rejected/`.

**Filesystem state after:** `rejected/` is empty.

---

### 5) Backup Accepted Images

**Prerequisite:** none (works even if `accepted/` is empty, though the zip will be empty too)

**What it asks for:**
- Destination folder path to copy the backup zip to (local filesystem)

**What it does:**
1. Creates a timestamped zip of everything in `accepted/` (e.g. `accepted_backup_20260619_143022.zip`).
2. Saves the zip to `backups/` locally.
3. Copies the same zip to the destination path you provided.
4. Leaves `accepted/` untouched — this is a copy, not a move.

**Filesystem state after:** zip present in both `backups/` and the destination path; `accepted/` unchanged.

---

### 6) Manifest Builder

**Prerequisite:** none (creates `manifest.csv` if it doesn't exist)

**What it asks for:**
- A Google Drive parent folder ID whose immediate child folders you want to review

**What it does:**
1. Lists all immediate child folders of the given Drive folder.
2. Appends any folder not already in `manifest.csv` as a new row with status `pending`.
3. Skips folders whose Drive ID is already present (idempotent — safe to re-run).
4. Prints how many rows were added vs. already present.

**Filesystem state after:** `manifest.csv` created/updated with `folder, id, status` rows.

> Run this once per parent folder. After building the manifest, use option 1 (Download & Review) to walk through all the subfolders automatically.
