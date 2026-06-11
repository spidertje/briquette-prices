#!/usr/bin/env python3
"""Commit and push briquette data to GitHub after each run."""
import json
import subprocess
import sys
import os

SCRIPT_DIR = "/opt/data/briquette-prices"
os.chdir(SCRIPT_DIR)

# Read the working token from gh_test.py
token = None
with open(os.path.join(SCRIPT_DIR, "gh_test.py")) as f:
    for line in f:
        if "token = " in line and "{" not in line:
            token = line.strip().split('"')[1]
            break

if not token:
    print("ERROR: Could not read token from gh_test.py", file=sys.stderr)
    sys.exit(1)

# Set remote URL with token
subprocess.run(
    ["git", "remote", "set-url", "origin", f"https://{token}@github.com/spidertje/briquette-prices.git"],
    check=True
)

# Check if there are changes
result = subprocess.run(["git", "diff", "--quiet", "HEAD"], capture_output=True)
if result.returncode == 0:
    print("No changes to commit.")
else:
    # Read the latest price for the commit message
    with open("briquette_prices.json") as f:
        prices = json.load(f)
    latest = prices[-1]
    msg = f"Update briquette prices: {len(prices)} points, latest: {latest['date']} @ {latest['price']}€/t"

    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", msg], check=True)
    subprocess.run(["git", "push", "origin", "master"], check=True)
    print("Pushed to GitHub.")
