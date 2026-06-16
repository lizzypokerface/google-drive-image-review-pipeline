# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A local, menu-driven CLI (`app.py`) that implements a recurring photo-vetting
cycle against Google Drive: download images from a Drive folder or local
folder, review them one by one (accept/reject), batch the accepted images
into dated upload folders, clear out the rejected pile, then re-upload the
batches back to Drive. See `README.md` for the full conceptual walkthrough
("The Full Cycle" section) — read it before making behavioral changes, since
the four menu options are designed to run in a specific order across
repeated cycles.

## Commands

```
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib tqdm Pillow
python app.py
python -m py_compile app.py drive_tools\*.py   # syntax-check after edits
```

There is no test suite, linter, or build step. `conda activate base` provides
a working Python interpreter with the dependencies installed in this dev
environment (plain `python`/`py` may not resolve on PATH).

Note: `requirements.txt` does not exist yet — dependencies are documented only
in `README.md`'s `pip install` line.

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
  other. `batch_sorter.get_unique_filename()` does the equivalent within a
  batch run.
- Idempotent/skip-if-exists is the norm for anything that touches the
  network: `download_file` skips files already on disk, `uploader` skips
  files already present in the destination Drive folder. Follow this pattern
  for any new network operation here.
- `drive_tools/` modules expose plain functions only — no `argparse`, no
  `input()`. If you add a new tool, wire its user-facing prompts into
  `app.py`'s menu rather than the module itself.
