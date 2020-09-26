import requests
from typing import List
from urllib.parse import urljoin
from bs4 import BeautifulSoup

session = requests.Session()


def list_remote_files(url: str, recursive: bool) -> List[str]:
    """
    A function used to create a listing of all files of a given path on the server

    Args:
        url: the url which should be searched for files
        recursive: definition if the function should iteratively list files
        from sub folders

    Returns:
        a list of strings representing the files from the path
    """

    if not url.endswith("/"):
        url += "/"

    r = session.get(url)
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "lxml")

    files_and_folders = [
        link.get("href") for link in soup.find_all("a") if link.get("href") != "../"
    ]

    files = []
    folders = []

    for f in files_and_folders:
        if not f.endswith("/"):
            files.append(urljoin(url, f))
        else:
            folders.append(urljoin(url, f))

    if recursive:
        files_in_folders = [list_remote_files(folder, recursive) for folder in folders]

        for files_in_folder in files_in_folders:
            files.extend(files_in_folder)

    return files
