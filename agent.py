import os
import time
from git import Repo

# Miljøvariabel for GitHub-token
token = os.getenv("GITHUB-TOKEN")
if not token:
    print("❌ Feil: GITHUB-TOKEN er ikke satt!")
    exit(1)

# Repo-URL med token (bruker hovedrepoet!)
repo_url = f"https://oauth2:{token}@github.com/Tom-debug-design/Atomicbot-heartbeat-test.git"
local_path = "repo"
INTERVAL = 3600  # 1 time

# Klon repo hvis det ikke finnes lokalt
try:
    if not os.path.exists(local_path):
        print("🔄 Kloner hovedrepo...")
        repo = Repo.clone_from(repo_url, local_path, branch='main')
    else:
        repo = Repo(local_path)
except Exception as e:
    print(f"🚫 Klarte ikke klone repo: {e}")
    exit(1)

# Git config
with repo.config_writer() as cw:
    cw.set_value("user", "name", "AtomicBot Agent")
    cw.set_value("user", "email", "[email protected]")

origin = repo.remotes.origin
print("✅ Agent kjører. Starter heartbeat-loop...")

while True:
    try:
        origin.pull()
    except Exception as e:
        print(f"⚠️ Pull-feil: {e}")

    # Oppdater heartbeat.txt
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    heartbeat_path = os.path.join(local_path, "heartbeat.txt")
    with open(heartbeat_path, "w") as f:
        f.write(f"AtomicBot er live – {timestamp}\n")

    try:
        repo.index.add([heartbeat_path])
        repo.index.commit("Oppdaterer heartbeat-tidspunkt")
        origin.push()
        print(f"🟢 Pushet heartbeat: {timestamp}")
    except Exception as e:
        print(f"❌ Push-feil: {e}")

    time.sleep(INTERVAL)
