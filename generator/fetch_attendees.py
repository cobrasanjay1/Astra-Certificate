"""
Fetch attendees directly from Supabase DB (or API) for certificate generation.

Fetches event details and all registrations with status='ATTENDED' directly
from the Supabase PostgreSQL database tables:
  - events_event
  - events_registration
  - authentication_user

Usage:
    python fetch_attendees.py --event-id 1
    python fetch_attendees.py --event-id 1 --sample
"""

import os
import sys
import json
import argparse
import logging
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (
    SUPABASE_URL, SUPABASE_KEY, DATABASE_URL,
    API_BASE_URL, API_TOKEN, DATA_DIR,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch")


def format_date_str(date_val):
    """Format datetime object or ISO string to uppercase date string (e.g. '6 OCTOBER 2026')."""
    if not date_val:
        return ""
    if isinstance(date_val, str):
        try:
            # Handle ISO format
            dt = datetime.fromisoformat(date_val.replace("Z", "+00:00"))
        except ValueError:
            return date_val
    elif isinstance(date_val, (datetime,)):
        dt = date_val
    else:
        return str(date_val)

    return f"{dt.day} {dt.strftime('%B').upper()} {dt.year}"


def fetch_from_supabase(event_id, supabase_url=None, supabase_key=None):
    """
    Fetch attendee and event data directly using Supabase client.
    Queries tables: events_event, events_registration, authentication_user
    """
    url = supabase_url or SUPABASE_URL
    key = supabase_key or SUPABASE_KEY

    if not url or not key:
        return None

    try:
        from supabase import create_client
    except ImportError:
        logger.warning("'supabase' package not installed. Run: pip install supabase")
        return None

    logger.info(f"⚡ Fetching directly from Supabase DB ({url}) for event #{event_id}")

    try:
        supabase = create_client(url, key)

        # 1. Fetch event
        event_resp = (
            supabase.table("events_event")
            .select("*")
            .eq("id", event_id)
            .execute()
        )
        if not event_resp.data:
            logger.error(f"Event #{event_id} not found in Supabase table 'events_event'")
            sys.exit(1)

        raw_event = event_resp.data[0]
        event_date_raw = raw_event.get("event_date", "")

        event = {
            "id": raw_event.get("id"),
            "title": raw_event.get("title", "Event"),
            "fest_name": raw_event.get("fest_name", "ZERO DAY"),
            "event_date": str(event_date_raw) if event_date_raw else "",
            "date_str": format_date_str(event_date_raw),
            "venue": raw_event.get("venue", ""),
            "category": raw_event.get("category", ""),
        }

        # 2. Fetch registrations with status='ATTENDED'
        reg_resp = (
            supabase.table("events_registration")
            .select("*")
            .eq("event_id", event_id)
            .eq("status", "ATTENDED")
            .execute()
        )
        registrations = reg_resp.data or []

        if not registrations:
            logger.warning(f"No registrations found with status='ATTENDED' for event #{event_id}")
            return {"event": event, "attendees": [], "count": 0}

        # 3. Fetch user details for each attendee
        user_ids = [r["user_id"] for r in registrations if "user_id" in r]
        users_by_id = {}
        if user_ids:
            user_resp = (
                supabase.table("authentication_user")
                .select("*")
                .in_("id", user_ids)
                .execute()
            )
            for u in (user_resp.data or []):
                users_by_id[u["id"]] = u

        # 4. Assemble attendees list
        attendees = []
        for reg in registrations:
            user = users_by_id.get(reg.get("user_id"), {})
            full_name = user.get("full_name") or user.get("email") or "Participant"
            email = user.get("email", "")
            college = reg.get("college") or user.get("college") or ""
            department = reg.get("department") or user.get("department") or ""

            attendees.append({
                "registration_id": reg.get("id"),
                "full_name": full_name,
                "email": email,
                "college": college,
                "department": department,
            })

        logger.info(f"✅ Successfully fetched {len(attendees)} attendees from Supabase DB")
        return {
            "event": event,
            "attendees": attendees,
            "count": len(attendees),
        }

    except Exception as e:
        logger.error(f"Error fetching from Supabase: {e}")
        return None


def fetch_from_postgres(event_id, db_url=None):
    """
    Fetch attendee and event data using direct PostgreSQL / SQLite connection.
    """
    url = db_url or DATABASE_URL
    if not url:
        return None

    logger.info(f"🔌 Connecting to database to fetch event #{event_id}")

    try:
        if url.startswith("sqlite"):
            import sqlite3
            conn = sqlite3.connect(url.replace("sqlite:///", ""))
            conn.row_factory = sqlite3.Row
            param = "?"
        else:
            import psycopg2
            import psycopg2.extras
            conn = psycopg2.connect(url)
            param = "%s"

        cursor = conn.cursor()

        # Fetch Event
        cursor.execute(f"SELECT id, title, event_date, venue, category FROM events_event WHERE id = {param}", (event_id,))
        row = cursor.fetchone()
        if not row:
            logger.error(f"Event #{event_id} not found in database")
            sys.exit(1)

        if isinstance(row, dict) or hasattr(row, "keys"):
            event_id_val, title, event_date, venue, category = row["id"], row["title"], row["event_date"], row["venue"], row["category"]
        else:
            event_id_val, title, event_date, venue, category = row

        event = {
            "id": event_id_val,
            "title": title,
            "fest_name": "ZERO DAY",
            "event_date": str(event_date) if event_date else "",
            "date_str": format_date_str(event_date),
            "venue": venue or "",
            "category": category or "",
        }

        # Fetch Registrations + User Info
        query = f"""
            SELECT 
                r.id as registration_id,
                u.email,
                u.full_name,
                COALESCE(NULLIF(r.college, ''), u.college, '') as college,
                COALESCE(NULLIF(r.department, ''), u.department, '') as department
            FROM events_registration r
            JOIN authentication_user u ON r.user_id = u.id
            WHERE r.event_id = {param} AND r.status = 'ATTENDED'
        """
        cursor.execute(query, (event_id,))
        rows = cursor.fetchall()

        attendees = []
        for r in rows:
            if isinstance(r, dict) or hasattr(r, "keys"):
                reg_id, email, full_name, college, department = r["registration_id"], r["email"], r["full_name"], r["college"], r["department"]
            else:
                reg_id, email, full_name, college, department = r

            attendees.append({
                "registration_id": reg_id,
                "full_name": full_name or email,
                "email": email,
                "college": college or "",
                "department": department or "",
            })

        conn.close()
        logger.info(f"✅ Successfully fetched {len(attendees)} attendees via Direct SQL")
        return {
            "event": event,
            "attendees": attendees,
            "count": len(attendees),
        }

    except Exception as e:
        logger.error(f"Error querying database: {e}")
        return None


def fetch_from_api(event_id, api_url=None, token=None):
    """
    Fallback HTTP API fetcher for backward compatibility.
    """
    base = api_url or API_BASE_URL
    auth_token = token or API_TOKEN

    if not auth_token:
        return None

    try:
        import requests
    except ImportError:
        return None

    url = f"{base.rstrip('/')}/api/certificates/attendees/"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
    }
    params = {"event_id": event_id}

    logger.info(f"🔍 [Fallback] Fetching attendees for event #{event_id} from API {url}")

    try:
        response = requests.get(url, headers=headers, params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        logger.info(f"✅ Found {len(data.get('attendees', []))} attendees via API")
        return data
    except Exception as e:
        logger.error(f"API fetch failed: {e}")
        return None


def fetch_attendees(event_id, supabase_url=None, supabase_key=None, db_url=None, api_url=None, token=None):
    """
    Main fetch entrypoint with multi-source fallback hierarchy:
    1. Supabase Client SDK
    2. Direct Postgres SQL Connection
    3. HTTP API
    """
    # Try Supabase Client SDK first
    data = fetch_from_supabase(event_id, supabase_url, supabase_key)
    if data is not None:
        return data

    # Try Direct Postgres DB Connection
    data = fetch_from_postgres(event_id, db_url)
    if data is not None:
        return data

    # Try Legacy HTTP API
    data = fetch_from_api(event_id, api_url, token)
    if data is not None:
        return data

    logger.error(
        "❌ Unable to fetch attendees!\n"
        "Please provide one of the following environment variables:\n"
        "  - SUPABASE_URL and SUPABASE_KEY\n"
        "  - DATABASE_URL / SUPABASE_DB_URL\n"
        "  - API_BASE_URL and API_TOKEN\n"
        "Or use --sample to generate test data locally."
    )
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
    Create sample attendee data for local testing.
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
    parser = argparse.ArgumentParser(description="Fetch attendees from Supabase DB")
    parser.add_argument("--event-id", type=int, required=True, help="Event ID")
    parser.add_argument("--supabase-url", help="Supabase URL override")
    parser.add_argument("--supabase-key", help="Supabase API key override")
    parser.add_argument("--db-url", help="Database URL override")
    parser.add_argument("--api-url", help="API base URL override")
    parser.add_argument("--token", help="API auth token override")
    parser.add_argument(
        "--sample", action="store_true",
        help="Create sample data instead of fetching from DB"
    )
    args = parser.parse_args()

    if args.sample:
        create_sample_data(args.event_id)
    else:
        data = fetch_attendees(
            args.event_id,
            supabase_url=args.supabase_url,
            supabase_key=args.supabase_key,
            db_url=args.db_url,
            api_url=args.api_url,
            token=args.token,
        )
        save_attendees(data, args.event_id)


if __name__ == "__main__":
    main()
