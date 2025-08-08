import os
import base64
import requests
from datetime import datetime

# Les miljøvariabler
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
GITHUB_REPO = os.getenv("GITHUB_REPO")  # f.eks. "brukernavn/repo-navn"

def commit_file(filename, content):
    if not GITHUB_TOKEN or not GITHUB_REPO:
        print("❌ Mangler GITHUB_TOKEN eller GITHUB_REPO i miljøvariabler.")
        return

    url = f"https://api.github.com/repos/{GITHUB_REPO}/contents/{filename}"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json"
    }

    # Sjekk om fil finnes fra før (for SHA)
    sha = None
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        sha = r.json()["sha"]

    # Lag commit
    data = {
        "message": f"Update {filename} at {datetime.utcnow().isoformat()}",
        "content": base64.b64encode(content.encode()).decode(),
        "branch": "main"
    }
    if sha:
        data["sha"] = sha

    res = requests.put(url, headers=headers, json=data)
    if res.status_code in (200, 201):
        print(f"✅ Fil '{filename}' pushet til GitHub.")
    else:
        print(f"❌ Push feilet: {res.status_code} - {res.text}")


if __name__ == "__main__":
    commit_file("bridge_test.txt", f"Bridge test OK - {datetime.utcnow().isoformat()}")