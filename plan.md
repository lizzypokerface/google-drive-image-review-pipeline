# Manifest-driven multi-folder review, preloading, and backups

## Context

The pipeline currently handles one Drive folder (or local folder) at a time:
the user pastes a folder ID into "Download & Review" every time they want to
load a folder's contents, everything lands flat in `downloads/`, gets
reviewed, and the cycle repeats by hand for the next folder. For a recurring
multi-folder workflow (e.g. one Drive folder per month/event) this means
re-entering folder IDs every time and waiting for each download before
review can start.

This plan adds a `manifest.csv`-driven workflow: a "Manifest Builder" menu
option takes one parent Drive folder ID and lists its immediate child
folders into `manifest.csv` (`folder, id, status`) — repo structure is
assumed to be a single level deep (`root -> folder -> pictures`, no further
nesting), so no recursion is needed. "Download & Review" then walks that
manifest automatically (no folder-ID prompt) — downloading each subfolder
into its own `downloads/<name>_<id>/` directory, reviewing it, and deleting
the emptied directory once review finishes. Reviewed rows stay in
`manifest.csv` (status=reviewed) as a permanent record rather than being
deleted. While the user reviews the current folder, the next pending folder
pre-downloads in the background so there's no dead time between folders. A
new "Backup Accepted" option zips `accepted/` to a timestamped archive, kept
locally and copied to a user-given path.

The legacy flow (typed Drive folder ID or local folder path, flat
`downloads/`) must keep working exactly as-is whenever `manifest.csv` does
not exist — this is the fallback path and also what local-folder ingestion
keeps using.

Issues are ordered easiest -> hardest; each is independently testable.

## Issue 0 — Tag MVP

- `git tag mvp` on current HEAD. No code changes.
- Test: `git tag` shows `mvp` pointing at the current commit.

## Issue 1 — Manifest Builder (new module + menu option)

New file `drive_tools/manifest.py`:
- `MANIFEST_PATH = os.path.join(PROJECT_ROOT, 'manifest.csv')`
- `build_manifest(service, parent_folder_id)`: calls
  `list_items(service, parent_folder_id, mime_filter='folders')` (same
  primitive `image_review.download_images` uses for files, just folder
  filter) to get the immediate child folders, then appends a
  `(folder, id, status='pending')` row per child folder to `manifest.csv` —
  only for folder IDs not already present (read existing rows first, skip
  duplicates by `id`) so re-running the builder against the same parent
  folder is safe/idempotent.
- Use the stdlib `csv` module (`csv.DictWriter`/`DictReader`,
  fieldnames `folder,id,status`).

`app.py` changes:
- Add menu option "Manifest Builder" (renumber Quit accordingly).
- Handler prompts for a Drive parent folder ID, calls
  `manifest.build_manifest(get_drive_service(), folder_id)`, prints how many
  rows were added vs already present.

Add `manifest.csv` to `.gitignore` (alongside `downloads`, `accepted`, etc. —
it's runtime-generated, references real Drive folder IDs).

**Test**: run the new menu option against a real Drive folder ID that has
child folders; confirm `manifest.csv` is created with correct
`folder,id,status=pending` rows, and re-running it doesn't duplicate rows.

## Issue 2 — Backup Accepted feature

New file `drive_tools/backup.py`:
- `BACKUPS_DIR = os.path.join(PROJECT_ROOT, 'backups')`
- `backup_accepted(dest_path)`: build a timestamped name
  `f"accepted_backup_{datetime.now():%Y%m%d_%H%M%S}.zip"`, zip the full
  contents of `ACCEPTED_DIR` (`shutil.make_archive` or `zipfile.ZipFile`, no
  filtering, no move/delete — `accepted/` is left untouched) into
  `BACKUPS_DIR` first, then copy that same zip to `dest_path`
  (`shutil.copy2`). Create both `BACKUPS_DIR` and `dest_path` if missing.

`app.py`:
- Add menu option "Backup Accepted" prompting for a destination folder
  path; call `backup.backup_accepted(dest_path)`; print the resulting zip
  name/size on success.

Add `backups/` to `.gitignore`.

**Test**: with a few files in `accepted/`, run the backup option twice in
quick succession; confirm two distinct timestamped zips exist both in
`backups/` and at the destination path, and `accepted/` still has all its
original files afterward. This issue has no dependency on the manifest work
and can be built/tested independently.

## Issue 3 — Manifest-driven Download & Review

`drive_tools/image_review.py` refactor (backward compatible):
- Add a `working_dir=None` parameter (defaulting to `DOWNLOADS_DIR`) to
  `list_pending_images`, `run_review`, and `ReviewApp.__init__` /
  `show_current` / `move_current`, so review can target a per-folder
  subdirectory instead of the flat `downloads/`. `unique_destination` stays
  as-is for the legacy flat path.
- Add `download_images_to(service, folder_id, dest_dir)`: same body as
  `download_images` but downloads into `dest_dir` (created via
  `os.makedirs(dest_dir, exist_ok=True)`) instead of `DOWNLOADS_DIR`, with
  collision checks only against `ACCEPTED_DIR`/`REJECTED_DIR` (each
  manifest subfolder is exclusive to one Drive folder, so no need to check
  other subfolders). `download_images` becomes a thin wrapper calling this
  with `dest_dir=DOWNLOADS_DIR` to avoid duplicating logic.
- Add a folder-name sanitizer (strip `<>:"/\|?*` and trim) used to build the
  subfolder name `f"{sanitized_name}_{folder_id}"` under `downloads/`.

`drive_tools/manifest.py` additions:
- `read_rows()` / `write_rows(rows)` — full read/rewrite of `manifest.csv`.
- `update_status(folder_id, new_status)` — read, patch the matching row,
  rewrite.
- `next_row(status)` — first row matching a given status, else `None`.

`app.py` — `download_and_review()` rewrite:
- If `manifest.MANIFEST_PATH` does not exist: keep the existing prompt loop
  (Drive ID or local path) untouched.
- If it exists: loop —
  1. Prefer a row with status `downloaded` (already fetched, possibly by
     preloading in Issue 4); else take the next `pending` row, download it
     via `download_images_to` into `downloads/<name>_<id>/`, and set its
     status to `downloaded`.
  2. If no `pending`/`downloaded` rows remain (only `reviewed` left), print
     a summary and return to the menu.
  3. Run `image_review.run_review(working_dir=<that subfolder>)`.
  4. After the review window closes, if the subfolder is now empty, delete
     it (`os.rmdir`) and set the row's status to `reviewed`; if not empty
     (user hit Esc early), leave status as `downloaded` so it resumes next
     time.

**Test**: build a manifest against a Drive folder with 2 small subfolders;
run Download & Review twice (resume after Esc, then finish) and confirm:
subfolder downloads appear under `downloads/<name>_<id>/`, statuses move
pending -> downloaded -> reviewed, reviewed rows stay in the CSV, and
folders are deleted only once emptied. Also confirm typing a folder ID with
no `manifest.csv` present still works exactly as before.

## Issue 4 — Preloading next folder (synchronous, no concurrency)

`app.py` — inside the manifest loop from Issue 3, right after the current
folder finishes downloading (status set to `downloaded`) and *before*
`run_review()` is called for it:
- Look up the next `pending` row (excluding the one just downloaded). If
  one exists, download it too via `download_images_to` into its own
  subfolder and set its status to `downloaded` — synchronously, no threads,
  no locks.
- Then proceed to `run_review()` for the current folder as before.
- Print a one-line reminder before this step, e.g. "Preloading next
  folder — please don't close the program until this finishes," since it's
  a blocking network call.
- Net effect: every iteration after the first already has its folder
  downloaded (because the *previous* iteration preloaded it), so review
  starts immediately for folders 2..N. Only the very first folder in a
  session pays for its own download up front (plus, on the first
  iteration, the preload of folder 2 happens before folder 1's review).

**Test**: with a manifest of 3 subfolders, start Download & Review; confirm
the console shows folder 2 downloading right after folder 1 (before folder
1's review window opens), folder 1 review then runs immediately, and after
finishing folder 1, folder 2's review opens immediately (already
downloaded) while folder 3 downloads next. Confirm manifest.csv statuses
update correctly at each step with no corruption (single-threaded, so no
concurrent-write risk).

## Issue 5 — Docs folder: sketch the whole workflow

New file `docs/workflow.md` (created after Issues 0-4 land, once the menu
options and behavior are final):
- A short overview diagram/description of the full recurring cycle end to
  end: Manifest Builder -> Download & Review (with preloading) -> Batch
  Sort -> Clear Rejected -> Upload Batches -> Backup Accepted, including
  where `manifest.csv`, `downloads/`, `accepted/`, `rejected/`,
  `batch_uploads/`, and `backups/` fit in and how state flows between them
  across repeated runs of the program.
- One section per menu option (final numbering from `app.py`'s `MENU`),
  each explaining: what it asks for, what it does step by step, what
  filesystem/manifest state changes as a result, and any
  prerequisites/order-of-operations notes (e.g. manifest must exist before
  Download & Review will use it; Batch Sort expects `accepted/` to be
  populated; Upload Batches expects `batch_uploads/` to be populated).
- Keep this doc separate from `CLAUDE.md` (which targets Claude Code editing
  the repo) — `docs/workflow.md` targets a human user trying to understand
  or operate the tool day to day. Cross-link the two rather than
  duplicating content: `CLAUDE.md` can point to `docs/workflow.md` for the
  full walkthrough.

**Test**: no code to test — review by walking through the doc against the
actual running app and confirming each described step/prompt/outcome
matches reality.

## Files touched

- `app.py` — new menu options, manifest-aware `download_and_review()`,
  synchronous next-folder preload step, backup handler.
- `drive_tools/image_review.py` — `working_dir` parameterization,
  `download_images_to`, folder-name sanitizer.
- `drive_tools/manifest.py` — new.
- `drive_tools/backup.py` — new.
- `.gitignore` — add `manifest.csv`, `backups/`.
- `docs/workflow.md` — new; full workflow + per-option walkthrough.
- `CLAUDE.md` — update once implemented, to document the manifest-driven
  flow and preload behavior alongside the existing four-option cycle
  description, and link to `docs/workflow.md`.

## Verification

After each issue, run `python -m py_compile app.py drive_tools\*.py`, then
exercise that issue's menu option(s) manually against a real (or
disposable test) Drive folder, checking `manifest.csv` contents and the
`downloads/`/`accepted/`/`backups/` filesystem state between steps.
