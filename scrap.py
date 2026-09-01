#!/usr/bin/env python3
"""
Cremica Campaign - Today's Winner Finder & SMS Scraper.
Scans Firebase panels concurrently and checks for TODAY'S winner SMS notifications.
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
from concurrent.futures import ThreadPoolExecutor, as_completed

# Fix Windows console UTF-8 output encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

RESULTS_FILE = "cremica_results.txt"
PANELS_FILE = "panels.txt"
WINNERS_FILE = "cremica_todays_winners.txt"

# Keywords for Cremica Bector Foods Promo Winners
CREMICA_KEYWORDS = [
    "bector foods", "back to school promo", "cremica", "woohoo.in/redemption", "pinelabs", "bourbonsupport"
]

TODAY_DATE_STR = datetime.now().strftime("%Y-%m-%d")

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
        resp = requests.get(url, headers=headers, timeout=8)
        if resp.status_code == 200:
            messages = resp.json() or {}
    except Exception as e:
        pass
    return panel_url, messages

def scan_single_panel(panel_url, target_numbers=None, filter_today=True):
    panel_url, messages_data = fetch_panel_data(panel_url)
    if not isinstance(messages_data, dict) or not messages_data:
        return []

    winners_found = []
    seen_signatures = set()

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
                timestamp_str = "Unknown"
                date_str = ""
                try:
                    ts = int(msg_id) / 1000
                    dt = datetime.fromtimestamp(ts)
                    timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
                    date_str = dt.strftime("%Y-%m-%d")
                except Exception:
                    pass

                # Filter ONLY FOR TODAY'S DATE if filter_today is enabled
                if filter_today and date_str and date_str != TODAY_DATE_STR:
                    continue

                sig = f"{msg_phone}_{timestamp_str}_{body[:20]}"
                if sig in seen_signatures:
                    continue
                seen_signatures.add(sig)

                winners_found.append({
                    "phone": msg_phone or "Unknown",
                    "sender": sender,
                    "message": body,
                    "timestamp": timestamp_str,
                    "date": date_str,
                    "panel": panel_url
                })

    return winners_found

def check_all_panels_parallel(panel_urls, target_numbers=None, filter_today=True, max_workers=20):
    print(f"\n🔄 Parallel Scanning {len(panel_urls)} Firebase panel(s) with {max_workers} worker(s)...")
    print(f"📅 Filter Mode: ONLY TODAY'S DATE ({TODAY_DATE_STR})")
    if target_numbers:
        print(f"📌 Target Filter: {len(target_numbers)} registered number(s) from {RESULTS_FILE}")
    else:
        print("📌 Target Filter: Scanning all phone numbers across panels.")

    all_winners = []
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(scan_single_panel, url, target_numbers, filter_today): url
            for url in panel_urls
        }

        for future in as_completed(future_to_url):
            completed += 1
            url = future_to_url[future]
            try:
                w_list = future.result()
                if w_list:
                    print(f"  [{completed}/{len(panel_urls)}] 🎉 Found {len(w_list)} winner message(s) on: {url}")
                    all_winners.extend(w_list)
                else:
                    print(f"  [{completed}/{len(panel_urls)}] Checked: {url[:55]}...")
            except Exception as e:
                print(f"  [{completed}/{len(panel_urls)}] [WARN] {url[:40]}: {e}")

    return all_winners

def main():
    print("=" * 70)
    print(f"🏆 Cremica Bector Foods Promo - TODAY'S Winner Finder ({TODAY_DATE_STR})")
    print("=" * 70)

    target_numbers = extract_registered_numbers(RESULTS_FILE)
    if target_numbers:
        print(f"Loaded {len(target_numbers)} registered number(s) from {RESULTS_FILE}")
    else:
        print("No cremica_results.txt found, checking all panel numbers.")

    panel_urls = []
    if os.path.exists(PANELS_FILE):
        with open(PANELS_FILE, "r", encoding="utf-8") as f:
            for line in f:
                parsed = parse_firebase_link(line)
                if parsed:
                    panel_urls.append(parsed)

    if not panel_urls:
        print("❌ No valid Firebase URLs found in panels.txt.")
        return

    winners = check_all_panels_parallel(panel_urls, target_numbers=target_numbers if target_numbers else None, filter_today=True)

    print("\n" + "=" * 70)
    print(f"🎉 SCAN COMPLETE! Total TODAY's ({TODAY_DATE_STR}) Cremica Winners: {len(winners)}")
    print("=" * 70)

    if winners:
        report_lines = []
        report_lines.append("=" * 80)
        report_lines.append(f"          CREMICA BECTOR FOODS PROMO - TODAY'S WINNERS ({TODAY_DATE_STR})")
        report_lines.append("=" * 80)
        report_lines.append(f"Scan Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"Total Winners Found Today: {len(winners)}\n")

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

        print(f"📄 Today's winner details saved to: {WINNERS_FILE}")
    else:
        print(f"ℹ️ No Cremica winner messages found for TODAY ({TODAY_DATE_STR}). Check back later after winner announcements!")

if __name__ == "__main__":
    main()
