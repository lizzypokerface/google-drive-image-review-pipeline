import csv
import os

from drive_tools.client import PROJECT_ROOT, list_items

MANIFEST_PATH = os.path.join(PROJECT_ROOT, 'manifest.csv')
FIELDNAMES = ['folder', 'id', 'status']


def read_rows():
    if not os.path.exists(MANIFEST_PATH):
        return []
    with open(MANIFEST_PATH, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def write_rows(rows):
    with open(MANIFEST_PATH, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def update_status(folder_id, new_status):
    rows = read_rows()
    for row in rows:
        if row['id'] == folder_id:
            row['status'] = new_status
            break
    write_rows(rows)


def next_row(status):
    for row in read_rows():
        if row['status'] == status:
            return row
    return None


def build_manifest(service, parent_folder_id):
    existing = {row['id'] for row in read_rows()}
    folders = list_items(service, parent_folder_id, mime_filter='folders')

    new_rows = []
    for folder in folders:
        if folder['id'] not in existing:
            new_rows.append({'folder': folder['name'], 'id': folder['id'], 'status': 'pending'})

    if new_rows:
        all_rows = read_rows() + new_rows
        write_rows(all_rows)

    return len(new_rows), len(folders) - len(new_rows)
