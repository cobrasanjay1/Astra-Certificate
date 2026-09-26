"""
Fetch attendees from Supabase for certificate generation.

Reads two tables:

  1. PROFILES_TABLE       — one row per authenticated user: id, email.
  2. REGISTRATIONS_TABLE  — one row per event registration. Holds the three
     fields that are asked at registration time and vary per participant
     (name, college, event title), plus an "attended" flag set after the
     event happens.

Only registrations where REG_ATTENDED_COL == REG_ATTENDED_VALUE are turned
into certificates. Registrations are grouped by event title, so each
distinct title becomes its own certificate batch — the same JSON shape
generate.py / build_site.py / send_emails.py already expect:

    {
      "event": {"id": "<title, filename-safe>", "title": "<title>", ...},
      "attendees": [{"registration_id", "full_name", "email", "college"}, ...],
      "count": <int>
    }

⚠️  ADJUST THE SCHEMA CONSTANTS BELOW to match your actual Supabase table
    and column names — everything else in this file works off them.

Usage:
    python fetch_attendees.py                    # every event with attendees
    python fetch_attendees.py --title "Cypher Decode"
    python fetch_attendees.py --sample            # local test data, no network call
    python fetch_attendees.py --dry-run           # fall back to sample data if the DB is empty/unreachable
"""

import os
import sys
import json
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import SUPABASE_URL, SUPABASE_KEY, DATA_DIR, FEST_NAME, EVENT_DATE_STR, safe_id

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger("fetch")

# ── Schema ───────────────────────────────────────────────────────────────
# Rename these to match your real Supabase tables/columns — nothing else
# in this file needs to change.
PROFILES_TABLE = "profiles"            # id, email (mirrors auth.users)
PROFILES_ID_COL = "id"
PROFILES_EMAIL_COL = "email"

REGISTRATIONS_TABLE = "event_registrations"
REG_ID_COL = "id"
REG_USER_ID_COL = "user_id"            # FK -> PROFILES_TABLE.id
REG_NAME_COL = "name"
REG_COLLEGE_COL = "college"
REG_TITLE_COL = "event_title"
REG_ATTENDED_COL = "attended"
REG_ATTENDED_VALUE = True              # change to e.g. "ATTENDED" if it's a status string, not a boolean


# ── Supabase access ────────────────────────────────────────────────────────

def get_client(supabase_url=None, supabase_key=None):
    """Create a Supabase client, or exit with a clear error."""
    url = supabase_url or SUPABASE_URL
    key = supabase_key or SUPABASE_KEY
    if not url or not key:
        logger.error(
            "SUPABASE_URL / SUPABASE_KEY are not set "
            "(env vars, or --supabase-url/--supabase-key)."
        )
        sys.exit(1)
    try:
        from supabase import create_client
    except ImportError:
        logger.error("'supabase' package not installed. Run: pip install supabase")
        sys.exit(1)
    return create_client(url, key)


def fetch_attended_registrations(client, title=None):
    """Return every registration row marked attended, optionally filtered to one event title."""
    query = (
        client.table(REGISTRATIONS_TABLE)
        .select("*")
        .eq(REG_ATTENDED_COL, REG_ATTENDED_VALUE)
    )
    if title:
        query = query.eq(REG_TITLE_COL, title)
    resp = query.execute()
    return resp.data or []


def fetch_emails_by_user_id(client, user_ids):
    """Look up {user_id: email} for a set of user ids from the profiles table."""
    user_ids = list({uid for uid in user_ids if uid})
    if not user_ids:
        return {}
    resp = (
        client.table(PROFILES_TABLE)
        .select(f"{PROFILES_ID_COL},{PROFILES_EMAIL_COL}")
        .in_(PROFILES_ID_COL, user_ids)
        .execute()
    )
    return {row[PROFILES_ID_COL]: row.get(PROFILES_EMAIL_COL, "") for row in (resp.data or [])}


def build_event_batches(registrations, emails_by_user_id):
    """Group attended registrations by event title into the pipeline's JSON shape."""
    batches = {}
    for reg in registrations:
        title = (reg.get(REG_TITLE_COL) or "Untitled Event").strip()
        batch = batches.setdefault(title, {
            "event": {
                "id": safe_id(title),
                "title": title,
                "fest_name": FEST_NAME,
                "date_str": EVENT_DATE_STR,
            },
            "attendees": [],
        })
        batch["attendees"].append({
            "registration_id": reg.get(REG_ID_COL),
            "full_name": reg.get(REG_NAME_COL) or "Participant",
            "email": emails_by_user_id.get(reg.get(REG_USER_ID_COL), ""),
            "college": reg.get(REG_COLLEGE_COL) or "",
        })

    result = list(batches.values())
    for batch in result:
        batch["count"] = len(batch["attendees"])
    return result


def fetch_all(title=None, supabase_url=None, supabase_key=None):
    """Main entrypoint: fetch attended registrations, join emails, group by event title."""
    client = get_client(supabase_url, supabase_key)
    logger.info(
        "⚡ Fetching attended registrations from Supabase"
        + (f" for '{title}'" if title else " (all events)")
    )

    registrations = fetch_attended_registrations(client, title=title)
    if not registrations:
        logger.warning(
            "No registrations found with "
            f"{REG_ATTENDED_COL}={REG_ATTENDED_VALUE!r}"
            + (f" for '{title}'" if title else "")
        )
        return []

    user_ids = [r.get(REG_USER_ID_COL) for r in registrations]
    emails_by_user_id = fetch_emails_by_user_id(client, user_ids)

    batches = build_event_batches(registrations, emails_by_user_id)
    for b in batches:
        logger.info(f"✅ '{b['event']['title']}': {b['count']} attendee(s)")
    return batches


# ── Persistence ─────────────────────────────────────────────────────────────

def save_batch(batch):
    """Save one event's batch to data/event_{id}_attendees.json."""
    os.makedirs(DATA_DIR, exist_ok=True)
    path = os.path.join(DATA_DIR, f"event_{batch['event']['id']}_attendees.json")
    with open(path, "w") as f:
        json.dump(batch, f, indent=2, default=str)
    logger.info(f"💾 Saved {path}")
    return path


def save_all(batches):
    """Save every event's batch, plus a combined summary file."""
    os.makedirs(DATA_DIR, exist_ok=True)
    paths = [save_batch(b) for b in batches]

    summary_path = os.path.join(DATA_DIR, "all_events_attendees.json")
    with open(summary_path, "w") as f:
        json.dump(batches, f, indent=2, default=str)
    logger.info(f"💾 Saved summary to {summary_path}")
    return paths, summary_path


# ── Sample data (for local testing, no DB call) ─────────────────────────────

def create_sample_data(title=None):
    """Write sample attendee batches so the rest of the pipeline can be tested
    without a real Supabase connection."""
    sample_titles = [
        ("Cypher Decode", [
            {"registration_id": 1, "full_name": "Jane Doe", "email": "jane@example.com",
             "college": "KMCT Institute of Emerging Technology and Management"},
            {"registration_id": 2, "full_name": "Rahul Menon", "email": "rahul@example.com",
             "college": "College of Engineering Trivandrum"},
        ]),
        ("Code Breach", [
            {"registration_id": 3, "full_name": "Sneha Prakash", "email": "sneha@example.com",
             "college": "NIT Calicut"},
        ]),
    ]
    # Derive "id" from the title with the same safe_id() used by fetch_all(),
    # so a file saved here is found the same way a real fetch would find it.
    sample_batches = [
        {
            "event": {"id": safe_id(t), "title": t,
                      "fest_name": FEST_NAME, "date_str": EVENT_DATE_STR or "6 OCTOBER 2026"},
            "attendees": attendees,
        }
        for t, attendees in sample_titles
    ]
    for b in sample_batches:
        b["count"] = len(b["attendees"])

    if title:
        matches = [b for b in sample_batches if b["event"]["title"].lower() == title.lower()]
        sample_batches = matches or sample_batches[:1]

    save_all(sample_batches)
    total = sum(b["count"] for b in sample_batches)
    logger.info(f"🧪 Sample data created for {len(sample_batches)} event(s), {total} attendee(s)")
    return sample_batches


# ── CLI ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fetch attended registrations from Supabase")
    parser.add_argument("--title", help="Only fetch this event's title (omit to fetch ALL events)")
    parser.add_argument("--supabase-url", help="Supabase URL override")
    parser.add_argument("--supabase-key", help="Supabase API key override")
    parser.add_argument("--sample", action="store_true", help="Write sample data instead of querying Supabase")
    parser.add_argument("--dry-run", action="store_true", help="Fall back to sample data if the DB is empty/unreachable")
    args = parser.parse_args()

    if args.sample:
        create_sample_data(args.title)
        return

    batches = None
    try:
        batches = fetch_all(title=args.title, supabase_url=args.supabase_url, supabase_key=args.supabase_key)
    except SystemExit:
        raise
    except Exception as e:
        logger.warning(f"Fetch failed: {e}")

    if batches:
        save_all(batches)
    elif args.dry_run:
        logger.info("🧪 Dry-run mode: DB returned no attendees. Generating sample data...")
        create_sample_data(args.title)
    else:
        logger.error(
            "❌ No attended registrations found in Supabase"
            + (f" for '{args.title}'" if args.title else "")
            + f"!\n   Make sure '{REG_ATTENDED_COL}' is set to {REG_ATTENDED_VALUE!r} for"
            "   participants who attended, or pass --dry-run to test with sample data."
        )
        sys.exit(1)


if __name__ == "__main__":
    main()
