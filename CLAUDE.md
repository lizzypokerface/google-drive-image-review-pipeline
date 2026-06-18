# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local, menu-driven CLI (`app.py`) that implements a recurring photo-vetting
cycle against Google Drive: download images from a Drive folder or local
folder, review them one by one (accept/reject), batch the accepted images
into dated upload folders, clear out the rejected pile, then re-upload the
batches back to Drive. See `docs/workflow.md` for the full end-to-end walkthrough
including the manifest-driven multi-folder flow — read it before making
behavioral changes, since the menu options are designed to run in a specific
order across repeated cycles.

## Commands

```
uv sync                                         # install deps into .venv (first time or after pyproject.toml changes)
uv run python app.py                            # run the app
uv run python -m py_compile app.py drive_tools\*.py   # syntax-check after edits
```

There is no test suite, linter, or build step. Dependencies are declared in
`pyproject.toml`; `uv sync` resolves them into `.venv` and locks versions in
`uv.lock`.

## Architecture

- **`app.py`** — the only entry point and the only place that owns user I/O
  (the menu loop, all `input()` prompts). It dispatches to plain functions in
  `drive_tools/`; those modules contain no `input()`/menu logic of their own
  by design, so they stay reusable/testable independent of the CLI.
- **`drive_tools/client.py`** — all Google Drive API plumbing: OAuth
  (`get_service`), listing (`list_items`), and the four file-level primitives
  used everywhere else (`download_file`, `upload_file`, `create_drive_folder`,
  `find_drive_child`). `PROJECT_ROOT` (the repo root, not `drive_tools/`) is
  defined here and imported by every other module to locate
  `credentials.json`/`token.json` and the `downloads/`/`accepted/`/`rejected/`/`batch_uploads/`
  working folders, all of which are created at runtime (not checked in).
- **`drive_tools/image_review.py`** — download/ingest images into
  `downloads/`, then a Tkinter `ReviewApp` for accept/reject review
  (Left = accept → `accepted/`, Right = reject → `rejected/`, Esc = stop).
  Filters strictly to image mimetypes/extensions; everything else is
  discarded without download.
- **`drive_tools/batch_sorter.py`** — moves (not copies) everything in
  `accepted/` into `batch_uploads/<YEAR>_<NNNN>/` folders of a fixed size.
  Moving (rather than copying) is intentional: it's what keeps `accepted/`
  representing only "not yet batched" images across repeated cycles — don't
  change this back to a copy without re-reading the "Batch Sort" section of
  the README, since the original copy-based behavior caused recurring
  re-batching/re-upload duplication.
- **`drive_tools/uploader.py`** — uploads every folder in `batch_uploads/` to
  a given Drive folder ID, mirroring local batch folder names as Drive
  subfolders. Designed to be safe to re-run after an interruption:
  `create_drive_folder` reuses an existing same-named Drive folder instead of
  duplicating it, and per-file uploads are skipped via `find_drive_child` if
  a same-named file already exists in the destination folder.
- **`drive_tools/manifest.py`** — `build_manifest` lists immediate child
  folders of a Drive parent into `manifest.csv` (folder, id, status). Helper
  functions `read_rows`, `write_rows`, `update_status`, and `next_row` are
  used by `app.py`'s manifest-driven `download_and_review` loop to track
  progress across sessions. `MANIFEST_PATH` is in the repo root.
- **`drive_tools/backup.py`** — `backup_accepted` zips `accepted/` to a
  timestamped archive in `backups/` and copies it to a user-given path.
  Does not move or delete anything in `accepted/`.

### Manifest-driven flow

When `manifest.csv` is present, option 1 (Download & Review) walks manifest
rows automatically instead of prompting for a folder ID each time. Each
subfolder downloads into `downloads/<sanitized_name>_<folder_id>/`; status
moves `pending → downloaded → reviewed`. After a folder's review window
closes with all images moved, the empty subfolder is deleted and the row is
marked `reviewed`. If the user hits Esc early (status stays `downloaded`), the
next run resumes that folder.

**Preloading:** immediately after the current folder's download completes and
before its review window opens, the next `pending` row is downloaded
synchronously into its own subfolder and marked `downloaded`. This means from
folder 2 onward, review starts immediately with no download wait.

## Auth / scopes

`SCOPES` in `drive_tools/client.py` includes both `drive.readonly` (listing/
downloading arbitrary folders) and `drive.file` (creating folders/uploading
files). `get_service()` checks the cached `token.json` against `SCOPES` via
`creds.has_scopes(...)` and forces a fresh OAuth flow if the token predates a
scope addition — keep that check in mind if you ever add a new scope.

## Conventions worth preserving

- Collision-safe naming: `image_review.unique_destination()` checks across
  `downloads/`, `accepted/`, and `rejected/` before writing a new file, so
  same-named images from different source folders never overwrite each
  other. `batch_sorter.get_unique_filename()` does the equivalent for batch
  moves — it checks both the in-run tracker dict and the target batch
  folder on disk, since `shutil.move` overwrites silently on Windows when
  the destination already exists (e.g. on a rerun into a partially-filled
  batch folder).
- Idempotent/skip-if-exists is the norm for anything that touches the
  network: `download_file` skips files already on disk, `uploader` skips
  files already present in the destination Drive folder. Follow this pattern
  for any new network operation here.
- `drive_tools/` modules expose plain functions only — no `argparse`, no
  `input()`. If you add a new tool, wire its user-facing prompts into
  `app.py`'s menu rather than the module itself.
