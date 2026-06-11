#!/usr/bin/env python3
"""Compose a Telegram-formatted report from briquette price data.

Always uses absolute paths. Reads JSON, computes stats, outputs Markdown.
"""

import json
import os
import sys

# ABSOLUTE paths
DATA_DIR = "/opt/data/briquette-prices"
PRICE_FILE = os.path.join(DATA_DIR, "briquette_prices.json")
CHART_PNG_FILE = os.path.join(DATA_DIR, "briquette_chart.png")


def compose_report():
    """Read price data and return formatted Telegram message."""
    if not os.path.exists(PRICE_FILE):
        return "ERROR: Price file not found"

    try:
        with open(PRICE_FILE) as f:
            prices = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return f"ERROR: Could not read price data ({e})"

    if not prices:
        return "No price data available"

    today = prices[-1]["date"]
    price = prices[-1]["price"]
    change = 0.0
    pct = 0.0
    icon = "➡️"

    if len(prices) >= 2:
        prev = prices[-2]["price"]
        change = price - prev
        pct = (change / prev) * 100 if prev else 0
        if pct > 0:
            icon = "📈"
        elif pct < 0:
            icon = "📉"

    all_p = [p["price"] for p in prices]

    return (
        f"🪵 **Briquette Price Report** — {today}\n"
        f"\n"
        f"**Current Price:** {price:.2f} €/t\n"
        f"**Change:** {change:+.2f} ({pct:+.2f}%) {icon}\n"
        f"**Data Points:** {len(prices)}\n"
        f"**Period:** {prices[0]['date']} → {today}\n"
        f"**Average:** {sum(all_p) / len(all_p):.2f} €/t\n"
        f"**High:** {max(all_p):.2f} €/t\n"
        f"**Low:** {min(all_p):.2f} €/t\n"
        f"\n"
        f"Source: skaidubriketes.lv\n"
        f"\n"
        f"MEDIA:{CHART_PNG_FILE}"
    )


if __name__ == "__main__":
    print(compose_report())
