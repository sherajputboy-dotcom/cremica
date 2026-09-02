#!/usr/bin/env python3
"""
Cremica / Firebase Ultra-Fast Direct OTP Fetcher.
Ultra-clean output: Simply input the phone number to get latest OTPs instantly.

Usage:
    python otp_fetcher.py 7208360119
    OR run: python otp_fetcher.py
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
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

DEVICE_INDEX_FILE = "device_index.json"

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
    except Exception:
        pass
    messages.sort(key=lambda x: (x["ts_val"], str(x["msg_id"])), reverse=True)
    return messages

import fcremica_core as core

def main():
    if len(sys.argv) >= 2:
        phone = sys.argv[1].strip()
    else:
        print("=" * 60)
        print("📱 ULTRA-FAST FIREBASE OTP FETCHER & NUMBER ASSIGNER")
        print("=" * 60)
        print("Options:")
        print("1. Enter specific 10-digit mobile number")
        print("2. Assign NEW UNIQUE Number (Auto-selects next available number)")
        print("=" * 60)
        choice = input("Enter choice (1/2 or Phone Number directly): ").strip()
        
        if choice == "2" or choice.lower() in ("n", "next", "new"):
            next_num = core.get_next_assigned_phone("cli")
            if not next_num:
                print("No numbers found in index.")
                return
            phone = next_num
            print(f"👉 Automatically assigned NEW UNIQUE Number: {phone}")
        elif len(choice) >= 10:
            phone = choice
        else:
            phone = input("Enter Phone Number: ").strip()

    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) > 10 and clean_phone.startswith("91"):
        clean_phone = clean_phone[2:]

    if len(clean_phone) != 10:
        print("Invalid 10-digit phone number!")
        return

    device_index = load_device_index()
    device_info = device_index.get(clean_phone)

    if not device_info:
        print(f"Phone {clean_phone} not found in index. Run 'python build_device_index.py'")
        return

    panel_url = device_info["panel_url"]
    client_id = device_info["client_id"]

    initial_msgs = fetch_direct_device_messages(panel_url, client_id)

    print(f"\n📱 TARGET NUMBER: {clean_phone}")
    print(f"📡 Panel: {panel_url} | Client ID: {client_id}")
    print(f"Latest 3 Messages:")
    print("=" * 60)

    seen_ids = set()
    if initial_msgs:
        for idx, m in enumerate(initial_msgs[:3], 1):
            seen_ids.add(m["msg_id"])
            print(f"{idx}. [🔑 OTP: {m['otp']}] | Time: {m['time']} | Sender: {m['sender']}")
            print(f"   Msg: {m['body']}")
            print("-" * 60)

    print("Listening for incoming OTPs (Press Ctrl+C for next/stop)...")

    try:
        while True:
            time.sleep(1.0)
            latest_msgs = fetch_direct_device_messages(panel_url, client_id)
            for m in latest_msgs:
                if m["msg_id"] not in seen_ids:
                    seen_ids.add(m["msg_id"])
                    print(f"\n🔥 NEW OTP RECEIVED: {m['otp']}")
                    print(f"Time: {m['time']} | Sender: {m['sender']}")
                    print(f"Msg: {m['body']}\n")
    except KeyboardInterrupt:
        print("\nStopped monitoring.")

if __name__ == "__main__":
    main()

