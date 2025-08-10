# agent_push.py
import os, sys, json, base64, requests
from datetime import datetime, timezone

def tell(msg: str):
    print(msg, flush=True)
    wh = os.getenv("DISCORD_WEBHOOK")
    if wh:
        try:
            requests.post(wh, json={"content": msg}, timeout=15)
        except Exception:
            pass

def require_env(keys):
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        tell(f"❌ Mangler env vars: {', '.join(missing)}")
        sys.exit(2)

def push_test():
    require_env(["GITHUB_TOKEN", "GITHUB_REPO"])
    token  = os.getenv("GITHUB_TOKEN").strip()
    repo   = os.getenv("GITHUB_REPO").strip()
    branch = os.getenv("GITHUB_BRANCH", "main").strip() or "main"

    # Ekstra sanity
    if not token.startswith("github_pat_"):
        tell("⚠️ GITHUB_TOKEN ser ikke ut som et nytt PAT (starter ikke med 'github_pat_'). Sjekk scope=repo.")
    if "/" not in repo:
        tell("❌ GITHUB_REPO må være på formen 'owner/repo'.")
        sys.exit(2)

    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    filename = "bridge_test_live.txt"
    url = f"https://api.github.com/repos/{repo}/contents/{filename}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    # Finn SHA hvis filen finnes
    sha = None
    r = requests.get(f"{url}?ref={branch}", headers=headers, timeout=20)
    if r.status_code == 200:
        try:
            sha = r.json().get("sha")
        except Exception:
            pass

    body = {
        "message": f"Bridge test {stamp}",
        "content": base64.b64encode(f"Bridge is alive - {stamp}".encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha

    res = requests.put(url, headers=headers, json=body, timeout=30)

    # Rapportér tydelig
    try:
        j = res.json()
    except Exception:
        j = {"raw": res.text[:400]}

    if res.status_code in (200, 201):
        tell(f"✅ Push OK ({res.status_code}) – {repo}@{branch} -> {filename}")
        sys.exit(0)
    else:
        tell(f"❌ Push FEIL ({res.status_code}) – detaljer: {json.dumps(j)[:600]}")
        # Vanlige feilkoder:
        # 401: Ugyldig token
        # 403: Mangler rettigheter / SSO ikke godkjent / rate limit
        # 404: Repo/branch feil
        # 422: Validation failed (ofte mangler 'sha' ved update, men vi setter den)
        sys.exit(1)

if __name__ == "__main__":
    push_test()