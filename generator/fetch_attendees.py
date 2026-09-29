"""
Fetch attended participants from the Astra Supabase database.

Database relationships used by the certificate pipeline:

    events_registration
        ├── user_id  -> authentication_user.id
        └── event_id -> events_event.id

The certificate data is built from:
    authentication_user.full_name  -> participant name
    authentication_user.email      -> recipient email
    events_registration.college    -> college entered during registration
    events_event.title             -> event title
    events_registration.status     -> attendance status

Only registrations whose status matches ATTENDED_STATUSES are included.

Output:
    data/event_<event-id>_attendees.json
    data/all_events_attendees.json

The rest of the certificate pipeline already consumes this format.

Examples:
    python fetch_attendees.py
    python fetch_attendees.py --event-id 12
    python fetch_attendees.py --title "Cypher Decode"
    python fetch_attendees.py --sample
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    DATA_DIR,
    EVENT_DATE_STR,
    FEST_NAME,
    SUPABASE_KEY,
    SUPABASE_URL,
    safe_id,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch")

# ---------------------------------------------------------------------------
# Actual Django/Postgres table names from the Astra database
# ---------------------------------------------------------------------------

USERS_TABLE = "authentication_user"
USER_ID_COL = "id"
USER_EMAIL_COL = "email"
USER_NAME_COL = "full_name"

REGISTRATIONS_TABLE = "events_registration"
REG_ID_COL = "id"
REG_USER_ID_COL = "user_id"
REG_EVENT_ID_COL = "event_id"
REG_COLLEGE_COL = "college"
REG_STATUS_COL = "status"
REG_ATTENDED_COL = "is_used"

PARTICIPANTS_TABLE = "events_registrationparticipant"
PARTICIPANT_ID_COL = "id"
PARTICIPANT_REG_ID_COL = "registration_id"
PARTICIPANT_NAME_COL = "name"
PARTICIPANT_EMAIL_COL = "email"
PARTICIPANT_LEADER_COL = "is_leader"

EVENTS_TABLE = "events_event"
EVENT_ID_COL = "id"
EVENT_TITLE_COL = "title"
EVENT_DATE_COL = "event_date"

# Attendance is recorded by changing events_registration.status from
# REGISTERED to ATTENDED.
ATTENDED_STATUSES = {
    value.strip().lower()
    for value in os.environ.get("ATTENDED_STATUSES", "ATTENDED").split(",")
    if value.strip()
}

# Supabase returns at most 1,000 rows by default, so fetch in pages.
PAGE_SIZE = 500
ID_BATCH_SIZE = 500


# ---------------------------------------------------------------------------
# Supabase
# ---------------------------------------------------------------------------

def get_client(supabase_url=None, supabase_key=None):
    url = supabase_url or SUPABASE_URL
    key = supabase_key or SUPABASE_KEY

    if not url or not key:
        logger.error("SUPABASE_URL / SUPABASE_KEY are not set.")
        sys.exit(1)

    try:
        from supabase import create_client
    except ImportError:
        logger.error("'supabase' package not installed. Run: pip install supabase")
        sys.exit(1)

    return create_client(url, key)


def fetch_all_rows(client, table, columns="*", filters=None):
    """
    Fetch a table in pages.

    Supabase's Data API defaults to a maximum of 1,000 returned rows, so using
    range() pagination prevents large event datasets from being truncated.
    """
    rows = []
    start = 0

    while True:
        query = client.table(table).select(columns)

        for column, value in (filters or {}).items():
            if isinstance(value, tuple) and value[0] == "in":
                query = query.in_(column, value[1])
            else:
                query = query.eq(column, value)

        response = (
            query
            .order("id")
            .range(start, start + PAGE_SIZE - 1)
            .execute()
        )

        page = response.data or []
        rows.extend(page)

        if len(page) < PAGE_SIZE:
            break

        start += PAGE_SIZE

    return rows


def fetch_rows_by_ids(client, table, columns, column, ids):
    """Fetch rows in safe-sized batches for IN queries."""
    ids = [value for value in dict.fromkeys(ids) if value is not None]
    if not ids:
        return []

    rows = []
    for start in range(0, len(ids), ID_BATCH_SIZE):
        batch = ids[start:start + ID_BATCH_SIZE]
        response = (
            client.table(table)
            .select(columns)
            .in_(column, batch)
            .execute()
        )
        rows.extend(response.data or [])

    return rows


# ---------------------------------------------------------------------------
# Database loading
# ---------------------------------------------------------------------------

def fetch_attended_registrations(client, event_id=None):
    """
    Fetch registrations that represent attendance.

    event_id is optional. If supplied, only registrations for that event
    are considered.
    """
    # Attendance is recorded by changing status from REGISTERED to ATTENDED.
    # Use the configured values in the query, then normalize again in Python.
    status_values = sorted({
        value.upper()
        for value in ATTENDED_STATUSES
    })
    filters = {
        REG_STATUS_COL: ("in", status_values),
    }

    if event_id is not None:
        filters[REG_EVENT_ID_COL] = event_id

    rows = fetch_all_rows(
        client,
        REGISTRATIONS_TABLE,
        columns=(
            f"{REG_ID_COL},"
            f"{REG_USER_ID_COL},"
            f"{REG_EVENT_ID_COL},"
            f"{REG_COLLEGE_COL},"
            f"{REG_STATUS_COL},"
            "certificate_sent,"
            "certificate_sent_at"
        ),
        filters=filters,
    )

    # Normalize status in Python so ATTENDED/Attended/attended are equivalent.
    rows = [
        row
        for row in rows
        if str(row.get(REG_STATUS_COL, "")).strip().lower() in ATTENDED_STATUSES
    ]

    return rows


def fetch_users(client, user_ids):
    rows = fetch_rows_by_ids(
        client,
        USERS_TABLE,
        f"{USER_ID_COL},{USER_EMAIL_COL},{USER_NAME_COL},first_name,last_name",
        USER_ID_COL,
        user_ids,
    )

    return {
        row.get(USER_ID_COL): row
        for row in rows
        if row.get(USER_ID_COL) is not None
    }


def fetch_events(client, event_ids):
    rows = fetch_rows_by_ids(
        client,
        EVENTS_TABLE,
        f"{EVENT_ID_COL},{EVENT_TITLE_COL},{EVENT_DATE_COL}",
        EVENT_ID_COL,
        event_ids,
    )

    return {
        row.get(EVENT_ID_COL): row
        for row in rows
        if row.get(EVENT_ID_COL) is not None
    }

def fetch_participants(client, registration_ids):
    return {
        row.get(PARTICIPANT_REG_ID_COL): row
        for row in fetch_rows_by_ids(
            client,
            PARTICIPANTS_TABLE,
            f"{PARTICIPANT_ID_COL},{PARTICIPANT_REG_ID_COL},{PARTICIPANT_NAME_COL},{PARTICIPANT_EMAIL_COL},{PARTICIPANT_LEADER_COL},certificate_sent,certificate_sent_at",
            PARTICIPANT_REG_ID_COL,
            registration_ids,
        )
        if row.get(PARTICIPANT_REG_ID_COL) is not None
    }


# ---------------------------------------------------------------------------
# Transformation
# ---------------------------------------------------------------------------

def format_event_date(event_date):
    """Convert the DB timestamp to the certificate's display date."""
    if not event_date:
        return EVENT_DATE_STR or ""

    try:
        value = str(event_date).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(value)
        return parsed.strftime("%-d %B %Y").upper()
    except (ValueError, TypeError):
        # GitHub Ubuntu supports %-d. Fall back for portability.
        try:
            parsed = datetime.fromisoformat(str(event_date).replace("Z", "+00:00"))
            return parsed.strftime("%d %B %Y").lstrip("0").upper()
        except (ValueError, TypeError):
            return EVENT_DATE_STR or str(event_date)


def get_user_name(user):
    name = (user.get(USER_NAME_COL) or "").strip()
    if name:
        return name

    first = (user.get("first_name") or "").strip()
    last = (user.get("last_name") or "").strip()
    return " ".join(part for part in (first, last) if part) or "Participant"


def build_event_batches(registrations, users_by_id, events_by_id, participants_by_registration):
    """
    Convert DB rows into the JSON structure expected by generate.py.

    Registrations are grouped by event_id, not by title, so two distinct
    database events with the same title do not get accidentally merged.
    """
    batches = {}

    for registration in registrations:
        registration_id = registration.get(REG_ID_COL)
        user_id = registration.get(REG_USER_ID_COL)
        event_id = registration.get(REG_EVENT_ID_COL)

        user = users_by_id.get(user_id, {})
        event = events_by_id.get(event_id, {})

        title = (event.get(EVENT_TITLE_COL) or "Untitled Event").strip()

        batch = batches.setdefault(
            event_id,
            {
                "event": {
                    "id": str(event_id),
                    "title": title,
                    "fest_name": FEST_NAME,
                    "date_str": format_event_date(event.get(EVENT_DATE_COL)),
                    "event_date": event.get(EVENT_DATE_COL, ""),
                },
                "attendees": [],
            },
        )

        participant_rows = participants_by_registration.get(registration_id, [])
        if participant_rows:
            for participant in participant_rows:
                batch["attendees"].append(
                    {
                        "participant_id": participant.get(PARTICIPANT_ID_COL),
                        "registration_id": registration_id,
                        "certificate_sent": bool(participant.get("certificate_sent", False)),
                        "certificate_sent_at": participant.get("certificate_sent_at"),
                        "full_name": (participant.get(PARTICIPANT_NAME_COL) or "Participant").strip(),
                        "email": (participant.get(PARTICIPANT_EMAIL_COL) or "").strip(),
                        "college": (registration.get(REG_COLLEGE_COL) or "").strip(),
                    }
                )
        else:
            # Backward compatibility for registrations created before the
            # participant table existed.
            batch["attendees"].append(
                {
                    "participant_id": None,
                    "registration_id": registration_id,
                    "certificate_sent": bool(registration.get("certificate_sent", False)),
                    "certificate_sent_at": registration.get("certificate_sent_at"),
                    "full_name": get_user_name(user),
                    "email": (user.get(USER_EMAIL_COL) or "").strip(),
                    "college": (registration.get(REG_COLLEGE_COL) or "").strip(),
                }
            )

    result = list(batches.values())

    # Stable ordering makes certificate generation reproducible.
    result.sort(key=lambda batch: (batch["event"]["title"].lower(), batch["event"]["id"]))

    for batch in result:
        batch["count"] = len(batch["attendees"])

    return result


def fetch_all(event_id=None, title=None, supabase_url=None, supabase_key=None):
    """
    Fetch attended participants and join:
        registration -> user -> event

    If title is provided, filtering happens after loading event metadata.
    """
    client = get_client(supabase_url, supabase_key)

    logger.info("🔍 Fetching attended registrations from Supabase")
    logger.info("   Tables: %s, %s, %s", REGISTRATIONS_TABLE, USERS_TABLE, EVENTS_TABLE)
    logger.info(
        "   Attendance source: events_registration.status in %s",
        ", ".join(sorted(ATTENDED_STATUSES)),
    )

    registrations = fetch_attended_registrations(client, event_id=event_id)

    if not registrations:
        logger.warning("No attended registrations found.")
        return []

    user_ids = [row.get(REG_USER_ID_COL) for row in registrations]
    event_ids = [row.get(REG_EVENT_ID_COL) for row in registrations]

    users_by_id = fetch_users(client, user_ids)
    events_by_id = fetch_events(client, event_ids)

    if title:
        wanted = title.strip().casefold()
        registrations = [
            row
            for row in registrations
            if (
                events_by_id.get(row.get(REG_EVENT_ID_COL), {})
                .get(EVENT_TITLE_COL, "")
                .strip()
                .casefold()
                == wanted
            )
        ]

    participants_by_registration = fetch_participants(client, [row.get(REG_ID_COL) for row in registrations])
    participants_grouped = {}
    for participant in participants_by_registration.values():
        participants_grouped.setdefault(participant.get(PARTICIPANT_REG_ID_COL), []).append(participant)

    batches = build_event_batches(registrations, users_by_id, events_by_id, participants_grouped)

    for batch in batches:
        event = batch["event"]
        logger.info(
            "✅ %s | event_id=%s | %d attendee(s)",
            event["title"],
            event["id"],
            batch["count"],
        )

    return batches


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------

def save_batch(batch):
    os.makedirs(DATA_DIR, exist_ok=True)

    event_id = safe_id(str(batch["event"]["id"]))
    path = os.path.join(DATA_DIR, f"event_{event_id}_attendees.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(batch, f, indent=2, ensure_ascii=False, default=str)

    logger.info("💾 Saved %s", path)
    return path


def save_all(batches):
    os.makedirs(DATA_DIR, exist_ok=True)

    paths = [save_batch(batch) for batch in batches]

    summary_path = os.path.join(DATA_DIR, "all_events_attendees.json")
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(batches, f, indent=2, ensure_ascii=False, default=str)

    logger.info("💾 Saved %s", summary_path)
    return paths, summary_path


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

def create_sample_data(title=None):
    sample_batches = [
        {
            "event": {
                "id": "1",
                "title": "CYPHER DECODE",
                "fest_name": FEST_NAME,
                "date_str": "6 OCTOBER 2026",
                "event_date": "2026-10-06T00:00:00+00:00",
            },
            "attendees": [
                {
                    "registration_id": 1,
                    "full_name": "Jane Doe",
                    "email": "jane@example.com",
                    "college": "KMCT Institute of Emerging Technology and Management",
                },
                {
                    "registration_id": 2,
                    "full_name": "Rahul Menon",
                    "email": "rahul@example.com",
                    "college": "College of Engineering Trivandrum",
                },
            ],
        },
        {
            "event": {
                "id": "2",
                "title": "CODE BREACH",
                "fest_name": FEST_NAME,
                "date_str": "6 OCTOBER 2026",
                "event_date": "2026-10-06T00:00:00+00:00",
            },
            "attendees": [
                {
                    "registration_id": 3,
                    "full_name": "Sneha Prakash",
                    "email": "sneha@example.com",
                    "college": "NIT Calicut",
                }
            ],
        },
    ]

    if title:
        wanted = title.strip().casefold()
        sample_batches = [
            batch for batch in sample_batches
            if batch["event"]["title"].casefold() == wanted
        ]

    for batch in sample_batches:
        batch["count"] = len(batch["attendees"])

    save_all(sample_batches)

    total = sum(batch["count"] for batch in sample_batches)
    logger.info(
        "🧪 Sample data created: %d event(s), %d attendee(s)",
        len(sample_batches),
        total,
    )

    return sample_batches


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Fetch attended event participants from Supabase."
    )

    parser.add_argument(
        "--event-id",
        type=int,
        help="Only fetch attendees for this events_event.id",
    )
    parser.add_argument(
        "--title",
        help="Only fetch attendees for an exact event title",
    )
    parser.add_argument(
        "--all-events",
        action="store_true",
        help="Explicitly fetch attendees for every event",
    )
    parser.add_argument("--supabase-url", help="Supabase URL override")
    parser.add_argument("--supabase-key", help="Supabase key override")
    parser.add_argument(
        "--sample",
        action="store_true",
        help="Generate local sample data without contacting Supabase",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Use sample data only when the DB returns no attendees",
    )

    args = parser.parse_args()

    if args.event_id is not None and args.title:
        parser.error("--event-id and --title cannot be used together")

    if args.sample:
        create_sample_data(args.title)
        return

    try:
        batches = fetch_all(
            event_id=args.event_id,
            title=args.title,
            supabase_url=args.supabase_url,
            supabase_key=args.supabase_key,
        )
    except Exception as exc:
        logger.exception("❌ Database fetch failed: %s", exc)
        if args.dry_run:
            logger.warning("🧪 --dry-run enabled, using sample data instead.")
            create_sample_data(args.title)
            return
        sys.exit(1)

    if batches:
        save_all(batches)
        return

    if args.dry_run:
        logger.warning("🧪 No attended participants found, using sample data.")
        create_sample_data(args.title)
        return

    scope = (
        f"event id {args.event_id}"
        if args.event_id is not None
        else f"title '{args.title}'"
        if args.title
        else "all events"
    )

    logger.error(
        "❌ No attended participants found for %s. "
        "Check events_registration.status and the Supabase credentials.",
        scope,
    )
    sys.exit(1)


if __name__ == "__main__":
    main()
