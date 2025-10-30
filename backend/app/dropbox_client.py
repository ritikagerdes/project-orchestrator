import requests
import os

class DropboxClient:
    """
    Minimal Dropbox client using the HTTP API. Requires DROPBOX_TOKEN env var.
    """

    LIST_URL = "https://api.dropboxapi.com/2/files/list_folder"
    DOWNLOAD_URL = "https://content.dropboxapi.com/2/files/download"

    def __init__(self, token: str):
        self.token = token

    def list_files(self, path: str = "/SOWs"):
        headers = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}
        payload = {"path": path, "recursive": False, "limit": 100}
        r = requests.post(self.LIST_URL, headers=headers, json=payload)
        r.raise_for_status()
        entries = r.json().get("entries", [])
        # filter for documents
        files = [e for e in entries if e[".tag"] == "file"]
        return files

    def download_file(self, path_lower: str):
        headers = {"Authorization": f"Bearer {self.token}", "Dropbox-API-Arg": f'{{"path": "{path_lower}"}}'}
        r = requests.post(self.DOWNLOAD_URL, headers=headers)
        r.raise_for_status()
        # use content and decode safely (fallback to replace any bad bytes)
        return r.content.decode("utf-8", errors="replace")