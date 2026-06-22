#!/usr/bin/env python3
"""Fetch current briquette price from skaidubriketes.lv and update price history.

Uses Pillow for PNG chart generation. Always uses absolute paths.
"""

import json
import os
import re
import sys
import urllib.request
import urllib.error
from datetime import date

SCRIPT_DIR = "/opt/data/briquette-projects"
# Persistent path — survives container restarts (on persistent overlay)
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
PRICE_FILE = os.path.join(DATA_DIR, "briquette_prices.json")
CHART_SVG_FILE = os.path.join(DATA_DIR, "briquette_chart.svg")
CHART_PNG_FILE = os.path.join(DATA_DIR, "briquette_chart.png")

URL = "https://skaidubriketes.lv/"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "lv,en-US,en;q=0.9",
}


def load_prices():
    """Load existing price history from JSON. Very robust."""
    if not os.path.exists(PRICE_FILE):
        return []
    try:
        with open(PRICE_FILE, "r") as f:
            data = json.load(f)
        if not isinstance(data, list):
            print("WARNING: price file was not a list, resetting.", file=sys.stderr)
            return []
        return data
    except (json.JSONDecodeError, OSError) as e:
        print(f"WARNING: failed to load price file ({e}), resetting.", file=sys.stderr)
        return []


def save_prices(prices):
    """Save price history to JSON."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(PRICE_FILE, "w") as f:
        json.dump(prices, f, indent=2)


def fetch_price():
    """Return current briquette price per tonne, or None on failure."""
    req = urllib.request.Request(URL, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            html = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        print(f"ERROR: HTTP {e.code} from {URL}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"ERROR: connection failed: {e.reason}", file=sys.stderr)
        return None
    except TimeoutError:
        print("ERROR: request timed out", file=sys.stderr)
        return None
    except Exception as e:
        print(f"ERROR: unexpected error: {e}", file=sys.stderr)
        return None

    # Strategy 1: Find the prices section and extract the "1 TONNA" price
    prices_section = re.search(
        r'class=.row prices.?(.*?)(?:</section>|$)', html, re.DOTALL | re.IGNORECASE
    )
    if prices_section:
        all_prices = re.findall(
            r'class=.price.?>\s*<span>€</span>\s*(\d+)',
            prices_section.group(0), re.DOTALL | re.IGNORECASE
        )
        if len(all_prices) >= 2:
            try:
                return float(all_prices[1])  # "1 TONNA" is the second entry
            except ValueError:
                pass

    # Strategy 2: Look for title attributes containing price (image titles)
    title_match = re.search(r'title=.*?BRIKETES.*?€(\d+)', html, re.IGNORECASE)
    if title_match:
        try:
            return float(title_match.group(1))
        except ValueError:
            pass

    # Strategy 3: Any € followed by 2-3 digit number in the prices section
    if prices_section:
        any_price = re.search(r'€\s*(\d{2,3})', prices_section.group(0))
        if any_price:
            val = float(any_price.group(1))
            if 100 < val < 1000:
                return val

    print("ERROR: could not parse price from page", file=sys.stderr)
    return None


def generate_png(prices, width=600, height=400):
    """Generate a PNG line chart of historical prices."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        print("WARNING: Pillow not installed, falling back to SVG", file=sys.stderr)
        svg = generate_svg(prices)
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(CHART_SVG_FILE, "w") as f:
            f.write(svg)
        return CHART_SVG_FILE

    if not prices:
        img = Image.new("RGB", (width, height), "#1a1a2e")
        draw = ImageDraw.Draw(img)
        draw.text((width // 2 - 30, height // 2 - 10), "No data", fill="#ffffff")
        img.save(CHART_PNG_FILE)
        return CHART_PNG_FILE

    padding = 60
    chart_w = width - 2 * padding
    chart_h = height - 2 * padding

    all_prices = [p["price"] for p in prices]
    min_price = min(all_prices)
    max_price = max(all_prices)
    price_range = max_price - min_price if max_price != min_price else 10.0
    price_range *= 1.2
    floor_price = min_price - (price_range - (max_price - min_price)) / 2

    def scale_y(p):
        return chart_h - ((p - floor_price) / price_range) * chart_h

    img = Image.new("RGB", (width, height), "#1a1a2e")
    draw = ImageDraw.Draw(img)

    # Grid lines and labels
    n_ticks = min(6, len(prices))
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 10)
        font_bold = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 14)
    except (OSError, IOError):
        font = ImageFont.load_default()
        font_bold = font

    for i in range(n_ticks + 1):
        val = floor_price + (price_range * i / n_ticks)
        y = padding + scale_y(val)
        draw.line([(padding, y), (width - padding, y)], fill="#2a2a4a", width=1)
        draw.text((5, y - 5), f"{val:.0f}€", fill="#888888", font=font)

    # Build points
    points = []
    for i, p in enumerate(prices):
        x = padding + (i / max(len(prices) - 1, 1)) * chart_w
        y = padding + scale_y(p["price"])
        points.append((x, y))

    # X-axis labels
    step = max(1, len(prices) // 8)
    for i, p in enumerate(prices):
        if i % step == 0 or i == len(prices) - 1:
            x = padding + (i / max(len(prices) - 1, 1)) * chart_w
            draw.text((x, height - 15), p["date"][-2:], fill="#888888", font=font)

    # Area fill
    for y_pos in range(int(points[0][1]), padding + chart_h + 1):
        alpha = max(0, 1 - (y_pos - padding) / chart_h)
        r = int(233 * alpha * 0.1)
        draw.line([(padding, y_pos), (padding + chart_w, y_pos)], fill=(r, 20, 50))

    # Line
    for i in range(len(points) - 1):
        draw.line([points[i], points[i + 1]], fill=(233, 69, 96), width=3)

    # Data points
    for i, (x, y) in enumerate(points):
        t = i / max(len(points) - 1, 1)
        r = int(233 * (1 - t) + 15 * t)
        g = int(69 * (1 - t) + 52 * t)
        b = int(96 * (1 - t) + 96 * t)
        draw.ellipse([(x - 3, y - 3), (x + 3, y + 3)], fill=(r, g, b))

    # Highlight last point
    lx, ly = points[-1]
    draw.ellipse([(lx - 5, ly - 5), (lx + 5, ly + 5)], fill="#e94560", outline="#ffffff", width=1)

    # Title
    draw.text((width // 2 - 80, 10), "Briquette Price (€/t)", fill="#e94560", font=font_bold)

    img.save(CHART_PNG_FILE, "PNG")
    return CHART_PNG_FILE


def generate_svg(prices, width=600, height=400):
    """Fallback SVG chart generation."""
    if not prices:
        return '<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400">' \
               '<rect width="600" height="400" fill="#1a1a2e"/>' \
               '<text x="50%" y="50%" text-anchor="middle" fill="#fff">No data</text>' \
               '</svg>'
    padding = 60
    chart_w = width - 2 * padding
    chart_h = height - 2 * padding
    all_prices = [p["price"] for p in prices]
    min_price = min(all_prices)
    max_price = max(all_prices)
    price_range = max_price - min_price if max_price != min_price else 10.0
    price_range *= 1.2
    floor_price = min_price - (price_range - (max_price - min_price)) / 2

    def scale_y(p):
        return chart_h - ((p - floor_price) / price_range) * chart_h

    points = []
    for i, p in enumerate(prices):
        x = padding + (i / max(len(prices) - 1, 1)) * chart_w
        y = padding + scale_y(p["price"])
        points.append(f"{x:.1f},{y:.1f}")

    polyline = f'<polyline points="{" ".join(points)}" fill="none" stroke="#e94560" stroke-width="2"/>'
    last_x, last_y = points[-1].split(",")
    dot = f'<circle cx="{last_x}" cy="{last_y}" r="4" fill="#e94560"/>'

    return f'<?xml version="1.0" encoding="UTF-8"?>\n' \
           f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">\n' \
           f'  <rect width="{width}" height="{height}" fill="#1a1a2e"/>\n' \
           f'  {polyline}\n' \
           f'  {dot}\n' \
           f'  <text x="{width/2}" y="25" text-anchor="middle" fill="#e94560" font-size="14" font-weight="bold">Briquette Price (€/t)</text>\n' \
           f'</svg>'


def main():
    print(f"Using data dir: {DATA_DIR}", file=sys.stderr)

    price = fetch_price()
    if price is None:
        print("FATAL: Could not fetch price, aborting.", file=sys.stderr)
        sys.exit(1)

    today = date.today().isoformat()
    prices = load_prices()

    # Robust date check — iterate ALL entries, not just the last
    today_found = any(str(e.get("date", "")).strip() == today for e in prices)

    if today_found:
        print(f"Already have data for {today}, skipping append.", file=sys.stderr)
    else:
        prices.append({"date": today, "price": price})
        save_prices(prices)
        print(f"Appended {today}: {price:.2f} €/t (total: {len(prices)} entries)", file=sys.stderr)

    chart_file = generate_png(prices)
    print(f"Chart saved to {chart_file}", file=sys.stderr)

    if len(prices) >= 2:
        prev = prices[-2]["price"]
        change = price - prev
        pct = (change / prev) * 100 if prev else 0
        print(f"{price:.2f}|{change:+.2f}|{pct:+.2f}")
    else:
        print(f"{price:.2f}|0.00|0.00")


if __name__ == "__main__":
    main()
