#!/usr/bin/env python3
"""Commit and push briquette data to GitHub after each run.

Token lookup order: GITHUB_TOKEN env var → GITHUB_PAT env var → .github_token file.
Push handles "no changes" and "everything up-to-date" gracefully.
"""
import json
import os
import subprocess
import sys

# Load env vars from .env file (absolute paths, try both locations)
_ENV_PATHS = [
    "/home/hermes/.hermes/.env",
    "/home/hermes/.hermes/home/.hermes/.env",
]
for _p in _ENV_PATHS:
    if os.path.exists(_p):
        with open(_p) as _f:
            for line in _f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    k, v = line.split('=', 1)
                    os.environ.setdefault(k, v)
        break

SCRIPT_DIR = "/opt/data/briquette-projects"
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

# Set remote URL with token for auth
subprocess.run(
    ["git", "remote", "set-url", "origin", f"https://{token}@github.com/spidertje/briquette-prices.git"],
    check=True, capture_output=True
)

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

# Commit changes
subprocess.run(["git", "commit", "-m", msg], check=True, capture_output=True)

# Try to push; exit 0 is success, "Everything up-to-date" is fine
push_result = subprocess.run(["git", "push", "origin", "master"], capture_output=True)
if push_result.returncode == 0:
    print("Pushed to GitHub.")
elif b"Everything up-to-date" in push_result.stdout or b"Everything up-to-date" in push_result.stderr:
    print("Already up to date.")
else:
    print(f"WARNING: push failed ({push_result.returncode}): {push_result.stderr.decode()}", file=sys.stderr)
