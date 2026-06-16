import os
import io
import sys
import time
from tqdm import tqdm
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload, MediaFileUpload
from googleapiclient.errors import HttpError

SCOPES = [
    'https://www.googleapis.com/auth/drive.readonly',
    'https://www.googleapis.com/auth/drive.file',
]
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MAX_RETRIES = 5


def get_service():
    creds = None
    token_path = os.path.join(PROJECT_ROOT, 'token.json')
    creds_path = os.path.join(PROJECT_ROOT, 'credentials.json')

    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(token_path, SCOPES)
        if not creds.has_scopes(SCOPES):
            creds = None

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(creds_path):
                print("Error: credentials.json not found in project root.")
                print(f"Expected: {creds_path}")
                sys.exit(1)
            flow = InstalledAppFlow.from_client_secrets_file(creds_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(token_path, 'w') as f:
            f.write(creds.to_json())

    return build('drive', 'v3', credentials=creds)


def list_items(service, parent_id, mime_filter=None):
    items = []
    page_token = None
    query = f"'{parent_id}' in parents and trashed = false"
    if mime_filter == 'folders':
        query += " and mimeType = 'application/vnd.google-apps.folder'"
    elif mime_filter == 'files':
        query += " and mimeType != 'application/vnd.google-apps.folder'"

    while True:
        resp = service.files().list(
            q=query,
            fields="nextPageToken, files(id, name, size, mimeType)",
            pageToken=page_token,
            pageSize=1000,
        ).execute()
        items += resp.get('files', [])
        page_token = resp.get('nextPageToken')
        if not page_token:
            break

    return items


def download_file(service, file_id, file_name, dest_dir, file_size):
    destination = os.path.join(dest_dir, file_name)

    if os.path.exists(destination):
        print(f"    skip (exists): {file_name}")
        return

    request = service.files().get_media(fileId=file_id)

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            with io.FileIO(destination, 'wb') as fh:
                downloader = MediaIoBaseDownload(fh, request, chunksize=1024 * 1024 * 5)
                with tqdm(total=file_size, unit='B', unit_scale=True, desc=f"    {file_name[:35]}", leave=False) as pbar:
                    done = False
                    while not done:
                        status, done = downloader.next_chunk()
                        if status:
                            pbar.update(status.resumable_progress - pbar.n)
            break
        except HttpError as e:
            if e.resp.status in (429, 500, 503):
                wait = 2 ** attempt
                print(f"    [{e.resp.status}] {file_name} — retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
                if os.path.exists(destination):
                    os.remove(destination)
            else:
                raise
    else:
        print(f"    FAILED after {MAX_RETRIES} retries: {file_name}")


def find_drive_child(service, name, parent_id, folders_only=False):
    escaped_name = name.replace("'", "\\'")
    query = f"'{parent_id}' in parents and trashed = false and name = '{escaped_name}'"
    if folders_only:
        query += " and mimeType = 'application/vnd.google-apps.folder'"

    resp = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
    matches = resp.get('files', [])
    return matches[0]['id'] if matches else None


def create_drive_folder(service, name, parent_id):
    existing_id = find_drive_child(service, name, parent_id, folders_only=True)
    if existing_id:
        return existing_id

    metadata = {
        'name': name,
        'mimeType': 'application/vnd.google-apps.folder',
        'parents': [parent_id],
    }
    folder = service.files().create(body=metadata, fields='id').execute()
    return folder['id']


def upload_file(service, file_path, file_name, parent_id):
    metadata = {'name': file_name, 'parents': [parent_id]}
    media = MediaFileUpload(file_path, resumable=True, chunksize=1024 * 1024 * 5)
    request = service.files().create(body=metadata, media_body=media, fields='id')

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = None
            with tqdm(total=os.path.getsize(file_path), unit='B', unit_scale=True,
                      desc=f"    {file_name[:35]}", leave=False) as pbar:
                while response is None:
                    status, response = request.next_chunk()
                    if status:
                        pbar.update(status.resumable_progress - pbar.n)
            return response['id']
        except HttpError as e:
            if e.resp.status in (429, 500, 503):
                wait = 2 ** attempt
                print(f"    [{e.resp.status}] {file_name} — retrying in {wait}s (attempt {attempt}/{MAX_RETRIES})")
                time.sleep(wait)
            else:
                raise

    print(f"    FAILED after {MAX_RETRIES} retries: {file_name}")
    return None
