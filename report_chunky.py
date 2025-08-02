import os
import requests
from base64 import b64encode
from datetime import datetime

REPO_OWNER = "Tom-debug-design"
REPO_NAME = "atomicbot-agent"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")

# Filnavn med dato (endre prefiks hvis du vil!)
date_str = datetime.utcnow().strftime("%Y-%m-%d")
FILE_TO_PUSH = f"chunky_report_{date_str}.txt"
GITHUB_PATH = FILE_TO_PUSH
COMMIT_MESSAGE = f"Auto-push: ChunkyAI daily report {date_str}"

def get_file_sha():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{GITHUB_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()["sha"]
    return None

def push_file():
    with open(FILE_TO_PUSH, "w", encoding="utf-8") as f:
        f.write(f"ChunkyAI daily report for {date_str}\nThis is a test report!\n")
    with open(FILE_TO_PUSH, "rb") as f:
        content = b64encode(f.read()).decode("utf-8")
    sha = get_file_sha()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{GITHUB_PATH}"
    data = {
        "message": COMMIT_MESSAGE,
        "content": content,
        "branch": "main"
    }
    if sha:
        data["sha"] = sha
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.put(url, json=data, headers=headers)
    if r.status_code in [200, 201]:
        print(f"✅ Report {FILE_TO_PUSH} pushed to GitHub!")
    else:
        print(f"❌ Failed to push file: {r.text}")

if __name__ == "__main__":
    push_file()
