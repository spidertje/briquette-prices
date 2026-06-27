#!/usr/bin/env python3
"""Commit and push briquette data to GitHub after each run.

Token lookup order: GITHUB_TOKEN env var → GITHUB_PAT env var → .github_token file.
Push handles "no changes" and "everything up-to-date" gracefully.
"""
import json
import os
import subprocess
import sys

SCRIPT_DIR = "/home/hermeswebui/.hermes/home/briquette-projects"
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
os.chdir(SCRIPT_DIR)

# Read the GitHub token — env var first, then local file as fallback
token = os.environ.get("GITHUB_TOKEN", os.environ.get("GITHUB_PAT", ""))
if not token:
    token_file = os.path.join(SCRIPT_DIR, ".github_token")
    if os.path.exists(token_file):
        with open(token_file) as f:
            token = f.read().strip()

if not token:
    print("WARNING: No GitHub token found, skipping push.", file=sys.stderr)
    sys.exit(0)

# Initialize git repo if not already done
if not os.path.exists(".git"):
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Briquette Bot"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "bot@briquette.local"], check=True, capture_output=True)

# Add or update remote URL with token for auth
REMOTE_URL = f"https://{token}@github.com/spidertje/briquette-prices.git"
try:
    subprocess.run(["git", "remote", "get-url", "origin"], check=True, capture_output=True)
    subprocess.run(["git", "remote", "set-url", "origin", REMOTE_URL], check=True, capture_output=True)
except subprocess.CalledProcessError:
    subprocess.run(["git", "remote", "add", "origin", REMOTE_URL], check=True, capture_output=True)

# Add all changes
result = subprocess.run(["git", "add", "-A"], capture_output=True)
if result.returncode != 0:
    print(f"ERROR: git add failed: {result.stderr.decode()}", file=sys.stderr)
    sys.exit(1)

# Check if there are changes to commit
result = subprocess.run(["git", "diff", "--quiet", "HEAD"], capture_output=True)
if result.returncode == 0:
    print("No changes to commit.")
    sys.exit(0)

# Read the latest price for the commit message
with open(os.path.join(DATA_DIR, "briquette_prices.json")) as f:
    prices = json.load(f)
latest = prices[-1]
msg = f"Update briquette prices: {len(prices)} points, latest: {latest['date']} @ {latest['price']}e/t"

subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)

# Try to push
push_result = subprocess.run(["git", "push", "origin", "master"], capture_output=True)
if push_result.returncode == 0:
    print("Pushed to GitHub.")
elif b"Everything up-to-date" in push_result.stdout or b"Everything up-to-date" in push_result.stderr:
    print("Already up to date.")
elif b"non-fast-forward" in push_result.stderr or b"Updates were rejected" in push_result.stderr:
    print("Remote has new commits. Pulling first...")
    pull = subprocess.run(
        ["git", "pull", "origin", "master", "--allow-unrelated-histories", "--no-rebase"],
        capture_output=True
    )
    if pull.returncode != 0 and b"CONFLICT" in pull.stderr:
        # Resolve add/add conflicts on script files by keeping ours
        for f in ["briquette-chart.py", "briquette-telegram.py", "push-to-github.py"]:
            subprocess.run(["git", "checkout", "--ours", f], capture_output=True)
            subprocess.run(["git", "add", f], capture_output=True)
        # Resolve data file: keep HEAD (remote full history), NOT --ours
        subprocess.run(["git", "checkout", "HEAD", "--", "data/briquette_prices.json"], capture_output=True)
        subprocess.run(["git", "add", "data/briquette_prices.json"], capture_output=True)
        subprocess.run(["git", "commit", "-m", "Merge: resolve conflicts — keep local scripts, remote data"], capture_output=True)
        # NOTE: This may lose entries that were only in the local session.
        # After resolution, check if today's data was lost. If so, manually re-add it.
        print("Conflicts resolved. Pushing again...")
        subprocess.run(["git", "push", "origin", "master"], capture_output=True)
    elif pull.returncode == 0:
        subprocess.run(["git", "push", "origin", "master"], capture_output=True)
    print("Push complete.")
else:
    print(f"WARNING: push failed ({push_result.returncode}): {push_result.stderr.decode()}", file=sys.stderr)
