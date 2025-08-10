# bridge.py — GitHub bridge (commit_file + append_line)
# Krever env:
#   GITHUB_TOKEN  – classic PAT eller fine‑grained med repo:contents
#   GITHUB_REPO   – f.eks. "Tom-debug-design/atomicbot-agent"
#   GITHUB_BRANCH – f.eks. "main" (valgfri, default main)

import os
import base64
import json
import requests
from typing import Optional

GITHUB_TOKEN  = os.getenv("GITHUB_TOKEN", "").strip()
GITHUB_REPO   = os.getenv("GITHUB_REPO", "").strip()
GITHUB_BRANCH = os.getenv("GITHUB_BRANCH", "main").strip()

API_BASE = "https://api.github.com"

def _headers():
    if not GITHUB_TOKEN:
        raise RuntimeError("GITHUB_TOKEN mangler")
    return {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

def _ensure_repo():
    if not GITHUB_REPO or "/" not in GITHUB_REPO:
        raise RuntimeError("GITHUB_REPO mangler eller er ugyldig (forventet 'owner/repo')")

def _get_contents(path: str) -> dict:
    """Hent innhold/sha for en fil (kan returnere 404)."""
    _ensure_repo()
    url = f"{API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
    params = {"ref": GITHUB_BRANCH}
    r = requests.get(url, headers=_headers(), params=params, timeout=20)
    if r.status_code == 200:
        return r.json()
    elif r.status_code == 404:
        return {"not_found": True}
    else:
        raise RuntimeError(f"GET contents feilet {r.status_code}: {r.text}")

def commit_file(path: str, content: str, message: Optional[str] = None) -> bool:
    """
    Opprett/oppdater fil i repoet på valgt branch.
    Overstyrer hele innholdet (bruk append_line for å legge til linjer).
    """
    _ensure_repo()
    if not isinstance(content, (str, bytes)):
        content = str(content)
    if isinstance(content, str):
        raw_bytes = content.encode("utf-8")
    else:
        raw_bytes = content

    enc = base64.b64encode(raw_bytes).decode("ascii")
    existing = _get_contents(path)
    sha = None if existing.get("not_found") else existing.get("sha")

    url = f"{API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
    payload = {
        "message": message or f"Update {path}",
        "content": enc,
        "branch": GITHUB_BRANCH,
    }
    if sha:
        payload["sha"] = sha

    r = requests.put(url, headers=_headers(), data=json.dumps(payload), timeout=30)
    if r.status_code in (200, 201):
        return True
    # nyttig feilmelding tilbake til Discord-loggene
    raise RuntimeError(f"PUT contents feilet {r.status_code}: {r.text}")

def append_line(path: str, line: str, message: Optional[str] = None) -> bool:
    """
    Legg til ÉN linje i en fil. Oppretter filen hvis den ikke finnes.
    Bruker token/Contents API (fungerer på private repo).
    """
    existing = _get_contents(path)
    if existing.get("not_found"):
        new_text = f"{line}\n"
        return commit_file(path, new_text, message or f"Create {path}")
    else:
        # decode base64 → append → commit med sha
        b64 = existing.get("content", "")
        if existing.get("encoding") == "base64":
            old_bytes = base64.b64decode(b64)
            old_text = old_bytes.decode("utf-8", errors="replace")
        else:
            # fallback – prøv å bruke rå felt hvis noen proxies endrer respons
            old_text = b64

        sep = "" if old_text.endswith("\n") or old_text == "" else "\n"
        new_text = f"{old_text}{sep}{line}\n"

        _ensure_repo()
        url = f"{API_BASE}/repos/{GITHUB_REPO}/contents/{path}"
        payload = {
            "message": message or f"Append {path}",
            "content": base64.b64encode(new_text.encode("utf-8")).decode("ascii"),
            "branch": GITHUB_BRANCH,
            "sha": existing.get("sha"),
        }
        r = requests.put(url, headers=_headers(), data=json.dumps(payload), timeout=30)
        if r.status_code in (200, 201):
            return True
        raise RuntimeError(f"Append PUT feilet {r.status_code}: {r.text}")