"""
Fetch attendees from the Astra IETM API for certificate generation.

Calls the staff-only endpoint to get all registrations with status='ATTENDED'
for a given event, then saves the data as JSON for the generator.

Usage:
    python fetch_attendees.py --event-id 1
    python fetch_attendees.py --event-id 1 --api-url https://api.astraietm.in
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import API_BASE_URL, API_TOKEN, DATA_DIR

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch")

try:
    import requests
except ImportError:
    logger.error("'requests' package not installed. Run: pip install requests")
    sys.exit(1)


def fetch_attendees(event_id, api_url=None, token=None):
    """
    Fetch attended registrations for an event from the API.

    Returns dict with:
        {
            "event": { id, title, event_date, date_str, venue, fest_name },
            "attendees": [
                { full_name, email, college, department, registration_id },
                ...
            ]
        }
    """
    base = api_url or API_BASE_URL
    auth_token = token or API_TOKEN

    url = f"{base.rstrip('/')}/api/certificates/attendees/"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    params = {"event_id": event_id}

    logger.info(f"🔍 Fetching attendees for event #{event_id} from {url}")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()

        attendees = data.get("attendees", [])
        event = data.get("event", {})

        logger.info(f"✅ Found {len(attendees)} attendees for '{event.get('title', 'Unknown')}'")
        return data

    except requests.exceptions.HTTPError as e:
        logger.error(f"API error: {e}")
        logger.error(f"Response: {e.response.text if e.response else 'No response'}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        logger.error(f"Could not connect to {base}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


def save_attendees(data, event_id):
    """Save fetched data to a JSON file in the data directory."""
    os.makedirs(DATA_DIR, exist_ok=True)
    filepath = os.path.join(DATA_DIR, f"event_{event_id}_attendees.json")

    with open(filepath, "w") as f:
        json.dump(data, f, indent=2, default=str)

    logger.info(f"💾 Saved to {filepath}")
    return filepath


def create_sample_data(event_id):
    """
    Create sample attendee data for testing (when API is not available).
    Useful for local development and dry runs.
    """
    sample = {
        "event": {
            "id": event_id,
            "title": "Cypher Decode",
            "fest_name": "ZERO DAY",
            "event_date": "2026-10-06T10:00:00+05:30",
            "date_str": "6 OCTOBER 2026",
            "venue": "Main Auditorium",
            "category": "TECHNICAL",
        },
        "attendees": [
            {
                "registration_id": 1,
                "full_name": "Jane Doe",
                "email": "jane@example.com",
                "college": "KMCT Institute of Emerging Technology and Management",
                "department": "CSE (Cyber Security)",
            },
            {
                "registration_id": 2,
                "full_name": "Rahul Menon",
                "email": "rahul@example.com",
                "college": "KMCT Institute of Emerging Technology and Management",
                "department": "CSE (Cyber Security)",
            },
            {
                "registration_id": 3,
                "full_name": "Aisha Fatima Khan",
                "email": "aisha@example.com",
                "college": "College of Engineering Trivandrum",
                "department": "Computer Science",
            },
        ],
    }

    filepath = save_attendees(sample, event_id)
    logger.info(f"🧪 Sample data created with {len(sample['attendees'])} attendees")
    return filepath


def main():
    parser = argparse.ArgumentParser(description="Fetch attendees from Astra API")
    parser.add_argument("--event-id", type=int, required=True, help="Event ID")
    parser.add_argument("--api-url", help="API base URL override")
    parser.add_argument("--token", help="API auth token override")
    parser.add_argument(
        "--sample", action="store_true",
        help="Create sample data instead of calling the API"
    )
    args = parser.parse_args()

    if args.sample:
        create_sample_data(args.event_id)
    else:
        data = fetch_attendees(args.event_id, args.api_url, args.token)
        save_attendees(data, args.event_id)


if __name__ == "__main__":
    main()
