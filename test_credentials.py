#!/usr/bin/env python3
"""
Dexcom Follow Credential Tester
Tries your credentials against the OUS (Canada/international) Dexcom server
and shows exactly what happens at each step.
"""

import getpass
import json
import os
import requests

APPLICATION_ID = "d89443d2-327c-4a6f-89e5-496bbb0317db"
BASE_URL = "https://shareous1.dexcom.com/ShareWebServices/Services"


def test_login(email, password):
    url = f"{BASE_URL}/General/LoginPublisherAccountByName"
    payload = {
        "accountName": email,
        "password": password,
        "applicationId": APPLICATION_ID,
    }
    try:
        resp = requests.post(url, json=payload, timeout=10)

        if resp.status_code == 200:
            session_id = resp.json()
            if not session_id or session_id == "00000000-0000-0000-0000-000000000000":
                return False, "Login returned a null session ID — account not found or credentials incorrect"
            return True, session_id

        elif resp.status_code == 401:
            return False, "401 Unauthorized — password is wrong"

        elif resp.status_code == 403:
            return False, "403 Forbidden — account may be locked or not a Dexcom Follow account"

        elif resp.status_code == 404:
            return False, "404 Not Found — email address not registered on OUS server (try US server?)"

        else:
            try:
                body = resp.json()
            except Exception:
                body = resp.text
            return False, f"HTTP {resp.status_code}: {body}"

    except requests.exceptions.SSLError as e:
        return False, f"SSL error — {e}"
    except requests.exceptions.ConnectionError:
        return False, "Connection failed — check your internet connection"
    except requests.exceptions.Timeout:
        return False, "Request timed out after 10 seconds"
    except Exception as e:
        return False, f"Unexpected error: {e}"


FOLLOWER_ENDPOINTS = [
    "Follower/ListFollowerContacts",
    "Follower/ListFollowers",
    "Follower/GetContacts",
    "Follower/Contacts",
    "General/Contacts",
]

def test_follower_contacts(session_id):
    """Probe multiple candidate follower endpoint paths."""
    params = {"sessionId": session_id}

    for path in FOLLOWER_ENDPOINTS:
        url = f"{BASE_URL}/{path}"
        for method in ("GET", "POST"):
            try:
                if method == "GET":
                    resp = requests.get(url, params=params, timeout=10)
                else:
                    resp = requests.post(url, params=params, timeout=10)

                print(f"\n         [DEBUG] {method} {path} → {resp.status_code}: {resp.text[:200]}")

                if resp.status_code == 200:
                    return True, resp.json()
            except Exception as e:
                print(f"\n         [DEBUG] {method} {path} → exception: {e}")

    return False, "No follower contacts endpoint found — see debug output above"


def main():
    print("=" * 45)
    print("  Dexcom Follow Credential Tester")
    print("  Server: shareous1.dexcom.com (OUS/Canada)")
    print("=" * 45)
    print()
    print("Your password will not be shown as you type.")
    print("Type Ctrl+C at any time to quit.")
    print()

    attempt = 1
    while True:
        print(f"--- Attempt {attempt} ---")
        try:
            email = input("Email: ").strip()
            if not email:
                print("Email cannot be empty.\n")
                continue
            password = getpass.getpass("Password: ")
            if not password:
                print("Password cannot be empty.\n")
                continue
        except KeyboardInterrupt:
            print("\nCancelled.")
            return

        print()
        print("Step 1: Logging in ...", end=" ", flush=True)
        success, result = test_login(email, password)

        if not success:
            print("FAILED")
            print(f"         Reason: {result}")
        else:
            session_id = result
            print("OK")
            print(f"         Session: {session_id[:8]}...{session_id[-4:]}")

            print("Step 2: Fetching follower contacts ...", end=" ", flush=True)
            ok, contacts = test_follower_contacts(session_id)

            if not ok:
                print("FAILED")
                print(f"         Reason: {contacts}")
            else:
                print("OK")
                if not contacts:
                    print("         Logged in but no followed contacts found.")
                    print("         Make sure your daughter has accepted the Follow invite.")
                else:
                    print(f"         Found {len(contacts)} contact(s):")
                    for c in contacts:
                        name = f"{c.get('FirstName', '?')} {c.get('LastName', '?')}".strip()
                        cid = c.get("ContactId", "?")
                        print(f"           - {name} (ContactId: {cid})")

                print()
                print("Everything working!")
                try:
                    save = input("Save these credentials to .env for the monitor? (y/n): ").strip().lower()
                except KeyboardInterrupt:
                    print("\nNot saving.")
                    return

                if save == "y":
                    with open(".env", "w") as f:
                        f.write(f"DEXCOM_USERNAME={email}\n")
                        f.write(f"DEXCOM_PASSWORD={password}\n")
                    print("Saved to .env  (this file is gitignored and stays local)")
                    print()
                    print("You can now run:  python3 glucose_monitor.py")
                return

        print()
        try:
            again = input("Try another combination? (y/n): ").strip().lower()
        except KeyboardInterrupt:
            print("\nCancelled.")
            return

        if again != "y":
            print("Exiting.")
            return

        print()
        attempt += 1


if __name__ == "__main__":
    main()
