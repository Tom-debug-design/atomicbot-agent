import os
from git import Repo

GH_PAT = os.getenv('GH_PAT')
if not GH_PAT:
    print("Error: GH_PAT not set as environment variable.")
    exit(1)

REPO_URL = f"https://x-access-token:{GH_PAT}@github.com/Tom-debug-design/atomicbot-agent.git"
LOCAL_PATH = "/tmp/atomicbot-agent"

if not os.path.exists(LOCAL_PATH):
    Repo.clone_from(REPO_URL, LOCAL_PATH)

# Lag en testfil
test_filename = f"bridge_test_agent_{os.getpid()}.txt"
with open(os.path.join(LOCAL_PATH, test_filename), "w") as f:
    f.write("Test fra Railway-agent\n")

repo = Repo(LOCAL_PATH)
repo.git.add(all=True)
repo.git.commit('-m', f'Automatisk test push fra agent: {test_filename}')
repo.git.push()

print(f"✅ Ferdig – sjekk at {test_filename} vises i GitHub-repoet!")
