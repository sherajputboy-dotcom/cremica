#!/usr/bin/env python3
"""
Cremica Campaign - Registered Numbers Winner Finder & SMS Scraper.
Scans Firebase panels and checks messages for registered numbers to find winning SMS notifications.
"""

import sys
import os
import re
import json
import time
import requests
import base64
from urllib.parse import urlparse, parse_qs
from datetime import datetime

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

RESULTS_FILE = "cremica_results.txt"
PANELS_FILE = "panels.txt"
WINNERS_FILE = "cremica_winners.txt"

# Keywords for Cremica Bector Foods Promo Winners
CREMICA_KEYWORDS = [
    "bector foods", "back to school promo", "cremica", "woohoo.in/redemption", "pinelabs", "bourbonsupport"
]

def parse_firebase_link(link: str):
    if not link:
        return None
    link = link.strip()
    if not link.startswith(("http://", "https://")):
        link = "https://" + link

    parsed = urlparse(link)
    qs = parse_qs(parsed.query)
    encoded_s = qs.get("s", [None])[0]
    if encoded_s:
        try:
            encoded_clean = encoded_s + "=" * (-len(encoded_s) % 4)
            decoded = base64.b64decode(encoded_clean).decode("utf-8", errors="ignore").split("|")[0].strip()
            if "firebaseio.com" in decoded or "firebasedatabase.app" in decoded:
                if not decoded.startswith(("http://", "https://")):
                    decoded = "https://" + decoded
                return decoded.rstrip("/") + "/"
        except Exception:
            pass

    if "firebaseio.com" in link or "firebasedatabase.app" in link:
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return base_url.rstrip("/") + "/"

    return None

def extract_registered_numbers(filepath=RESULTS_FILE):
    numbers = set()
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
            found = re.findall(r"\b([6-9]\d{9})\b", content)
            numbers.update(found)
    return numbers

def fetch_panel_data(panel_url):
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    messages = {}
    try:
        url = panel_url.rstrip("/") + "/messages.json"
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            messages = resp.json() or {}
    except Exception as e:
        print(f"  [WARN] Error reading panel {panel_url}: {e}")
    return messages

def check_winners_on_panels(panel_urls, target_numbers=None):
    print(f"\n🔍 Scanning {len(panel_urls)} Firebase panel(s) for Cremica Winner SMS...")
    if target_numbers:
        print(f"📌 Checking across {len(target_numbers)} registered number(s).")
    else:
        print("📌 Checking ALL messages across panels for Cremica Winner SMS.")

    winners_found = []
    seen_signatures = set()

    for idx, panel_url in enumerate(panel_urls, 1):
        print(f"\nScanning Panel ({idx}/{len(panel_urls)}): {panel_url}")
        messages_data = fetch_panel_data(panel_url)
        if not isinstance(messages_data, dict) or not messages_data:
            print("  [WARN] No messages found or panel unreachable.")
            continue

        for client_id, device_msgs in messages_data.items():
            if not isinstance(device_msgs, dict):
                continue

            phone_found = None
            for m in device_msgs.values():
                if isinstance(m, dict):
                    text = str(m.get("body") or m.get("message") or m.get("text") or "")
                    m_phone = re.search(r"\b([6-9]\d{9})\b", text)
                    if m_phone:
                        phone_found = m_phone.group(1)
                        break

            for msg_id, mdata in device_msgs.items():
                if not isinstance(mdata, dict):
                    continue
                body = str(mdata.get("body") or mdata.get("message") or mdata.get("text") or "")
                if not body:
                    continue

                lower_body = body.lower()
                is_cremica_winner = any(kw in lower_body for kw in CREMICA_KEYWORDS)

                if is_cremica_winner:
                    msg_phone = phone_found
                    phone_match = re.search(r"\b([6-9]\d{9})\b", body)
                    if phone_match:
                        msg_phone = phone_match.group(1)

                    if target_numbers and msg_phone and msg_phone not in target_numbers:
                        continue

                    sender = str(mdata.get("sender") or mdata.get("address") or mdata.get("from") or "Unknown")
                    timestamp = "Unknown"
                    try:
                        ts = int(msg_id) / 1000
                        timestamp = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pass

                    sig = f"{msg_phone}_{timestamp}_{body[:20]}"
                    if sig in seen_signatures:
                        continue
                    seen_signatures.add(sig)

                    winners_found.append({
                        "phone": msg_phone or "Unknown",
                        "sender": sender,
                        "message": body,
                        "timestamp": timestamp,
                        "panel": panel_url
                    })

    return winners_found

def main():
    print("=" * 65)
    print("🏆 Cremica Bector Foods Promo - Winner Finder & SMS Scraper")
    print("=" * 65)

    target_numbers = extract_registered_numbers(RESULTS_FILE)
    print(f"Loaded {len(target_numbers)} registered number(s) from {RESULTS_FILE}")

    panel_urls = []
    if os.path.exists(PANELS_FILE):
        with open(PANELS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parsed = parse_firebase_link(line)
                if parsed:
                    panel_urls.append(parsed)

    if not panel_urls:
        source = input("\nEnter path to panels.txt or paste Firebase URL: ").strip()
        if os.path.exists(source):
            with open(source, "r", encoding="utf-8") as f:
                for line in f:
                    parsed = parse_firebase_link(line)
                    if parsed:
                        panel_urls.append(parsed)
        else:
            parsed = parse_firebase_link(source)
            if parsed:
                panel_urls.append(parsed)

    if not panel_urls:
        print("❌ No valid Firebase URLs provided.")
        return

    winners = check_winners_on_panels(panel_urls, target_numbers=target_numbers if target_numbers else None)

    print("\n" + "=" * 65)
    print(f"🎉 SCAN COMPLETE! Total Cremica Winners Found: {len(winners)}")
    print("=" * 65)

    if winners:
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append("                CREMICA BECTOR FOODS PROMO - WINNERS REPORT")
        report_lines.append("=" * 80)
        report_lines.append(f"Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total Winners Found: {len(winners)}\n")

        for idx, w in enumerate(winners, 1):
            line = (
                f"{idx}. Phone: {w['phone']}\n"
                f"   Sender: {w['sender']} | Time: {w['timestamp']}\n"
                f"   Message: {w['message']}\n"
                f"   Claim Link: https://cremicabacktoschool.woohoo.in/redemption\n"
                f"   Panel: {w['panel']}\n"
            )
            print(line)
            report_lines.append(line)

        with open(WINNERS_FILE, "w", encoding="utf-8") as f:
            f.write("\n".join(report_lines))

        print(f"📄 Winner details saved to: {WINNERS_FILE}")
    else:
        print("ℹ️ No Cremica winner messages found yet for registered numbers.")

if __name__ == "__main__":
    main()
