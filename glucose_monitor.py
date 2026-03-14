#!/usr/bin/env python3
"""
Dexcom Follow Live Glucose Monitor
Polls every 10 seconds and displays your daughter's current reading.

Setup: run test_credentials.py first to save your credentials to .env
"""

import os
import sys
import time
from datetime import datetime

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # .env values already in environment, or loaded manually

APPLICATION_ID = "d89443d2-327c-4a6f-89e5-496bbb0317db"
BASE_URL = "https://shareous1.dexcom.com/ShareWebServices/Services"
POLL_INTERVAL = 10  # seconds

TREND_ARROWS = {
    "None":             "  ?  ",
    "DoubleUp":         " ↑↑  ",
    "SingleUp":         "  ↑  ",
    "FortyFiveUp":      "  ↗  ",
    "Flat":             "  →  ",
    "FortyFiveDown":    "  ↘  ",
    "SingleDown":       "  ↓  ",
    "DoubleDown":       " ↓↓  ",
    "NotComputable":    "  ~  ",
    "RateOutOfRange":   "  ⚠  ",
}


def login(email, password):
    url = f"{BASE_URL}/General/LoginPublisherAccountByName"
    payload = {
        "accountName": email,
        "password": password,
        "applicationId": APPLICATION_ID,
    }
    resp = requests.post(url, json=payload, timeout=10)

    if resp.status_code == 401:
        raise ValueError("Wrong password or account not found (HTTP 401)")
    if resp.status_code == 404:
        raise ValueError("Account not found on OUS server — check email or try US server (HTTP 404)")
    resp.raise_for_status()

    session_id = resp.json()
    if not session_id or session_id == "00000000-0000-0000-0000-000000000000":
        raise ValueError("Login returned a null session — credentials may be incorrect")
    return session_id


def get_latest_glucose(session_id):
    url = f"{BASE_URL}/Publisher/ReadPublisherLatestGlucoseValues"
    params = {
        "sessionId": session_id,
        "minutes": 1440,
        "maxCount": 1,
    }
    resp = requests.post(url, params=params, timeout=10)

    if resp.status_code == 500:
        raise SessionExpiredError("Session expired")
    resp.raise_for_status()
    return resp.json()


class SessionExpiredError(Exception):
    pass


def ts():
    return datetime.now().strftime("%H:%M:%S")


def main():
    email = os.getenv("DEXCOM_USERNAME")
    password = os.getenv("DEXCOM_PASSWORD")

    if not email or not password:
        print("ERROR: No credentials found.")
        print("  Run python3 test_credentials.py first to save your credentials.")
        sys.exit(1)

    print("=" * 50)
    print("  Dexcom Follow — Live Glucose Monitor")
    print("  Server : shareous1.dexcom.com (OUS/Canada)")
    print(f"  Account: {email}")
    print("  Updates every 10 seconds  |  Ctrl+C to stop")
    print("=" * 50)
    print()

    # --- Initial login ---
    print("Logging in ...", end=" ", flush=True)
    try:
        session_id = login(email, password)
        print("OK")
    except ValueError as e:
        print("FAILED")
        print(f"  {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print("FAILED")
        print("  Cannot reach shareous1.dexcom.com — check your internet connection")
        sys.exit(1)
    except requests.exceptions.Timeout:
        print("FAILED")
        print("  Connection timed out")
        sys.exit(1)
    except Exception as e:
        print("FAILED")
        print(f"  Unexpected error: {e}")
        sys.exit(1)

    print()
    print(f"  {'Time':^10}  {'Glucose':^12}  {'Trend':^10}")
    print("  " + "-" * 40)

    # --- Polling loop ---
    last_value = None
    consecutive_errors = 0

    while True:
        try:
            readings = get_latest_glucose(session_id)
            consecutive_errors = 0

            if readings:
                r = readings[0]
                value = r.get("Value")
                trend = r.get("Trend", "None")
                arrow = TREND_ARROWS.get(trend, "  ?  ")

                changed = " *" if value != last_value else "  "
                last_value = value
                print(f"  [{ts()}]  {value:>5} mg/dL  {arrow}  {trend}{changed}")
            else:
                print(f"  [{ts()}]  No data returned from Dexcom")

        except SessionExpiredError:
            print(f"  [{ts()}]  Session expired — re-logging in ...", end=" ", flush=True)
            try:
                session_id = login(email, password)
                print("OK")
                consecutive_errors = 0
            except Exception as e:
                print(f"FAILED: {e}")
                consecutive_errors += 1

        except requests.exceptions.ConnectionError:
            consecutive_errors += 1
            print(f"  [{ts()}]  Connection lost (attempt {consecutive_errors}) — retrying in 10s")

        except requests.exceptions.Timeout:
            consecutive_errors += 1
            print(f"  [{ts()}]  Request timed out (attempt {consecutive_errors}) — retrying in 10s")

        except requests.exceptions.HTTPError as e:
            consecutive_errors += 1
            print(f"  [{ts()}]  HTTP error: {e}")

        except KeyboardInterrupt:
            print()
            print("Stopped.")
            break

        except Exception as e:
            consecutive_errors += 1
            print(f"  [{ts()}]  Unexpected error: {e}")

        if consecutive_errors >= 10:
            print(f"  [{ts()}]  10 consecutive errors — giving up. Check your connection and re-run.")
            break

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
