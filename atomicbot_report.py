import os
import requests
from base64 import b64encode

REPO_OWNER = "Tom-debug-design"
REPO_NAME = "atomicbot-agent"
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
FILE_TO_PUSH = "atomicbot_report_ai.txt"
GITHUB_PATH = "atomicbot_report_ai.txt"
COMMIT_MESSAGE = "Auto-push: AI-rapport fra AtomicBot"

def get_file_sha():
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{GITHUB_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}"}
    r = requests.get(url, headers=headers)
    if r.status_code == 200:
        return r.json()["sha"]
    return None

def push_file():
    with open(FILE_TO_PUSH, "rb") as f:
        content = b64encode(f.read()).decode("utf-8")
    sha = get_file_sha()
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/contents/{GITHUB_PATH}"
    headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github+json"}
    data = {
        "message": COMMIT_MESSAGE,
        "content": content,
        "branch": "main"
    }
    if sha: data["sha"] = sha
    r = requests.put(url, headers=headers, json=data)
    if r.status_code in [200, 201]:
        print("✅ Rapport pushet til GitHub!")
    else:
        print("❌ Push feilet:", r.text)

if __name__ == "__main__":
    push_file()
